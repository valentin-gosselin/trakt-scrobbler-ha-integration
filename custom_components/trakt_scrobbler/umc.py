"""Upcoming Media Card (UMC) formatting helpers.

Builds the `data` attribute structure expected by the popular
`custom:upcoming-media-card`, so our sensors are a drop-in replacement for the
separate `sensor.trakt` integration.
"""

from __future__ import annotations

import homeassistant.util.dt as dt_util


def _to_local(iso: str | None) -> str:
    """Convert a Trakt ISO 8601 UTC timestamp to a local, readable string.

    Uses day/month/year and the Home Assistant time zone (e.g.
    '24/07/2026 03:00'). Falls back to the original value if it can't be parsed.
    """
    if not iso:
        return ""
    parsed = dt_util.parse_datetime(iso)
    if parsed is None:
        return iso
    return dt_util.as_local(parsed).strftime("%d/%m/%Y %H:%M")


def _ids(obj: dict | None) -> dict:
    """Keep only the id kinds Trakt matches on, as strings for the card."""
    ids = (obj or {}).get("ids") or {}
    return {
        k: str(ids[k]) for k in ("trakt", "imdb", "tmdb", "tvdb") if ids.get(k)
    }


def _round1(value) -> str:
    """Round a Trakt rating to one decimal for display; '' if missing."""
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return ""


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
    """First element of the UMC data array: default field mapping.

    Lines shown by the Upcoming Media Card, kept simple and readable:
    - line1: episode title
    - line2: air date/time (localized)
    - line3: SxxExx and the rating
    - line4: genres
    """
    return {
        "title_default": title_default,
        "line1_default": "$episode",
        "line2_default": "$release",
        "line3_default": "$number - $rating",
        "line4_default": "$genres",
        "icon": "mdi:arrow-down-bold",
    }


def umc_data(items: list, empty_message: str = "Nothing here") -> list:
    """Wrap UMC items with the header, or a placeholder when the list is empty.

    The Upcoming Media Card shows a loading bar when it only gets the header
    with no items, so we add a single placeholder item for empty states. The
    placeholder is flagged so our own card can localize it and hide actions.
    """
    if not items:
        return [umc_header(), {"title": empty_message, "airdate": "", "empty": True}]
    return [umc_header(), *items]


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
        "release": _to_local(entry.get("first_aired")),
        "poster": _image_url(show.get("images"), "poster"),
        "fanart": _image_url(show.get("images"), "fanart"),
        "rating": _round1(show.get("rating")),
        "runtime": episode.get("runtime"),
        "genres": ", ".join(show.get("genres") or []),
        "deep_link": _trakt_link("show", show.get("ids")),
        "ids": _ids(show),
        "season": season,
        "number_int": number,
    }


def movie_calendar_to_umc(entry: dict) -> dict:
    """Map one Trakt 'my movies' calendar entry to a UMC item."""
    movie = entry.get("movie") or {}
    return {
        "title": movie.get("title"),
        "episode": "",
        "airdate": entry.get("released"),
        "release": _to_local(entry.get("released")),
        "poster": _image_url(movie.get("images"), "poster"),
        "fanart": _image_url(movie.get("images"), "fanart"),
        "rating": _round1(movie.get("rating")),
        "runtime": movie.get("runtime"),
        "genres": ", ".join(movie.get("genres") or []),
        "deep_link": _trakt_link("movie", movie.get("ids")),
        "ids": _ids(movie),
    }


def next_to_watch_to_umc(entry: dict) -> dict:
    """Map a next-to-watch entry (show + next_episode) to a UMC item."""
    show = entry.get("show") or {}
    ep = entry.get("next_episode") or {}
    season = ep.get("season")
    number = ep.get("number")
    return {
        "title": show.get("title"),
        "episode": ep.get("title"),
        "number": f"S{season:02d}E{number:02d}"
        if season is not None and number is not None
        else "",
        "airdate": ep.get("first_aired"),
        "release": _to_local(ep.get("first_aired")),
        "poster": _image_url(show.get("images"), "poster"),
        "fanart": _image_url(show.get("images"), "fanart"),
        "rating": _round1(show.get("rating")),
        "genres": ", ".join(show.get("genres") or []),
        "deep_link": _trakt_link("show", show.get("ids")),
        "ids": _ids(show),
        "season": season,
        "number_int": number,
    }


def recommendation_to_umc(obj: dict, kind: str) -> dict:
    """Map a recommended show/movie object to a UMC item."""
    year = obj.get("year")
    return {
        "title": obj.get("title"),
        "episode": str(year) if year else "",
        "airdate": "",
        "release": str(year) if year else "",
        "poster": _image_url(obj.get("images"), "poster"),
        "fanart": _image_url(obj.get("images"), "fanart"),
        "rating": _round1(obj.get("rating")),
        "genres": ", ".join(obj.get("genres") or []),
        "deep_link": _trakt_link(kind[:-1] if kind.endswith("s") else kind, obj.get("ids")),
        "ids": _ids(obj),
    }


def _trakt_link(kind: str, ids: dict | None) -> str:
    """Build a trakt.tv link for a show/movie from its ids."""
    if not ids:
        return ""
    slug = ids.get("slug") or ids.get("trakt")
    if not slug:
        return ""
    return f"https://trakt.tv/{kind}s/{slug}"
