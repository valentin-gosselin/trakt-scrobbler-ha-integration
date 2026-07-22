"""Upcoming Media Card (UMC) formatting helpers.

Builds the `data` attribute structure expected by the popular
`custom:upcoming-media-card`, so our sensors are a drop-in replacement for the
separate `sensor.trakt` integration.
"""

from __future__ import annotations


def _image_url(images: dict | None, kind: str) -> str:
    """Return the first https image url of a kind from a Trakt images object."""
    if not images:
        return ""
    urls = images.get(kind) or []
    if not urls:
        return ""
    url = urls[0]
    # Trakt returns host-relative urls like "media.trakt.tv/...".
    if url.startswith("http"):
        return url
    return f"https://{url}"


def umc_header(title_default: str = "$title") -> dict:
    """First element of the UMC data array: default field mapping."""
    return {
        "title_default": title_default,
        "line1_default": "$episode",
        "line2_default": "$release",
        "line3_default": "$number - $rating - $runtime",
        "line4_default": "$genres",
        "icon": "mdi:arrow-down-bold",
    }


def show_calendar_to_umc(entry: dict) -> dict:
    """Map one Trakt 'my shows' calendar entry to a UMC item."""
    show = entry.get("show") or {}
    episode = entry.get("episode") or {}
    season = episode.get("season")
    number = episode.get("number")
    return {
        "title": show.get("title"),
        "episode": episode.get("title"),
        "number": f"S{season:02d}E{number:02d}"
        if season is not None and number is not None
        else "",
        "airdate": entry.get("first_aired"),
        "release": entry.get("first_aired"),
        "poster": _image_url(show.get("images"), "poster"),
        "fanart": _image_url(show.get("images"), "fanart"),
        "rating": show.get("rating"),
        "runtime": episode.get("runtime"),
        "genres": ", ".join(show.get("genres") or []),
        "deep_link": _trakt_link("show", show.get("ids")),
    }


def movie_calendar_to_umc(entry: dict) -> dict:
    """Map one Trakt 'my movies' calendar entry to a UMC item."""
    movie = entry.get("movie") or {}
    return {
        "title": movie.get("title"),
        "episode": "",
        "airdate": entry.get("released"),
        "release": entry.get("released"),
        "poster": _image_url(movie.get("images"), "poster"),
        "fanart": _image_url(movie.get("images"), "fanart"),
        "rating": movie.get("rating"),
        "runtime": movie.get("runtime"),
        "genres": ", ".join(movie.get("genres") or []),
        "deep_link": _trakt_link("movie", movie.get("ids")),
    }


def _trakt_link(kind: str, ids: dict | None) -> str:
    """Build a trakt.tv link for a show/movie from its ids."""
    if not ids:
        return ""
    slug = ids.get("slug") or ids.get("trakt")
    if not slug:
        return ""
    return f"https://trakt.tv/{kind}s/{slug}"
