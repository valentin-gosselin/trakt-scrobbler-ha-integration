"""The Trakt Scrobbler integration."""

from datetime import datetime, timedelta, timezone
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import Platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_DRY_RUN,
    ATTR_START_DATE,
    CONF_AUTO_SYNC_HISTORY,
    CONF_AUTO_SYNC_INTERVAL_HOURS,
    CONF_IMPORT_ON_SETUP,
    CONF_IMPORT_START_DATE,
    DEFAULT_AUTO_SYNC_INTERVAL_HOURS,
    DOMAIN,
    SERVICE_IMPORT_PLEX_HISTORY,
)
from .coordinator import TraktDataCoordinator
from .history_sync import HistorySync
from .options import enabled_groups
from .services_trakt import async_register_trakt_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SENSOR]

# Where the media_player platform registers its live entities so the service
# can reach their Plex + Trakt access.
DATA_ENTITIES = "entities"
# Key under which the data coordinator is stored per entry.
DATA_COORDINATOR = "coordinator"

IMPORT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_START_DATE): cv.datetime,
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
    }
)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_ENTITIES, {})
    hass.data[DOMAIN].setdefault(DATA_COORDINATOR, {})
    # Merge entry.data and entry.options
    config = {**entry.data, **entry.options}
    hass.data[DOMAIN][entry.entry_id] = config

    # Build the data coordinator for the enabled sensor groups and do a first
    # refresh before forwarding platforms so sensors have data on creation.
    coordinator = TraktDataCoordinator(hass, entry, enabled_groups(entry))
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = coordinator

    # Forward the setup to the platforms (media_player scrobbler + sensors)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up reload listener
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    _async_register_services(hass)
    async_register_trakt_services(hass)
    _async_setup_auto_sync(hass, entry, config)
    _async_maybe_import_on_setup(hass, entry, config)

    return True


def _async_maybe_import_on_setup(
    hass: core.HomeAssistant,
    entry: config_entries.ConfigEntry,
    config: dict,
) -> None:
    """Run a one-shot Plex history backfill if requested during setup.

    The request is stored on the entry; we consume it once (in the background)
    and then clear it so it never runs again on later restarts.
    """
    if not config.get(CONF_IMPORT_ON_SETUP):
        return

    start_raw = config.get(CONF_IMPORT_START_DATE)

    async def _run_import() -> None:
        entities = list(hass.data.get(DOMAIN, {}).get(DATA_ENTITIES, {}).values())
        if not entities:
            return
        # Empty date means "all available history".
        if start_raw:
            start = datetime.fromisoformat(start_raw)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        else:
            start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        summary = await HistorySync(entities[0]).async_import(start, dry_run=False)
        _LOGGER.info("Initial Plex history import finished: %s", summary)

    # Clear the one-shot flags so this doesn't repeat on the next restart.
    new_data = dict(entry.data)
    new_data.pop(CONF_IMPORT_ON_SETUP, None)
    new_data.pop(CONF_IMPORT_START_DATE, None)
    hass.config_entries.async_update_entry(entry, data=new_data)

    hass.async_create_task(_run_import())


def _async_setup_auto_sync(
    hass: core.HomeAssistant,
    entry: config_entries.ConfigEntry,
    config: dict,
) -> None:
    """Schedule the periodic Plex-to-Trakt history sync when enabled."""
    if not config.get(CONF_AUTO_SYNC_HISTORY, False):
        return

    hours = config.get(
        CONF_AUTO_SYNC_INTERVAL_HOURS, DEFAULT_AUTO_SYNC_INTERVAL_HOURS
    )
    try:
        hours = max(1, int(hours))
    except (TypeError, ValueError):
        hours = DEFAULT_AUTO_SYNC_INTERVAL_HOURS

    async def _run_auto_sync(_now) -> None:
        entities = list(hass.data.get(DOMAIN, {}).get(DATA_ENTITIES, {}).values())
        if not entities:
            return
        summary = await HistorySync(entities[0]).async_auto_sync()
        _LOGGER.debug("Auto history sync finished: %s", summary)

    cancel = async_track_time_interval(
        hass, _run_auto_sync, timedelta(hours=hours)
    )
    entry.async_on_unload(cancel)
    _LOGGER.debug("Auto history sync scheduled every %d hour(s)", hours)


def _async_register_services(hass: core.HomeAssistant) -> None:
    """Register the Plex history import service (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_IMPORT_PLEX_HISTORY):
        return

    async def _handle_import(call: core.ServiceCall) -> None:
        entities = list(hass.data.get(DOMAIN, {}).get(DATA_ENTITIES, {}).values())
        if not entities:
            _LOGGER.error(
                "No Trakt Scrobbler entity available to run the history import"
            )
            return

        start_date = call.data.get(ATTR_START_DATE)
        if start_date is None:
            # Default: last 30 days if no date given (safe, small backfill).
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        elif start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        dry_run = call.data.get(ATTR_DRY_RUN, True)

        # Use the first entity (multi-instance households would target one each,
        # but a single import covers the shared Plex/Trakt account here).
        entity = entities[0]
        summary = await HistorySync(entity).async_import(start_date, dry_run=dry_run)
        _LOGGER.info("Plex history import finished: %s", summary)

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_PLEX_HISTORY,
        _handle_import,
        schema=IMPORT_HISTORY_SCHEMA,
    )


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    _LOGGER.debug("Options updated, reloading integration")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove config entry from domain
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].get(DATA_COORDINATOR, {}).pop(entry.entry_id, None)

    return unload_ok
