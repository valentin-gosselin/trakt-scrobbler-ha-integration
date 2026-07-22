"""Serve and auto-register the integration's Lovelace card.

Registers a static HTTP path for the card JS and adds it as a Lovelace module
resource (storage mode), so users don't have to install anything. Everything is
guarded so a failure here never blocks integration setup.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import CARD_FILENAME, CARD_URL_BASE, CARD_VERSION

_LOGGER = logging.getLogger(__name__)

_CARD_URL = f"{CARD_URL_BASE}/{CARD_FILENAME}"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card file and register it as a Lovelace resource (once)."""
    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_URL_BASE, str(Path(__file__).parent), False
                )
            ]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not register static path for the card: %s", err)
        return

    await _async_register_resource(hass)


async def _async_register_resource(hass: HomeAssistant) -> None:
    """Add the card JS as a Lovelace module resource if not already present."""
    url = f"{_CARD_URL}?v={CARD_VERSION}"
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None:
            # Not in storage mode: fall back to injecting the JS url directly.
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, url)
            return

        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True

        # Skip if a resource for this card is already registered (any version).
        for item in resources.async_items():
            if item.get("url", "").startswith(_CARD_URL):
                return

        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.debug("Registered Trakt card resource: %s", url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Could not register the card as a resource: %s", err)
