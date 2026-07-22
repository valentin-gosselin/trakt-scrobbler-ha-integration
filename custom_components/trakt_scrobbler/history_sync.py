"""Backfill Plex watch history into Trakt.

Reads the Plex server watch history from a given start date and pushes the
movies and episodes that are not already on Trakt to /sync/history, using the
real watch date. Deduplication is done explicitly against the existing Trakt
history (not just relying on Trakt's own dedup), so re-running the import is
safe and idempotent.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    HISTORY_BATCH_SIZE,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    STORAGE_KEY_LAST_SYNC,
    SYNC_HISTORY,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
# How many Plex items to resolve per bulk metadata request.
FETCH_BATCH_SIZE = 50


def _to_utc_iso(value) -> str | None:
    """Normalize a datetime to a UTC ISO 8601 string Trakt accepts."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        # Plex viewedAt is naive local/UTC depending on the server; assume UTC
        # to stay deterministic. Users comparing timestamps to the minute won't
        # be affected because dedup rounds to the minute.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _dedup_key(ids: dict, watched_at: str | None) -> str | None:
    """Build a dedup key from the best available id plus the watch minute.

    A movie/episode can legitimately be watched more than once, so the key
    includes the watch time rounded to the minute rather than the id alone.
    """
    if not ids or not watched_at:
        return None
    # Prefer the most stable id available.
    for kind in ("imdb", "tmdb", "tvdb", "trakt"):
        if ids.get(kind):
            # Round to the minute (drop seconds) to tolerate small skews.
            minute = watched_at[:16]
            return f"{kind}:{ids[kind]}@{minute}"
    return None


def _fallback_key(entry: dict) -> str | None:
    """Dedup key when no ids are available: title/show + slot + watch minute."""
    watched_at = entry.get("watched_at")
    if not watched_at:
        return None
    minute = watched_at[:16]
    if entry["_type"] == MEDIA_TYPE_MOVIE:
        title = (entry.get("movie", {}) or {}).get("title") or ""
        return f"movie:{title.lower()}@{minute}"
    show = (entry.get("show", {}) or {}).get("title") or ""
    ep = entry.get("episode", {}) or {}
    return f"ep:{show.lower()}:s{ep.get('season')}e{ep.get('number')}@{minute}"


def _ids_from_guids(guids) -> dict:
    """Turn a list of Plex guid objects into an imdb/tmdb/tvdb id dict."""
    ids: dict = {}
    for guid in guids or []:
        gid = getattr(guid, "id", "") or ""
        if gid.startswith("imdb://"):
            ids["imdb"] = gid.replace("imdb://", "")
        elif gid.startswith("tmdb://"):
            ids["tmdb"] = gid.replace("tmdb://", "")
        elif gid.startswith("tvdb://"):
            ids["tvdb"] = gid.replace("tvdb://", "")
    return ids


class HistorySync:
    """Import Plex watch history into Trakt for a given scrobbler entity."""

    def __init__(self, entity) -> None:
        """Bind to a scrobbler entity that provides Plex + Trakt access."""
        self._entity = entity
        self._hass = entity.hass
        self._account_id = None
        self._store = Store(
            entity.hass, STORAGE_VERSION, f"{DOMAIN}_{STORAGE_KEY_LAST_SYNC}"
        )

    async def _async_get_last_sync(self) -> datetime | None:
        """Return the datetime of the most recently synced watch, if any."""
        data = await self._store.async_load()
        if not data or not data.get("last_watched_at"):
            return None
        try:
            return datetime.fromisoformat(data["last_watched_at"])
        except ValueError:
            return None

    async def _async_set_last_sync(self, value: datetime) -> None:
        """Persist the datetime of the most recently synced watch."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        await self._store.async_save({"last_watched_at": value.isoformat()})

    async def async_auto_sync(self) -> dict:
        """Incremental sync: push Plex watches newer than the last sync point.

        Runs with dry_run disabled. Uses the stored last-sync date as the start
        date (falling back to the last 7 days on first run), then advances the
        stored point to the newest watch it saw so the next run only covers new
        history.
        """
        last = await self._async_get_last_sync()
        if last is None:
            from datetime import timedelta

            last = datetime.now(timezone.utc) - timedelta(days=7)
            _LOGGER.debug("No previous sync point, starting from %s", last.isoformat())

        newest = await self._async_newest_plex_watch(last)
        summary = await self.async_import(last, dry_run=False)

        # Advance the stored point only if the run didn't error out, so a failed
        # run is retried next time instead of silently skipping history.
        if newest is not None and summary.get("errors", 0) == 0:
            await self._async_set_last_sync(newest)
        return summary

    async def _async_newest_plex_watch(self, since: datetime) -> datetime | None:
        """Return the most recent viewedAt among Plex history since a date."""
        plex = self._entity._plex_server
        if plex is None:
            return None
        try:
            items = await self._hass.async_add_executor_job(
                self._read_own_history, plex, since
            )
        except Exception:  # noqa: BLE001
            return None
        newest = None
        for item in items:
            viewed = getattr(item, "viewedAt", None)
            if isinstance(viewed, datetime) and (newest is None or viewed > newest):
                newest = viewed
        return newest

    async def async_import(self, start_date: datetime, dry_run: bool = True) -> dict:
        """Run the backfill.

        Returns a summary dict: found / already_present / to_add / pushed / errors.
        When dry_run is True, nothing is sent to Trakt; the diff is only logged.
        """
        summary = {
            "found": 0,
            "already_present": 0,
            "to_add": 0,
            "pushed": 0,
            "errors": 0,
            "dry_run": dry_run,
        }

        # The Plex connection is set up in a background task, so right after
        # setup it may not be ready yet. Wait briefly for it before giving up.
        plex = await self._async_wait_for_plex()
        if plex is None:
            _LOGGER.error(
                "Cannot import history: Plex server is not connected "
                "(check the Plex URL/token in the integration options)"
            )
            summary["errors"] += 1
            return summary

        # 1. Read Plex history since start_date, filtered to the token's own
        #    account so we never scrobble other Plex users' watches. All Plex
        #    I/O runs in the executor (plexapi is synchronous).
        try:
            plex_items = await self._hass.async_add_executor_job(
                self._read_own_history, plex, start_date
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to read Plex history: %s", err)
            summary["errors"] += 1
            return summary

        summary["found"] = len(plex_items)
        _LOGGER.info(
            "Found %d Plex history items since %s",
            len(plex_items),
            start_date.isoformat(),
        )

        # 2. Read existing Trakt history since start_date to deduplicate.
        existing_keys = await self._async_get_trakt_history_keys(start_date)

        # 3. Keep only movies/episodes and drop obvious duplicates using data
        #    already present on the lightweight history entries (no network), so
        #    we don't fetch full items for everything (music, rewatches, ...).
        candidates = [
            item
            for item in plex_items
            if getattr(item, "type", None) in ("movie", "episode")
        ]

        # 4. Resolve full items (which carry the ids) in an executor: source()
        #    is a blocking network call and must not run in the event loop.
        entries = await self._hass.async_add_executor_job(
            self._map_items, candidates
        )

        to_push: list[dict] = []
        for entry in entries:
            if entry is None:
                continue
            key = _dedup_key(entry["_ids"], entry["watched_at"]) or _fallback_key(
                entry
            )
            if key and key in existing_keys:
                summary["already_present"] += 1
                continue
            summary["to_add"] += 1
            to_push.append(entry)

        _LOGGER.info(
            "Backfill diff: %d found, %d already on Trakt, %d to add",
            summary["found"],
            summary["already_present"],
            summary["to_add"],
        )

        if dry_run:
            for entry in to_push:
                _LOGGER.info(
                    "[dry-run] would add: %s (%s) watched_at=%s ids=%s",
                    entry.get("_label"),
                    entry["_type"],
                    entry["watched_at"],
                    entry["_ids"],
                )
            return summary

        # 4. Push in batches, respecting the entity's throttling in _api_request.
        summary["pushed"] = await self._async_push(to_push, summary)
        return summary

    async def _async_get_trakt_history_keys(self, start_date: datetime) -> set:
        """Fetch existing Trakt history since start_date as a set of dedup keys."""
        keys: set = set()
        start_iso = _to_utc_iso(start_date)
        page = 1
        while True:
            endpoint = (
                f"{SYNC_HISTORY}?start_at={start_iso}&limit=1000&page={page}"
            )
            data = await self._entity._api_request(endpoint, method="GET")
            if not data or not isinstance(data, list):
                break
            for row in data:
                watched_at = row.get("watched_at")
                obj = row.get(row.get("type", ""), {})
                ids = (obj.get("ids") or {}) if isinstance(obj, dict) else {}
                # Episodes carry ids on the show; also index the episode's own ids.
                key = _dedup_key(ids, watched_at)
                if key:
                    keys.add(key)
            if len(data) < 1000:
                break
            page += 1
        _LOGGER.debug("Loaded %d existing Trakt history keys", len(keys))
        return keys

    async def _async_wait_for_plex(self, timeout: float = 30.0):
        """Wait for the entity's Plex connection to be ready, up to timeout."""
        import asyncio

        waited = 0.0
        while self._entity._plex_server is None and waited < timeout:
            await asyncio.sleep(1)
            waited += 1
        return self._entity._plex_server

    def _resolve_account_id(self, plex):
        """Return the local Plex accountID that owns the configured token.

        Plex history mixes every user of the server. To only import our own
        watches we need the *local* accountID of the token holder, which is not
        necessarily 1 (the owner): a shared/managed user has their own id. We
        map the token's plex.tv username to the local accountID reported by the
        server's systemAccounts. Result is cached on the instance.
        """
        if self._account_id is not None:
            return self._account_id
        try:
            from plexapi.myplex import MyPlexAccount

            token = self._entity._plex_token
            username = MyPlexAccount(token=token).username
            for sa in plex.systemAccounts():
                if sa.name and username and sa.name.lower() == username.lower():
                    self._account_id = sa.accountID
                    _LOGGER.debug(
                        "Resolved Plex account '%s' to local id %s",
                        username,
                        sa.accountID,
                    )
                    return self._account_id
            _LOGGER.warning(
                "Could not match the Plex token account '%s' to a server "
                "account; history will not be filtered by user",
                username,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to resolve Plex account id: %s", err)
        return None

    def _read_own_history(self, plex, start_date):
        """Read Plex history since start_date for the token's own account only."""
        account_id = self._resolve_account_id(plex)
        if account_id is not None:
            return plex.history(mindate=start_date, accountID=account_id)
        # Fallback: if we couldn't resolve the account, don't import anything
        # rather than risk scrobbling other users' history.
        _LOGGER.error(
            "Refusing to import Plex history because the token's own account "
            "could not be identified (avoids importing other users' watches)"
        )
        return []

    def _map_items(self, items: list) -> list:
        """Map Plex history items to Trakt entries (runs in an executor).

        History entries are lightweight and carry no guids. Rather than loading
        each item individually (one network round-trip per item), we resolve the
        full items in bulk by ratingKey, a handful of requests for thousands of
        items. This does blocking network I/O, so it must run in an executor,
        never in the event loop.
        """
        plex = self._entity._plex_server

        # Build a ratingKey -> full item map using bulk metadata requests.
        full_by_key: dict = {}
        rating_keys = [
            str(getattr(it, "ratingKey", "") or "")
            for it in items
            if getattr(it, "ratingKey", None)
        ]
        import time

        for start in range(0, len(rating_keys), FETCH_BATCH_SIZE):
            chunk = [k for k in rating_keys[start : start + FETCH_BATCH_SIZE] if k]
            if not chunk:
                continue
            path = f"/library/metadata/{','.join(chunk)}"
            fetched = None
            # Retry a few times: resolving Plex's *.plex.direct hostnames can be
            # flaky, and a transient failure here would drop ids for the chunk.
            for attempt in range(3):
                try:
                    fetched = plex.fetchItems(path)
                    break
                except Exception as err:  # noqa: BLE001
                    if attempt == 2:
                        _LOGGER.warning(
                            "Bulk metadata fetch failed for %d items after "
                            "retries (ids may be missing for these): %s",
                            len(chunk),
                            err,
                        )
                    else:
                        time.sleep(1)
            for full in fetched or []:
                key = str(getattr(full, "ratingKey", "") or "")
                if key:
                    full_by_key[key] = full

        entries = []
        for item in items:
            key = str(getattr(item, "ratingKey", "") or "")
            full = full_by_key.get(key)
            entries.append(self._history_entry(item, full))
        return entries

    def _history_entry(self, item, full) -> dict | None:
        """Map a Plex history item (+ its pre-resolved full item) to Trakt.

        Only movies and episodes are handled; music and other types are ignored.
        `full` is the bulk-resolved library item that carries the guids; it may
        be None if resolution failed, in which case we fall back to the
        lightweight history item (title/season/number are on it anyway).
        """
        item_type = getattr(item, "type", None)
        if item_type not in ("movie", "episode"):
            return None

        watched_at = _to_utc_iso(getattr(item, "viewedAt", None))
        if not watched_at:
            return None

        src = full or item

        if item_type == "movie":
            ids = _ids_from_guids(getattr(src, "guids", None))
            title = getattr(src, "title", None) or getattr(item, "title", None)
            movie: dict = {"title": title}
            year = getattr(src, "year", None) or getattr(item, "year", None)
            if year:
                movie["year"] = year
            if ids:
                movie["ids"] = ids
            return {
                "_type": MEDIA_TYPE_MOVIE,
                "_ids": ids,
                "_label": title or "?",
                "watched_at": watched_at,
                "movie": movie,
            }

        # episode: season/number come from the lightweight history item, which
        # always has them; the guids come from the full item when available.
        show_title = getattr(item, "grandparentTitle", None) or getattr(
            src, "grandparentTitle", None
        )
        season = getattr(item, "parentIndex", None)
        if season is None:
            season = getattr(src, "parentIndex", None)
        number = getattr(item, "index", None)
        if number is None:
            number = getattr(src, "index", None)
        if season is None or number is None:
            return None
        # The episode's own guids are on the full item (already fetched in bulk).
        # Trakt matches an episode by its own ids too, so we attach them to the
        # episode object alongside the season/number and the show title.
        episode_ids = _ids_from_guids(getattr(src, "guids", None))
        show: dict = {"title": show_title}
        episode: dict = {"season": season, "number": number}
        if episode_ids:
            episode["ids"] = episode_ids
        return {
            "_type": MEDIA_TYPE_EPISODE,
            "_ids": episode_ids,
            "_label": f"{show_title} S{season}E{number}",
            "watched_at": watched_at,
            "show": show,
            "episode": episode,
        }

    async def _async_push(self, to_push: list[dict], summary: dict) -> int:
        """Push entries to Trakt in batches; return the number pushed."""
        pushed = 0
        for start in range(0, len(to_push), HISTORY_BATCH_SIZE):
            batch = to_push[start : start + HISTORY_BATCH_SIZE]
            payload = {"movies": [], "episodes": []}
            for entry in batch:
                if entry["_type"] == MEDIA_TYPE_MOVIE:
                    payload["movies"].append(
                        {"watched_at": entry["watched_at"], **_movie_body(entry)}
                    )
                else:
                    payload["episodes"].append(
                        {"watched_at": entry["watched_at"], **_episode_body(entry)}
                    )
            result = await self._entity._api_request(
                SYNC_HISTORY, method="POST", data=payload
            )
            if result is None:
                summary["errors"] += 1
                _LOGGER.error("Failed to push a batch of %d items", len(batch))
                continue
            added = result.get("added", {}) if isinstance(result, dict) else {}
            pushed += (added.get("movies", 0) or 0) + (added.get("episodes", 0) or 0)
            _LOGGER.info(
                "Pushed batch: Trakt added %s movies, %s episodes",
                added.get("movies", 0),
                added.get("episodes", 0),
            )
        return pushed


def _movie_body(entry: dict) -> dict:
    """Return the movie fields of a /sync/history entry.

    Trakt wants the movie's title/year/ids flat on the entry (not wrapped in a
    "movie" object), matching primarily by ids.
    """
    movie = entry.get("movie", {}) or {}
    body: dict = {}
    if movie.get("ids"):
        body["ids"] = movie["ids"]
    if movie.get("title"):
        body["title"] = movie["title"]
    if movie.get("year"):
        body["year"] = movie["year"]
    return body


def _episode_body(entry: dict) -> dict:
    """Return the episode portion of a /sync/history entry.

    Trakt matches an episode most reliably by its own ids alone. When the
    episode has ids we send just {ids}; otherwise we fall back to identifying it
    by show title + season + episode number (which requires the show to be
    resolvable by title on Trakt).
    """
    episode = entry.get("episode", {}) or {}
    ids = episode.get("ids")
    if ids:
        return {"ids": ids}
    # Fallback with no episode ids: identify via show title + season/number.
    return {
        "show": entry.get("show", {}),
        "episode": {
            "season": episode.get("season"),
            "number": episode.get("number"),
        },
    }
