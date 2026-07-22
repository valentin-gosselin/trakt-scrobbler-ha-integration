"""Data update coordinator for Trakt read endpoints (sensors).

Keeps sensor data (upcoming, next-to-watch, watchlist, stats, recommendations)
fresh via the Home Assistant DataUpdateCoordinator, using the same OAuth token
as the scrobbler. It is intentionally separate from the real-time scrobbling in
media_player.py, which stays untouched.
"""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_UPCOMING_DAYS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DEFAULT_UPCOMING_DAYS,
    DOMAIN,
    GROUP_NEXT,
    GROUP_RECO,
    GROUP_STATS,
    GROUP_UPCOMING,
    GROUP_WATCHLIST,
    NEXT_TO_WATCH_MAX_SHOWS,
    TRAKT_API_URL,
    TRAKT_API_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class TraktDataCoordinator(DataUpdateCoordinator):
    """Fetch Trakt read data for the enabled sensor groups."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        groups: set[str],
    ) -> None:
        """Initialize the coordinator.

        `groups` is the set of enabled sensor groups; only those are fetched.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_data",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self._entry = entry
        self._groups = groups
        self._session = async_get_clientsession(hass)

    @property
    def _config(self) -> dict:
        """Return the merged config entry data/options."""
        return {**self._entry.data, **self._entry.options}

    @property
    def _headers(self) -> dict:
        """Trakt API headers using the shared OAuth token."""
        config = self._config
        return {
            "Content-Type": "application/json",
            "trakt-api-version": TRAKT_API_VERSION,
            "trakt-api-key": config.get(CONF_CLIENT_ID, ""),
            "Authorization": f"Bearer {config.get(CONF_ACCESS_TOKEN, '')}",
        }

    async def _get(self, endpoint: str):
        """Authenticated GET against the Trakt API; returns parsed JSON or None."""
        url = f"{TRAKT_API_URL}{endpoint}"
        try:
            async with self._session.get(
                url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status == 429:
                    _LOGGER.warning("Trakt rate limit hit on %s", endpoint)
                elif resp.status == 401:
                    _LOGGER.error(
                        "Trakt auth error on %s (token may be expired)", endpoint
                    )
                else:
                    _LOGGER.debug("Trakt GET %s returned %s", endpoint, resp.status)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Trakt GET %s failed: %s", endpoint, err)
        return None

    async def async_post(self, endpoint: str, payload: dict):
        """Authenticated POST against the Trakt API; returns parsed JSON or None."""
        url = f"{TRAKT_API_URL}{endpoint}"
        try:
            async with self._session.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                if resp.status == 429:
                    _LOGGER.warning("Trakt rate limit hit on POST %s", endpoint)
                elif resp.status == 401:
                    _LOGGER.error("Trakt auth error on POST %s", endpoint)
                else:
                    text = await resp.text()
                    _LOGGER.error(
                        "Trakt POST %s returned %s: %s", endpoint, resp.status, text
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Trakt POST %s failed: %s", endpoint, err)
        return None

    async def _async_update_data(self) -> dict:
        """Fetch data for the enabled groups.

        Each group adds its own key to the returned dict. Groups are added by
        later stories; for now this returns an empty dict (or only the groups
        implemented so far), which is a valid, no-entity state.
        """
        data: dict = {}

        if GROUP_UPCOMING in self._groups:
            days = self._config.get(CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS)
            # Trakt calendars are date-anchored; "today" in UTC is fine here.
            start = dt_util.utcnow().strftime("%Y-%m-%d")
            shows = await self._get(
                f"/calendars/my/shows/{start}/{days}?extended=full"
            )
            movies = await self._get(
                f"/calendars/my/movies/{start}/{days}?extended=full"
            )
            data["upcoming_shows"] = shows if isinstance(shows, list) else []
            data["upcoming_movies"] = movies if isinstance(movies, list) else []

        if GROUP_NEXT in self._groups:
            data["next_to_watch"] = await self._fetch_next_to_watch()

        if GROUP_WATCHLIST in self._groups:
            wl = await self._get("/sync/watchlist?extended=full")
            data["watchlist"] = wl if isinstance(wl, list) else []

        if GROUP_STATS in self._groups:
            stats = await self._get("/users/me/stats")
            data["stats"] = stats if isinstance(stats, dict) else {}

        if GROUP_RECO in self._groups:
            rec_shows = await self._get(
                "/recommendations/shows?limit=20&extended=full"
            )
            rec_movies = await self._get(
                "/recommendations/movies?limit=20&extended=full"
            )
            data["reco_shows"] = rec_shows if isinstance(rec_shows, list) else []
            data["reco_movies"] = rec_movies if isinstance(rec_movies, list) else []

        return data

    async def _fetch_next_to_watch(self) -> list:
        """Return the next unwatched episode for in-progress shows.

        Progress requires one request per show, so we look only at the most
        recently watched shows (capped) to stay well within Trakt's rate limit,
        and keep only shows that actually have an aired next episode.
        """
        watched = await self._get("/sync/watched/shows?extended=noseasons")
        if not isinstance(watched, list):
            return []
        watched.sort(key=lambda x: x.get("last_watched_at") or "", reverse=True)

        results: list = []
        for entry in watched[:NEXT_TO_WATCH_MAX_SHOWS]:
            show = entry.get("show") or {}
            ids = show.get("ids") or {}
            trakt_id = ids.get("trakt")
            if not trakt_id:
                continue
            progress = await self._get(
                f"/shows/{trakt_id}/progress/watched"
                "?hidden=false&specials=false&count_specials=false"
            )
            if not isinstance(progress, dict):
                continue
            next_ep = progress.get("next_episode")
            if not next_ep:
                continue  # show is up to date on aired episodes
            # watched/shows never returns images, so fetch them for the few
            # shows we actually keep (those with a ready next episode).
            full_show = await self._get(
                f"/shows/{trakt_id}?extended=full,images"
            )
            if isinstance(full_show, dict) and full_show.get("images"):
                show = {**show, "images": full_show["images"]}
                if full_show.get("genres"):
                    show["genres"] = full_show["genres"]
                if full_show.get("rating"):
                    show["rating"] = full_show["rating"]
            results.append(
                {
                    "show": show,
                    "next_episode": next_ep,
                    "aired": progress.get("aired"),
                    "completed": progress.get("completed"),
                    "last_watched_at": entry.get("last_watched_at"),
                }
            )
        return results
