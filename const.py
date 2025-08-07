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

# OAuth URLs
OAUTH_AUTHORIZE_URL = "https://trakt.tv/oauth/authorize"
OAUTH_TOKEN_URL = "https://api.trakt.tv/oauth/token"
OAUTH_REDIRECT_URI = "https://my.home-assistant.io/redirect/oauth"

# API Configuration  
TRAKT_API_URL = "https://api.trakt.tv"
TRAKT_API_VERSION = "2"
TRAKT_APP_ID = "Home Assistant Trakt Scrobbler"

# API Endpoints
SCROBBLE_START = "/scrobble/start"
SCROBBLE_PAUSE = "/scrobble/pause" 
SCROBBLE_STOP = "/scrobble/stop"
SEARCH = "/search/{type}"
HISTORY = "/sync/history/{type}"

# Defaults
DEFAULT_SCROBBLE_PERCENTAGE = 80
DEFAULT_UPDATE_WATCHING = True
DEFAULT_DEBUG_MODE = False
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