"""Action services that write to Trakt (watchlist, mark watched).

These reuse the data coordinator's authenticated POST so they share the same
token and error handling as the sensors.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_EPISODE_FIELD,
    ATTR_MEDIA_TYPE_FIELD,
    ATTR_SEASON_FIELD,
    ATTR_TITLE,
    DOMAIN,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    SERVICE_ADD_TO_WATCHLIST,
    SERVICE_MARK_WATCHED,
    SERVICE_REMOVE_FROM_WATCHLIST,
)

_LOGGER = logging.getLogger(__name__)

_ID_FIELDS = ("trakt", "imdb", "tmdb", "tvdb")

WATCHLIST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDIA_TYPE_FIELD): vol.In(["movie", "show"]),
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional("year"): vol.Coerce(int),
        vol.Optional("trakt"): cv.string,
        vol.Optional("imdb"): cv.string,
        vol.Optional("tmdb"): cv.string,
        vol.Optional("tvdb"): cv.string,
    }
)

MARK_WATCHED_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDIA_TYPE_FIELD): vol.In(["movie", "episode"]),
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional("year"): vol.Coerce(int),
        vol.Optional(ATTR_SEASON_FIELD): vol.Coerce(int),
        vol.Optional(ATTR_EPISODE_FIELD): vol.Coerce(int),
        vol.Optional("trakt"): cv.string,
        vol.Optional("imdb"): cv.string,
        vol.Optional("tmdb"): cv.string,
        vol.Optional("tvdb"): cv.string,
    }
)


def _ids_from_call(data: dict) -> dict:
    """Collect provided external ids from a service call."""
    ids: dict = {}
    for field in _ID_FIELDS:
        if data.get(field):
            ids[field] = data[field]
    return ids


def _first_coordinator(hass: HomeAssistant):
    """Return any available data coordinator (single-entry is the common case)."""
    from . import DATA_COORDINATOR

    coordinators = hass.data.get(DOMAIN, {}).get(DATA_COORDINATOR, {})
    return next(iter(coordinators.values()), None)


def async_register_trakt_services(hass: HomeAssistant) -> None:
    """Register the Trakt action services (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_TO_WATCHLIST):
        return

    async def _watchlist(call: ServiceCall, remove: bool) -> None:
        coordinator = _first_coordinator(hass)
        if coordinator is None:
            _LOGGER.error("No Trakt coordinator available for the service")
            return
        media_type = call.data[ATTR_MEDIA_TYPE_FIELD]
        obj: dict = {}
        ids = _ids_from_call(call.data)
        if ids:
            obj["ids"] = ids
        if call.data.get(ATTR_TITLE):
            obj["title"] = call.data[ATTR_TITLE]
        if call.data.get("year"):
            obj["year"] = call.data["year"]
        key = "movies" if media_type == "movie" else "shows"
        payload = {key: [obj]}
        endpoint = "/sync/watchlist/remove" if remove else "/sync/watchlist"
        result = await coordinator.async_post(endpoint, payload)
        _LOGGER.info(
            "%s watchlist %s: %s",
            "Removed from" if remove else "Added to",
            media_type,
            result,
        )
        await coordinator.async_request_refresh()

    async def _add_watchlist(call: ServiceCall) -> None:
        await _watchlist(call, remove=False)

    async def _remove_watchlist(call: ServiceCall) -> None:
        await _watchlist(call, remove=True)

    async def _mark_watched(call: ServiceCall) -> None:
        coordinator = _first_coordinator(hass)
        if coordinator is None:
            _LOGGER.error("No Trakt coordinator available for the service")
            return
        media_type = call.data[ATTR_MEDIA_TYPE_FIELD]
        ids = _ids_from_call(call.data)
        payload: dict = {"movies": [], "episodes": [], "shows": []}
        if media_type == MEDIA_TYPE_MOVIE:
            movie: dict = {}
            if ids:
                movie["ids"] = ids
            if call.data.get(ATTR_TITLE):
                movie["title"] = call.data[ATTR_TITLE]
            if call.data.get("year"):
                movie["year"] = call.data["year"]
            payload["movies"].append(movie)
        else:  # episode
            season = call.data.get(ATTR_SEASON_FIELD)
            number = call.data.get(ATTR_EPISODE_FIELD)
            if ids and not (season and number):
                # Episode identified by its own ids.
                payload["episodes"].append({"ids": ids})
            elif ids and season and number:
                # Show ids + season/number nested under shows.
                payload["shows"].append(
                    {
                        "ids": ids,
                        "seasons": [
                            {"number": season, "episodes": [{"number": number}]}
                        ],
                    }
                )
            else:
                _LOGGER.error(
                    "mark_watched for an episode needs ids, or show ids + "
                    "season + episode"
                )
                return
        result = await coordinator.async_post("/sync/history", payload)
        _LOGGER.info("Marked watched (%s): %s", media_type, result)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TO_WATCHLIST, _add_watchlist, schema=WATCHLIST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_FROM_WATCHLIST,
        _remove_watchlist,
        schema=WATCHLIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MARK_WATCHED, _mark_watched, schema=MARK_WATCHED_SCHEMA
    )
