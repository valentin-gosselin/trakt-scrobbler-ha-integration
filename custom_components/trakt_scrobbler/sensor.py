"""Trakt data sensors.

Sensors are created per enabled group from the shared TraktDataCoordinator.
This module starts empty (S1: coordinator plumbing only) and gains sensor
classes in later stories.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_COORDINATOR
from .const import DOMAIN
from .options import enabled_groups

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
    # Sensor classes are added per group by later stories, e.g.:
    #   if GROUP_UPCOMING in groups:
    #       entities.append(TraktUpcomingSensor(coordinator, entry, "shows"))
    _ = (coordinator, groups)  # referenced now; used as stories land

    async_add_entities(entities)
