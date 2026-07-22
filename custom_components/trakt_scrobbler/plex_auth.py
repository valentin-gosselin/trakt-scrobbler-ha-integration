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
    import socket
    from urllib.parse import urlparse

    from plexapi.myplex import MyPlexAccount

    def _responds(uri: str, timeout: float = 2.0) -> bool:
        """Quick TCP check that something is actually listening at the uri."""
        parsed = urlparse(uri)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    account = MyPlexAccount(token=token)
    servers: list[dict] = []
    for resource in account.resources():
        # Only real media servers, owned by the user.
        if "server" not in (resource.provides or ""):
            continue
        connections = getattr(resource, "connections", []) or []
        if not connections:
            continue

        # Order candidates: local connections first, then the rest.
        ordered = sorted(
            connections, key=lambda c: not getattr(c, "local", False)
        )
        # Pick the first connection that actually responds; if none do, fall
        # back to the first candidate but mark the server as unreachable so the
        # user isn't silently pointed at a dead server.
        reachable_uri = next((c.uri for c in ordered if _responds(c.uri)), None)
        chosen_uri = reachable_uri or ordered[0].uri
        servers.append(
            {
                "name": resource.name,
                "url": chosen_uri,
                "reachable": reachable_uri is not None,
            }
        )

    # Show reachable servers first so the default selection is a working one.
    servers.sort(key=lambda s: not s["reachable"])
    return servers


def list_libraries(server_url: str, token: str) -> list[dict]:
    """List the movie/show libraries of a Plex server.

    Returns [{'key', 'title', 'type'}]. Runs plexapi (synchronous) - call via
    async_add_executor_job. Only video libraries are returned, since music and
    photo sections are never scrobbled to Trakt.
    """
    from plexapi.server import PlexServer

    plex = PlexServer(server_url, token)
    libraries: list[dict] = []
    for section in plex.library.sections():
        if section.type not in ("movie", "show"):
            continue
        libraries.append(
            {
                "key": str(section.key),
                "title": section.title,
                "type": section.type,
            }
        )
    return libraries
