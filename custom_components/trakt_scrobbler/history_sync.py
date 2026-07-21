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

from .const import (
    HISTORY_BATCH_SIZE,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    SYNC_HISTORY,
)

_LOGGER = logging.getLogger(__name__)


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


def _plex_guids_to_ids(item) -> dict:
    """Extract imdb/tmdb/tvdb ids from a Plex history item's guids."""
    ids: dict = {}
    guids = getattr(item, "guids", None) or []
    for guid in guids:
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

        plex = self._entity._plex_server
        if plex is None:
            _LOGGER.error(
                "Cannot import history: Plex server is not connected "
                "(check the Plex URL/token in the integration options)"
            )
            summary["errors"] += 1
            return summary

        # 1. Read Plex history since start_date (runs in executor: plexapi is sync)
        try:
            plex_items = await self._hass.async_add_executor_job(
                lambda: plex.history(mindate=start_date)
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

        # 3. Build the batch of items missing from Trakt.
        to_push: list[dict] = []
        for item in plex_items:
            entry = self._plex_item_to_trakt(item)
            if entry is None:
                continue
            key = _dedup_key(entry["_ids"], entry["watched_at"])
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

    def _plex_item_to_trakt(self, item) -> dict | None:
        """Map a Plex history item to a Trakt /sync/history entry."""
        watched_at = _to_utc_iso(getattr(item, "viewedAt", None))
        if not watched_at:
            return None
        ids = _plex_guids_to_ids(item)
        item_type = getattr(item, "type", None)

        if item_type == "movie":
            movie: dict = {"title": getattr(item, "title", None)}
            year = getattr(item, "year", None)
            if year:
                movie["year"] = year
            if ids:
                movie["ids"] = ids
            return {
                "_type": MEDIA_TYPE_MOVIE,
                "_ids": ids,
                "_label": getattr(item, "title", "?"),
                "watched_at": watched_at,
                "movie": movie,
            }

        if item_type == "episode":
            show_title = getattr(item, "grandparentTitle", None)
            season = getattr(item, "parentIndex", None)
            number = getattr(item, "index", None)
            if season is None or number is None:
                return None
            show: dict = {"title": show_title}
            if ids:
                show["ids"] = ids
            return {
                "_type": MEDIA_TYPE_EPISODE,
                "_ids": ids,
                "_label": f"{show_title} S{season}E{number}",
                "watched_at": watched_at,
                "show": show,
                "episode": {"season": season, "number": number},
            }

        return None

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
    """Return the movie portion of a /sync/history entry."""
    return {"movie": entry["movie"]}


def _episode_body(entry: dict) -> dict:
    """Return the show/episode portion of a /sync/history entry."""
    return {"show": entry["show"], "episode": entry["episode"]}
