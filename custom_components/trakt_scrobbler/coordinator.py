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

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
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

    async def _async_update_data(self) -> dict:
        """Fetch data for the enabled groups.

        Each group adds its own key to the returned dict. Groups are added by
        later stories; for now this returns an empty dict (or only the groups
        implemented so far), which is a valid, no-entity state.
        """
        data: dict = {}
        # Group fetches are added incrementally by later stories, e.g.:
        #   if GROUP_UPCOMING in self._groups: data["upcoming_shows"] = ...
        return data
