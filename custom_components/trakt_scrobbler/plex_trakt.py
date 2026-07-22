"""Shared Plex-to-Trakt mapping helpers.

These are used by both the real-time scrobbler and the history backfill so the
two paths resolve ids and search Trakt the same way and don't drift apart.
"""

from __future__ import annotations

from urllib.parse import quote


def ids_from_plex_guids(guids) -> dict:
    """Extract imdb/tmdb/tvdb ids from a list of Plex guid objects.

    Accepts the guid objects Plex exposes (each with an `.id` like
    "imdb://tt123"). Returns a dict with only the id kinds Trakt understands.
    """
    ids: dict = {}
    for guid in guids or []:
        gid = getattr(guid, "id", "") or ""
        if gid.startswith("imdb://"):
            ids["imdb"] = gid.replace("imdb://", "")
        elif gid.startswith("tmdb://"):
            ids["tmdb"] = gid.replace("tmdb://", "")
        elif gid.startswith("tvdb://"):
            ids["tvdb"] = gid.replace("tvdb://", "")
    return ids


def only_trakt_ids(ids: dict | None) -> dict | None:
    """Keep only the id kinds Trakt matches on (trakt/imdb/tmdb/tvdb)."""
    if not ids:
        return None
    kept = {
        k: v for k, v in ids.items() if k in ("trakt", "imdb", "tmdb", "tvdb")
    }
    return kept or None


def search_endpoint(media_type: str, title: str) -> str:
    """Build the Trakt search endpoint for a show/movie title (top result)."""
    return f"/search/{media_type}?query={quote(title)}&limit=1"


def ids_from_search_result(result, media_type: str) -> dict | None:
    """Extract Trakt ids from a /search response for the given media type."""
    if isinstance(result, list) and result:
        obj = result[0].get(media_type, {}) or {}
        return only_trakt_ids(obj.get("ids"))
    return None
