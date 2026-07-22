"""Trakt data sensors.

Sensors are created per enabled group from the shared TraktDataCoordinator.
The scrobbler (media_player.py) is unaffected.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DATA_COORDINATOR
from .const import (
    DOMAIN,
    GROUP_NEXT,
    GROUP_RECO,
    GROUP_STATS,
    GROUP_UPCOMING,
    GROUP_WATCHLIST,
)
from .options import enabled_groups
from .umc import (
    movie_calendar_to_umc,
    next_to_watch_to_umc,
    recommendation_to_umc,
    show_calendar_to_umc,
    umc_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trakt sensors for the enabled groups."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id]
    groups = enabled_groups(entry)

    entities: list[SensorEntity] = []

    if GROUP_UPCOMING in groups:
        entities.append(TraktUpcomingSensor(coordinator, entry, "shows"))
        entities.append(TraktUpcomingSensor(coordinator, entry, "movies"))

    if GROUP_NEXT in groups:
        entities.append(TraktNextToWatchSensor(coordinator, entry))

    if GROUP_WATCHLIST in groups:
        entities.append(TraktWatchlistSensor(coordinator, entry))

    if GROUP_STATS in groups:
        entities.append(TraktStatsSensor(coordinator, entry))

    if GROUP_RECO in groups:
        entities.append(TraktRecommendationsSensor(coordinator, entry, "shows"))
        entities.append(TraktRecommendationsSensor(coordinator, entry, "movies"))

    async_add_entities(entities)


class TraktBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Trakt data sensors backed by the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, key: str) -> None:
        """Initialize with a stable unique id derived from the entry + key."""
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Trakt Scrobbler",
            manufacturer="Trakt",
        )


class TraktUpcomingSensor(TraktBaseSensor):
    """Upcoming shows or movies, formatted for the Upcoming Media Card."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry: ConfigEntry, kind: str) -> None:
        """kind is 'shows' or 'movies'."""
        super().__init__(coordinator, entry, f"upcoming_{kind}")
        self._kind = kind
        self._attr_name = (
            "Upcoming shows" if kind == "shows" else "Upcoming movies"
        )

    @property
    def _items(self) -> list:
        data = self.coordinator.data or {}
        return data.get(f"upcoming_{self._kind}") or []

    @property
    def native_value(self):
        """State is the number of upcoming items."""
        return len(self._items)

    @property
    def extra_state_attributes(self) -> dict:
        items = self._items
        mapper = (
            show_calendar_to_umc if self._kind == "shows" else movie_calendar_to_umc
        )
        mapped = [mapper(entry) for entry in items]
        empty = (
            "No upcoming shows"
            if self._kind == "shows"
            else "No upcoming movies"
        )
        umc = umc_data(mapped, empty)

        first = mapped[0] if mapped else {}
        return {
            "count": len(items),
            "next_title": first.get("title"),
            "next_air_date": first.get("airdate"),
            "data": umc,
        }


class TraktNextToWatchSensor(TraktBaseSensor):
    """Next unwatched episode across in-progress shows."""

    _attr_icon = "mdi:play-box-multiple"
    _attr_name = "Next to watch"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the next-to-watch sensor."""
        super().__init__(coordinator, entry, "next_to_watch")

    @property
    def _items(self) -> list:
        return (self.coordinator.data or {}).get("next_to_watch") or []

    @property
    def native_value(self):
        """State is the number of shows with a ready next episode."""
        return len(self._items)

    @property
    def extra_state_attributes(self) -> dict:
        items = self._items
        shows = []
        mapped = []
        for entry in items:
            show = entry.get("show") or {}
            ep = entry.get("next_episode") or {}
            shows.append(
                {
                    "show": show.get("title"),
                    "season": ep.get("season"),
                    "number": ep.get("number"),
                    "episode_title": ep.get("title"),
                    "aired_episodes": entry.get("aired"),
                    "watched_episodes": entry.get("completed"),
                }
            )
            mapped.append(next_to_watch_to_umc(entry))
        return {
            "count": len(items),
            "shows": shows,
            "data": umc_data(mapped, "Nothing to watch"),
        }


class TraktWatchlistSensor(TraktBaseSensor):
    """The user's Trakt watchlist (movies and shows)."""

    _attr_icon = "mdi:bookmark-multiple"
    _attr_name = "Watchlist"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the watchlist sensor."""
        super().__init__(coordinator, entry, "watchlist")

    @property
    def _items(self) -> list:
        return (self.coordinator.data or {}).get("watchlist") or []

    @property
    def native_value(self):
        """State is the number of items on the watchlist."""
        return len(self._items)

    @property
    def extra_state_attributes(self) -> dict:
        items = []
        for entry in self._items:
            media_type = entry.get("type")
            obj = entry.get(media_type) if media_type else None
            obj = obj or {}
            items.append(
                {
                    "type": media_type,
                    "title": obj.get("title"),
                    "year": obj.get("year"),
                    "ids": obj.get("ids"),
                }
            )
        return {"count": len(items), "items": items}


class TraktStatsSensor(TraktBaseSensor):
    """Aggregate Trakt watch statistics."""

    _attr_icon = "mdi:chart-box"
    _attr_name = "Stats"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the stats sensor."""
        super().__init__(coordinator, entry, "stats")

    @property
    def _stats(self) -> dict:
        return (self.coordinator.data or {}).get("stats") or {}

    @property
    def native_value(self):
        """State is total movies + episodes watched."""
        stats = self._stats
        movies = (stats.get("movies") or {}).get("watched", 0)
        episodes = (stats.get("episodes") or {}).get("watched", 0)
        return (movies or 0) + (episodes or 0)

    @property
    def extra_state_attributes(self) -> dict:
        stats = self._stats
        movies = stats.get("movies") or {}
        episodes = stats.get("episodes") or {}
        shows = stats.get("shows") or {}
        total_minutes = (movies.get("minutes", 0) or 0) + (
            episodes.get("minutes", 0) or 0
        )
        return {
            "movies_watched": movies.get("watched"),
            "movies_plays": movies.get("plays"),
            "episodes_watched": episodes.get("watched"),
            "episodes_plays": episodes.get("plays"),
            "shows_watched": shows.get("watched"),
            "total_minutes": total_minutes,
            "total_days": round(total_minutes / 1440, 1) if total_minutes else 0,
        }


class TraktRecommendationsSensor(TraktBaseSensor):
    """Personalized Trakt recommendations for shows or movies."""

    _attr_icon = "mdi:star-shooting"

    def __init__(self, coordinator, entry: ConfigEntry, kind: str) -> None:
        """kind is 'shows' or 'movies'."""
        super().__init__(coordinator, entry, f"reco_{kind}")
        self._kind = kind
        self._attr_name = (
            "Recommended shows" if kind == "shows" else "Recommended movies"
        )

    @property
    def _items(self) -> list:
        return (self.coordinator.data or {}).get(f"reco_{self._kind}") or []

    @property
    def native_value(self):
        """State is the number of recommendations."""
        return len(self._items)

    @property
    def extra_state_attributes(self) -> dict:
        mapped = [recommendation_to_umc(o, self._kind) for o in self._items]
        items = []
        for obj, m in zip(self._items, mapped):
            items.append(
                {
                    "title": obj.get("title"),
                    "year": obj.get("year"),
                    "ids": obj.get("ids"),
                    "overview": obj.get("overview"),
                    "poster": m.get("poster"),
                    "fanart": m.get("fanart"),
                    "rating": m.get("rating"),
                    "link": m.get("deep_link"),
                }
            )
        return {
            "count": len(items),
            "items": items,
            "data": umc_data(mapped, "No recommendations"),
        }
