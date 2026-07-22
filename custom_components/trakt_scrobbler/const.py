"""Constants for the trakt_scrobbler integration."""

DOMAIN = "trakt_scrobbler"

# Configuration
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_MEDIA_PLAYERS = "media_players"
CONF_CHECK_ENTITY = "check_entity"
CONF_SCROBBLE_PERCENTAGE = "scrobble_percentage"
CONF_UPDATE_WATCHING = "update_watching"
CONF_PLEX_SERVER_URL = "plex_server_url"
CONF_PLEX_TOKEN = "plex_token"
CONF_DEBUG_MODE = "debug_mode"
CONF_AUTO_SYNC_HISTORY = "auto_sync_history"
CONF_AUTO_SYNC_INTERVAL_HOURS = "auto_sync_interval_hours"
CONF_PLEX_CLIENT_ID = "plex_client_id"
# Plex library section keys the user chose to import/scrobble from. Empty or
# missing means "all video libraries" (backward compatible).
CONF_PLEX_LIBRARIES = "plex_libraries"
# One-shot backfill requested during setup (consumed once, then cleared).
CONF_IMPORT_ON_SETUP = "import_on_setup"
CONF_IMPORT_START_DATE = "import_start_date"

# Plex authentication (PIN flow via plex.tv)
PLEX_PRODUCT = "Home Assistant Trakt Scrobbler"
PLEX_PINS_URL = "https://plex.tv/api/v2/pins"
PLEX_AUTH_APP_URL = "https://app.plex.tv/auth"

# OAuth URLs
OAUTH_AUTHORIZE_URL = "https://trakt.tv/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.trakt.tv/oauth/token"
OAUTH_REDIRECT_URI = "https://my.home-assistant.io/redirect/oauth"

# API Configuration
TRAKT_API_URL = "https://api.trakt.tv"
TRAKT_API_VERSION = "2"
TRAKT_APP_ID = "Home Assistant Trakt Scrobbler"

# Sensor data groups (each maps to a set of Trakt read endpoints and can be
# enabled/disabled independently in the options).
GROUP_UPCOMING = "upcoming"
GROUP_NEXT = "next_to_watch"
GROUP_WATCHLIST = "watchlist"
GROUP_STATS = "stats"
GROUP_RECO = "recommendations"

# Default polling interval for the data coordinator (hours).
DEFAULT_SCAN_INTERVAL_HOURS = 3

# Options that enable/disable each sensor group (added to the options flow in a
# later story). Defaults: the two headline groups on, the rest off, so users
# aren't flooded with entities they didn't ask for.
CONF_ENABLE_UPCOMING = "enable_upcoming"
CONF_ENABLE_NEXT = "enable_next_to_watch"
CONF_ENABLE_WATCHLIST = "enable_watchlist"
CONF_ENABLE_STATS = "enable_stats"
CONF_ENABLE_RECO = "enable_recommendations"
CONF_UPCOMING_DAYS = "upcoming_days"

DEFAULT_ENABLE_UPCOMING = True
DEFAULT_ENABLE_NEXT = True
DEFAULT_ENABLE_WATCHLIST = False
DEFAULT_ENABLE_STATS = False
DEFAULT_ENABLE_RECO = False
DEFAULT_UPCOMING_DAYS = 30

# Where users can create/manage their own Trakt API app (advanced mode).
TRAKT_APPS_URL = "https://app.trakt.tv/settings/apps/api/new"

# Built-in Trakt app credentials so users don't have to create their own app.
# For the OAuth device flow these are shipped with the client by design; Trakt
# treats them as public identifiers for a distributed application, not secrets.
# TODO: fill these in with the integration's own Trakt application before release.
TRAKT_BUILTIN_CLIENT_ID = "abDhseoq2ze4ROIPOS7RsVH-w1odJVz6FoVZnV3pXic"
TRAKT_BUILTIN_CLIENT_SECRET = "BALzkBPJGTnTbNDrBUScURR2kYQvyeIb_9V_Psjanw4"

# API Endpoints
SCROBBLE_START = "/scrobble/start"
SCROBBLE_PAUSE = "/scrobble/pause" 
SCROBBLE_STOP = "/scrobble/stop"
SEARCH = "/search/{type}"
HISTORY = "/sync/history/{type}"
SYNC_HISTORY = "/sync/history"

# Service: import Plex watch history into Trakt (backfill)
SERVICE_IMPORT_PLEX_HISTORY = "import_plex_history"
ATTR_START_DATE = "start_date"
ATTR_DRY_RUN = "dry_run"

# Batch size for pushing items to /sync/history
HISTORY_BATCH_SIZE = 100
# Storage key that remembers the last synced watch date (for auto-sync)
STORAGE_KEY_LAST_SYNC = "last_history_sync"

# Defaults
DEFAULT_SCROBBLE_PERCENTAGE = 80
DEFAULT_UPDATE_WATCHING = True
DEFAULT_DEBUG_MODE = False
DEFAULT_AUTO_SYNC_HISTORY = False
DEFAULT_AUTO_SYNC_INTERVAL_HOURS = 6
MIN_DURATION_SECONDS = 300  # 5 minutes for movies
MIN_EPISODE_DURATION_SECONDS = 60  # 1 minute for episodes (Bref, Kaamelott, etc.)

# Attributes
ATTR_TRAKT_ID = "trakt_id"
ATTR_TMDB_ID = "tmdb_id"
ATTR_IMDB_ID = "imdb_id"
ATTR_TVDB_ID = "tvdb_id"
ATTR_MEDIA_TYPE = "media_type"
ATTR_SHOW_NAME = "show_name"
ATTR_SEASON = "season"
ATTR_EPISODE = "episode"
ATTR_YEAR = "year"
ATTR_PROGRESS = "progress"

# Media Types
MEDIA_TYPE_MOVIE = "movie"
MEDIA_TYPE_EPISODE = "episode"