"""Config flow for trakt_scrobbler integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
import uuid

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    DateTimeSelector,
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
)

from . import plex_auth

from .const import (
    CONF_AUTO_SYNC_HISTORY,
    CONF_AUTO_SYNC_INTERVAL_HOURS,
    CONF_CHECK_ENTITY,
    CONF_IMPORT_ON_SETUP,
    CONF_IMPORT_START_DATE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MEDIA_PLAYERS,
    CONF_PLEX_CLIENT_ID,
    CONF_PLEX_SERVER_URL,
    CONF_PLEX_TOKEN,
    CONF_SCROBBLE_PERCENTAGE,
    CONF_UPDATE_WATCHING,
    DEFAULT_AUTO_SYNC_HISTORY,
    DEFAULT_AUTO_SYNC_INTERVAL_HOURS,
    DEFAULT_SCROBBLE_PERCENTAGE,
    DEFAULT_UPDATE_WATCHING,
    DOMAIN,
    TRAKT_API_URL,
    TRAKT_APPS_URL,
    TRAKT_BUILTIN_CLIENT_ID,
    TRAKT_BUILTIN_CLIENT_SECRET,
)

_LOGGER = logging.getLogger(__name__)


class TraktScrobblerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trakt Scrobbler."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}
        self._device_info = None
        self._errors = {}
        self._plex_pin_id = None
        self._plex_auth_url = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step.

        If the integration ships built-in Trakt app credentials, the user
        doesn't create their own app: we go straight to authorization. If not
        (or in advanced setups), fall back to asking for client credentials.
        """
        errors: dict[str, str] = {}

        # Fast path: built-in app credentials, nothing for the user to enter.
        if TRAKT_BUILTIN_CLIENT_ID and TRAKT_BUILTIN_CLIENT_SECRET:
            self._data[CONF_CLIENT_ID] = TRAKT_BUILTIN_CLIENT_ID
            self._data[CONF_CLIENT_SECRET] = TRAKT_BUILTIN_CLIENT_SECRET
            try:
                await self._get_device_code()
                return await self.async_step_device()
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Error getting device code: %s", e)
                # Fall through to manual entry so setup isn't fully blocked.
                errors["base"] = "device_code_failed"

        if user_input is not None:
            self._data[CONF_CLIENT_ID] = user_input[CONF_CLIENT_ID]
            self._data[CONF_CLIENT_SECRET] = user_input[CONF_CLIENT_SECRET]

            try:
                # Get device code from Trakt
                await self._get_device_code()
                return await self.async_step_device()
            except Exception as e:
                _LOGGER.error("Error getting device code: %s", e)
                errors["base"] = "device_code_failed"

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "trakt_app_url": TRAKT_APPS_URL,
            },
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device code activation."""
        if user_input is not None:
            # Poll for token
            token_data = await self._poll_token()
            if token_data:
                self._data.update({
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data.get("refresh_token"),
                    "created_at": token_data.get("created_at"),
                    "expires_in": token_data.get("expires_in"),
                })
                return await self.async_step_options()
            else:
                return self.async_abort(reason="token_poll_failed")

        if not self._device_info:
            return self.async_abort(reason="no_device_info")

        verification_url = self._device_info.get("verification_url", "https://trakt.tv/activate")
        user_code = self._device_info.get("user_code", "XXXX-XXXX")

        return self.async_show_form(
            step_id="device",
            description_placeholders={
                "verification_url": verification_url,
                "user_code": user_code,
            },
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store all configuration
            self._data.update(user_input)

            # Check if all optional fields have default values
            self._data.setdefault(CONF_CHECK_ENTITY, [])

            # Move on to the optional Plex connection step.
            return await self.async_step_plex_ask()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Trakt Scrobbler"): str,
                vol.Required(
                    CONF_SCROBBLE_PERCENTAGE, default=DEFAULT_SCROBBLE_PERCENTAGE
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Required(
                    CONF_UPDATE_WATCHING, default=DEFAULT_UPDATE_WATCHING
                ): bool,
                vol.Required(CONF_MEDIA_PLAYERS): EntitySelector(
                    EntitySelectorConfig(
                        filter=EntityFilterSelectorConfig(domain="media_player"),
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_CHECK_ENTITY, default=[]): EntitySelector(
                    EntitySelectorConfig(
                        filter=EntityFilterSelectorConfig(
                            domain=["person", "input_boolean", "switch"]
                        ),
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="options", data_schema=schema, errors=errors
        )

    async def async_step_plex_ask(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask whether to connect a Plex account (optional)."""
        if user_input is not None:
            if user_input.get("connect_plex"):
                return await self.async_step_plex_pin()
            # Skip Plex entirely and finish.
            return self._create_entry()

        schema = vol.Schema({vol.Required("connect_plex", default=False): bool})
        return self.async_show_form(step_id="plex_ask", data_schema=schema)

    async def async_step_plex_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Generate a Plex PIN and wait for the user to authorize it."""
        # Stable client identifier for this integration instance.
        if not self._data.get(CONF_PLEX_CLIENT_ID):
            self._data[CONF_PLEX_CLIENT_ID] = str(uuid.uuid4())
        client_id = self._data[CONF_PLEX_CLIENT_ID]

        if user_input is not None:
            # User clicked submit after authorizing: check the PIN.
            token = await plex_auth.async_check_pin(self._plex_pin_id, client_id)
            if not token:
                return self.async_show_form(
                    step_id="plex_pin",
                    errors={"base": "plex_not_authorized"},
                    description_placeholders={"auth_url": self._plex_auth_url},
                )
            self._data[CONF_PLEX_TOKEN] = token
            return await self.async_step_plex_server()

        pin = await plex_auth.async_create_pin(client_id)
        if not pin or not pin.get("code"):
            return self.async_abort(reason="plex_pin_failed")
        self._plex_pin_id = pin["id"]
        self._plex_auth_url = plex_auth.build_auth_url(client_id, pin["code"])

        return self.async_show_form(
            step_id="plex_pin",
            description_placeholders={"auth_url": self._plex_auth_url},
        )

    async def async_step_plex_server(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Discover the user's Plex servers and let them pick one."""
        token = self._data[CONF_PLEX_TOKEN]

        if user_input is not None:
            self._data[CONF_PLEX_SERVER_URL] = user_input[CONF_PLEX_SERVER_URL]
            return await self.async_step_import_ask()

        try:
            servers = await self.hass.async_add_executor_job(
                plex_auth.discover_servers, token
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to discover Plex servers: %s", err)
            servers = []

        if not servers:
            # Authenticated but no server found: finish without a server URL.
            return self._create_entry()

        options = {s["url"]: f"{s['name']} ({s['url']})" for s in servers}
        schema = vol.Schema(
            {vol.Required(CONF_PLEX_SERVER_URL): vol.In(options)}
        )
        return self.async_show_form(step_id="plex_server", data_schema=schema)

    async def async_step_import_ask(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Offer to backfill Plex watch history into Trakt right after setup."""
        if user_input is not None:
            if user_input.get(CONF_IMPORT_ON_SETUP):
                # Stored in the entry; async_setup_entry runs the backfill once
                # in the background, then clears these keys.
                self._data[CONF_IMPORT_ON_SETUP] = True
                start = user_input.get(CONF_IMPORT_START_DATE)
                self._data[CONF_IMPORT_START_DATE] = (
                    start.isoformat() if start else None
                )
            return self._create_entry()

        schema = vol.Schema(
            {
                vol.Required(CONF_IMPORT_ON_SETUP, default=False): bool,
                vol.Optional(CONF_IMPORT_START_DATE): DateTimeSelector(),
            }
        )
        return self.async_show_form(step_id="import_ask", data_schema=schema)

    def _create_entry(self) -> FlowResult:
        """Create the config entry with a unique title."""
        existing_entries = self._async_current_entries()
        if existing_entries:
            count = len(existing_entries) + 1
            title = f"{self._data[CONF_NAME]} {count}"
        else:
            title = self._data[CONF_NAME]
        return self.async_create_entry(title=title, data=self._data)

    async def _get_device_code(self):
        """Get device code from Trakt API."""
        url = f"{TRAKT_API_URL}/oauth/device/code"
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self._data[CONF_CLIENT_ID],
        }
        payload = {"client_id": self._data[CONF_CLIENT_ID]}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise ValueError(f"Device code error {resp.status}: {text}")
                self._device_info = await resp.json()
                _LOGGER.debug("Device info: %s", self._device_info)

    async def _poll_token(self):
        """Poll for access token."""
        url = f"{TRAKT_API_URL}/oauth/device/token"
        headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
        }
        payload = {
            "client_id": self._data[CONF_CLIENT_ID],
            "client_secret": self._data[CONF_CLIENT_SECRET],
            "code": self._device_info["device_code"],
        }
        
        # Poll for the token
        interval = self._device_info.get("interval", 5)
        expires_in = self._device_info.get("expires_in", 600)
        
        for _ in range(int(expires_in / interval)):
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 400:
                        error = await resp.json()
                        if error.get("error") == "authorization_pending":
                            await asyncio.sleep(interval)
                            continue
                    else:
                        _LOGGER.warning("Token poll failed: %s", resp.status)
                        return None
        
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        # Note: self.config_entry is automatically set by Home Assistant
        # Explicit assignment is deprecated as of HA 2025.12

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Check if all optional fields have default values
            user_input.setdefault(CONF_CHECK_ENTITY, [])
            
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCROBBLE_PERCENTAGE,
                    default=self.config_entry.options.get(
                        CONF_SCROBBLE_PERCENTAGE, 
                        self.config_entry.data.get(CONF_SCROBBLE_PERCENTAGE, DEFAULT_SCROBBLE_PERCENTAGE)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Required(
                    CONF_UPDATE_WATCHING,
                    default=self.config_entry.options.get(
                        CONF_UPDATE_WATCHING,
                        self.config_entry.data.get(CONF_UPDATE_WATCHING, DEFAULT_UPDATE_WATCHING)
                    ),
                ): bool,
                vol.Required(
                    CONF_MEDIA_PLAYERS,
                    default=self.config_entry.options.get(
                        CONF_MEDIA_PLAYERS,
                        self.config_entry.data.get(CONF_MEDIA_PLAYERS, [])
                    ),
                ): EntitySelector(
                    EntitySelectorConfig(
                        filter=EntityFilterSelectorConfig(domain="media_player"),
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_CHECK_ENTITY,
                    default=self.config_entry.options.get(
                        CONF_CHECK_ENTITY,
                        self.config_entry.data.get(CONF_CHECK_ENTITY, [])
                    ),
                ): EntitySelector(
                    EntitySelectorConfig(
                        filter=EntityFilterSelectorConfig(
                            domain=["person", "input_boolean", "switch"]
                        ),
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_PLEX_SERVER_URL,
                    default=self.config_entry.options.get(
                        CONF_PLEX_SERVER_URL,
                        self.config_entry.data.get(CONF_PLEX_SERVER_URL, "")
                    ),
                ): str,
                vol.Optional(
                    CONF_PLEX_TOKEN,
                    default=self.config_entry.options.get(
                        CONF_PLEX_TOKEN,
                        self.config_entry.data.get(CONF_PLEX_TOKEN, "")
                    ),
                ): str,
                vol.Required(
                    CONF_AUTO_SYNC_HISTORY,
                    default=self.config_entry.options.get(
                        CONF_AUTO_SYNC_HISTORY,
                        self.config_entry.data.get(
                            CONF_AUTO_SYNC_HISTORY, DEFAULT_AUTO_SYNC_HISTORY
                        ),
                    ),
                ): bool,
                vol.Required(
                    CONF_AUTO_SYNC_INTERVAL_HOURS,
                    default=self.config_entry.options.get(
                        CONF_AUTO_SYNC_INTERVAL_HOURS,
                        self.config_entry.data.get(
                            CONF_AUTO_SYNC_INTERVAL_HOURS,
                            DEFAULT_AUTO_SYNC_INTERVAL_HOURS,
                        ),
                    ),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)