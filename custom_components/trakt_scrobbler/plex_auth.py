"""Plex account authentication via the plex.tv PIN flow.

Instead of asking the user to paste an X-Plex-Token (which expires and is
awkward to find), this obtains a durable account token through the standard
Plex PIN flow: generate a PIN, send the user to app.plex.tv to authorize it,
then exchange the claimed PIN for the account token. The token is then used to
discover the user's Plex servers.
"""

from __future__ import annotations

import logging
from urllib.parse import quote, urlencode

import aiohttp

from .const import PLEX_AUTH_APP_URL, PLEX_PINS_URL, PLEX_PRODUCT

_LOGGER = logging.getLogger(__name__)


async def async_create_pin(client_id: str) -> dict | None:
    """Create a strong Plex PIN. Returns {'id', 'code'} or None on failure."""
    headers = {"accept": "application/json"}
    data = {
        "strong": "true",
        "X-Plex-Product": PLEX_PRODUCT,
        "X-Plex-Client-Identifier": client_id,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(PLEX_PINS_URL, headers=headers, data=data) as resp:
            if resp.status not in (200, 201):
                _LOGGER.error("Plex PIN creation failed: %s", resp.status)
                return None
            body = await resp.json()
            return {"id": body.get("id"), "code": body.get("code")}


def build_auth_url(client_id: str, code: str, forward_url: str | None = None) -> str:
    """Build the app.plex.tv URL the user visits to authorize the PIN."""
    params = {
        "clientID": client_id,
        "code": code,
        "context[device][product]": PLEX_PRODUCT,
    }
    if forward_url:
        params["forwardUrl"] = forward_url
    # Auth App params live in the URL fragment (after '#?'). Encode spaces as
    # %20 (quote) rather than '+' to match Plex's documented example.
    return f"{PLEX_AUTH_APP_URL}#?{urlencode(params, quote_via=quote)}"


async def async_check_pin(pin_id: int, client_id: str) -> str | None:
    """Return the account auth token once the PIN is claimed, else None."""
    headers = {"accept": "application/json"}
    data = {"X-Plex-Client-Identifier": client_id}
    url = f"{PLEX_PINS_URL}/{pin_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, data=data) as resp:
            if resp.status != 200:
                _LOGGER.debug("Plex PIN check status: %s", resp.status)
                return None
            body = await resp.json()
            return body.get("authToken")


def discover_servers(token: str) -> list[dict]:
    """Return the user's Plex Media Servers as [{'name', 'url'}].

    Runs plexapi (synchronous) - call via async_add_executor_job. Prefers a
    local/direct connection URI when available, otherwise the first reachable
    connection reported by plex.tv.
    """
    from plexapi.myplex import MyPlexAccount

    account = MyPlexAccount(token=token)
    servers: list[dict] = []
    for resource in account.resources():
        # Only real media servers, owned by the user.
        if "server" not in (resource.provides or ""):
            continue
        connections = getattr(resource, "connections", []) or []
        # Prefer a local connection, fall back to any.
        local = next((c for c in connections if getattr(c, "local", False)), None)
        chosen = local or (connections[0] if connections else None)
        if chosen is None:
            continue
        servers.append({"name": resource.name, "url": chosen.uri})
    return servers
