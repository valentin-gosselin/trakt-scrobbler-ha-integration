"""Helpers for reading the integration's sensor-group options.

Centralized so __init__, the coordinator and the sensor platform all agree on
which sensor groups are enabled. Group toggles are added to the options flow in
a later story; until then sensible defaults apply.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ENABLE_NEXT,
    CONF_ENABLE_RECO,
    CONF_ENABLE_STATS,
    CONF_ENABLE_UPCOMING,
    CONF_ENABLE_WATCHLIST,
    DEFAULT_ENABLE_NEXT,
    DEFAULT_ENABLE_RECO,
    DEFAULT_ENABLE_STATS,
    DEFAULT_ENABLE_UPCOMING,
    DEFAULT_ENABLE_WATCHLIST,
    GROUP_NEXT,
    GROUP_RECO,
    GROUP_STATS,
    GROUP_UPCOMING,
    GROUP_WATCHLIST,
)

# Map each group to its option key and default.
_GROUP_OPTIONS = {
    GROUP_UPCOMING: (CONF_ENABLE_UPCOMING, DEFAULT_ENABLE_UPCOMING),
    GROUP_NEXT: (CONF_ENABLE_NEXT, DEFAULT_ENABLE_NEXT),
    GROUP_WATCHLIST: (CONF_ENABLE_WATCHLIST, DEFAULT_ENABLE_WATCHLIST),
    GROUP_STATS: (CONF_ENABLE_STATS, DEFAULT_ENABLE_STATS),
    GROUP_RECO: (CONF_ENABLE_RECO, DEFAULT_ENABLE_RECO),
}


def enabled_groups(entry: ConfigEntry) -> set[str]:
    """Return the set of enabled sensor groups for a config entry."""
    config = {**entry.data, **entry.options}
    groups: set[str] = set()
    for group, (conf_key, default) in _GROUP_OPTIONS.items():
        if config.get(conf_key, default):
            groups.add(group)
    return groups
