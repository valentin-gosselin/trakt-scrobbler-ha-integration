"""Trakt data sensors.

Sensors are created per enabled group from the shared TraktDataCoordinator.
The scrobbler (media_player.py) is unaffected.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DATA_COORDINATOR
from .const import DOMAIN, GROUP_UPCOMING
from .options import enabled_groups
from .umc import (
    movie_calendar_to_umc,
    show_calendar_to_umc,
    umc_header,
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
        umc = [umc_header()]
        for entry in items:
            umc.append(mapper(entry))

        # Native, easy-to-read attributes alongside the UMC `data` array.
        next_item = umc[1] if len(umc) > 1 else {}
        return {
            "count": len(items),
            "next_title": next_item.get("title"),
            "next_air_date": next_item.get("airdate"),
            "data": umc,
        }
