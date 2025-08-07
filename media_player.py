"""Trakt Scrobbler media_player platform."""

from datetime import datetime, timedelta
import logging
import time
from typing import Any

import aiohttp

from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.const import CONF_NAME, STATE_PLAYING, STATE_PAUSED
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PLEX_SERVER_URL,
    CONF_PLEX_TOKEN,
    ATTR_EPISODE,
    ATTR_IMDB_ID,
    ATTR_MEDIA_TYPE,
    ATTR_PROGRESS,
    ATTR_SEASON,
    ATTR_SHOW_NAME,
    ATTR_TMDB_ID,
    ATTR_TRAKT_ID,
    ATTR_TVDB_ID,
    ATTR_YEAR,
    CONF_CHECK_ENTITY,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MEDIA_PLAYERS,
    CONF_SCROBBLE_PERCENTAGE,
    CONF_UPDATE_WATCHING,
    DOMAIN,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MIN_DURATION_SECONDS,
    MIN_EPISODE_DURATION_SECONDS,
    SCROBBLE_PAUSE,
    SCROBBLE_START,
    SCROBBLE_STOP,
    TRAKT_API_URL,
    TRAKT_API_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Trakt Scrobbler from a config entry."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    
    name = config.get(CONF_NAME, "Trakt Scrobbler")
    media_players = config.get(CONF_MEDIA_PLAYERS, [])
    check_entities = config.get(CONF_CHECK_ENTITY, [])
    scrobble_percentage = config.get(CONF_SCROBBLE_PERCENTAGE, 80)
    update_watching = config.get(CONF_UPDATE_WATCHING, True)
    
    # Setup Trakt API
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    access_token = config.get("access_token")
    refresh_token = config.get("refresh_token")
    
    # Setup Plex (optional)
    plex_server_url = config.get(CONF_PLEX_SERVER_URL)
    plex_token = config.get(CONF_PLEX_TOKEN)
    
    async_add_entities(
        [
            TraktScrobblerMediaPlayer(
                hass,
                name,
                client_id,
                client_secret,
                access_token,
                refresh_token,
                media_players,
                check_entities,
                scrobble_percentage,
                update_watching,
                plex_server_url,
                plex_token,
            )
        ]
    )


class TraktScrobblerMediaPlayer(MediaPlayerEntity):
    """The Trakt Scrobbler entity."""

    def __init__(
        self,
        hass,
        name,
        client_id,
        client_secret,
        access_token,
        refresh_token,
        media_players,
        check_entities,
        scrobble_percentage,
        update_watching,
        plex_server_url,
        plex_token,
    ) -> None:
        """Initialize the Trakt scrobbler."""
        self.hass = hass
        self._name = name
        self._attr_unique_id = f"{DOMAIN}-{name}"
        self._state = None
        self._current_media = None
        self._media_type = None
        self._title = None
        self._show_name = None
        self._season = None
        self._episode = None
        self._year = None
        self._duration = None
        self._progress = None
        self._last_scrobbled = None
        self._watching_started = None
        self._is_watching = False
        
        # API Configuration
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        
        # Configuration
        self._media_players = media_players
        self._check_entities = check_entities
        self._scrobble_percentage = scrobble_percentage
        self._update_watching = update_watching
        
        # Plex Configuration (optional)
        self._plex_server_url = plex_server_url
        self._plex_token = plex_token
        self._plex_server = None
        
        # Initialize Plex if configured
        if self._plex_server_url and self._plex_token:
            try:
                from plexapi.server import PlexServer
                self._plex_server = PlexServer(self._plex_server_url, self._plex_token)
                _LOGGER.info("Plex server connected: %s", self._plex_server.friendlyName)
            except Exception as e:
                _LOGGER.warning("Failed to connect to Plex server: %s", e)
                self._plex_server = None
        
        # Headers for API calls
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "trakt-api-version": TRAKT_API_VERSION,
            "trakt-api-key": self._client_id,
        }

    def _handle_task_result(self, task):
        """Handle the result of an async task."""
        try:
            task.result()
        except Exception as e:
            _LOGGER.error("Error in async task: %s", e)

    def check_entities(self):
        """Check if all the given check_entities agree to scrobble."""
        for entity_id in self._check_entities:
            entity = self.hass.states.get(entity_id)
            if not entity:
                continue
                
            _LOGGER.debug("Checking %s", entity.entity_id)

            if entity.domain in ["input_boolean", "switch"]:
                if entity.state != "on":
                    _LOGGER.debug(
                        "%s is not on - preventing scrobbling", entity.entity_id
                    )
                    return False

            elif entity.domain == "person":
                if entity.state != "home":
                    _LOGGER.debug(
                        "%s is not home - preventing scrobbling", entity.entity_id
                    )
                    return False

        _LOGGER.debug("All entity checks passed - can scrobble")
        return True

    async def _api_request(self, endpoint: str, method: str = "POST", data: dict = None):
        """Make an API request to Trakt."""
        url = f"{TRAKT_API_URL}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method, url, headers=self._headers, json=data
                ) as resp:
                    if resp.status in [200, 201, 204]:
                        if resp.status != 204:
                            return await resp.json()
                        return True
                    else:
                        error = await resp.text()
                        _LOGGER.error(
                            "Trakt API error %s: %s", resp.status, error
                        )
                        return None
            except Exception as e:
                _LOGGER.error("Error calling Trakt API: %s", e)
                return None

    def _extract_media_info(self, player):
        """Extract media information from player attributes."""
        attrs = player.attributes
        
        # Debug logging
        _LOGGER.debug("Extracting media info from %s:", player.entity_id)
        _LOGGER.debug("  app_name: %s", attrs.get("app_name"))
        _LOGGER.debug("  media_content_type: %s", attrs.get("media_content_type"))
        _LOGGER.debug("  media_title: %s", attrs.get("media_title"))
        _LOGGER.debug("  media_series_title: %s", attrs.get("media_series_title"))
        _LOGGER.debug("  media_content_id: %s", attrs.get("media_content_id"))
        
        # Skip if it's YouTube or other non-scrobbleable content
        media_source = attrs.get("app_name", "").lower()
        media_content_id = attrs.get("media_content_id", "").lower()
        
        # List of sources to skip
        skip_sources = ["youtube", "spotify", "soundcloud", "twitch", "vimeo", "dailymotion"]
        if any(source in media_source for source in skip_sources):
            _LOGGER.debug("Skipping %s content", media_source)
            return None, None
            
        # Also skip if content_id looks like a YouTube URL
        if "youtube.com" in media_content_id or "youtu.be" in media_content_id:
            _LOGGER.debug("Skipping YouTube URL")
            return None, None
        
        # Try to detect media type
        media_type = None
        if attrs.get(ATTR_MEDIA_TYPE) in ["movie", "episode", "tvshow"]:
            media_type = MEDIA_TYPE_MOVIE if attrs.get(ATTR_MEDIA_TYPE) == "movie" else MEDIA_TYPE_EPISODE
        elif attrs.get("media_content_type") == "movie":
            media_type = MEDIA_TYPE_MOVIE
        elif attrs.get("media_content_type") in ["tvshow", "episode"]:
            media_type = MEDIA_TYPE_EPISODE
        elif attrs.get(ATTR_SEASON) is not None or attrs.get(ATTR_EPISODE) is not None:
            media_type = MEDIA_TYPE_EPISODE
        
        # Extract IDs
        ids = {}
        if attrs.get(ATTR_TRAKT_ID):
            ids["trakt"] = attrs.get(ATTR_TRAKT_ID)
        if attrs.get(ATTR_TMDB_ID):
            ids["tmdb"] = attrs.get(ATTR_TMDB_ID)
        if attrs.get(ATTR_IMDB_ID):
            ids["imdb"] = attrs.get(ATTR_IMDB_ID)
        if attrs.get(ATTR_TVDB_ID):
            ids["tvdb"] = attrs.get(ATTR_TVDB_ID)
        
        # Check if we have proper IDs OR if it's from a trusted source like Plex
        trusted_sources = ["plex", "jellyfin", "emby", "kodi"]
        is_trusted_source = any(source in media_source for source in trusted_sources)
        
        # Only scrobble if we have proper IDs OR it's from a trusted media server
        if not ids and not is_trusted_source:
            _LOGGER.debug("No IDs and not from trusted source (%s), skipping", media_source)
            return None, None
        
        # For trusted sources without IDs, we need at least a title and proper media type
        if not ids and is_trusted_source:
            title = attrs.get("media_title") or attrs.get("media_series_title")
            
            # Special handling for Plex when title is missing
            if not title and "plex" in media_source:
                # Try to extract from content_id or other attributes
                content_id = attrs.get("media_content_id", "")
                if "metadata" in content_id and self._plex_server:
                    _LOGGER.debug("Plex content detected but no title, need async metadata fetch")
                    # Return a special marker indicating we need async processing
                    return "PLEX_ASYNC_NEEDED", content_id
                elif not self._plex_server:
                    _LOGGER.debug("Plex content but no Plex server configured")
                    return None, None
            
            if not title or not media_type:
                _LOGGER.debug("Trusted source but missing title (%s) or media type (%s), skipping", title, media_type)
                return None, None
        
        # Build media object
        media_obj = {}
        
        if media_type == MEDIA_TYPE_MOVIE:
            media_obj["movie"] = {
                "title": attrs.get("media_title"),
                "year": attrs.get(ATTR_YEAR) or attrs.get("media_year"),
            }
            if ids:
                media_obj["movie"]["ids"] = ids
                
        elif media_type == MEDIA_TYPE_EPISODE:
            show_name = attrs.get(ATTR_SHOW_NAME) or attrs.get("media_series_title")
            season = attrs.get(ATTR_SEASON) or attrs.get("media_season")
            episode = attrs.get(ATTR_EPISODE) or attrs.get("media_episode")
            
            media_obj["show"] = {
                "title": show_name,
            }
            if ids:
                media_obj["show"]["ids"] = ids
                
            media_obj["episode"] = {
                "season": season,
                "number": episode,
            }
        
        return media_type, media_obj

    async def get_plex_metadata(self, content_id: str) -> dict | None:
        """Get metadata from Plex server using content_id."""
        if not self._plex_server:
            return None
            
        try:
            # Extract rating key from content_id
            # Format: server://xxx/com.plexapp.plugins.library/library/metadata/84303
            parts = content_id.split('/')
            if 'metadata' in parts:
                idx = parts.index('metadata')
                if idx + 1 < len(parts):
                    rating_key = parts[idx + 1]
                    
                    # Fetch metadata from Plex
                    _LOGGER.debug("Fetching Plex metadata for rating key: %s", rating_key)
                    
                    # Run in executor to avoid blocking
                    import asyncio
                    loop = asyncio.get_event_loop()
                    item = await loop.run_in_executor(
                        None, 
                        self._plex_server.fetchItem, 
                        int(rating_key)
                    )
                    
                    if item:
                        metadata = {}
                        
                        # Determine if it's a movie or episode
                        if item.type == 'movie':
                            metadata['media_title'] = item.title
                            metadata['media_content_type'] = 'movie'
                            if hasattr(item, 'year'):
                                metadata['year'] = item.year
                        elif item.type == 'episode':
                            metadata['media_series_title'] = item.grandparentTitle
                            metadata['media_title'] = item.title
                            metadata['media_season'] = item.seasonNumber
                            metadata['media_episode'] = item.episodeNumber
                            metadata['media_content_type'] = 'episode'
                            
                        # Get external IDs if available
                        if hasattr(item, 'guids'):
                            for guid in item.guids:
                                if 'imdb://' in guid.id:
                                    metadata['imdb_id'] = guid.id.replace('imdb://', '')
                                elif 'tmdb://' in guid.id:
                                    metadata['tmdb_id'] = guid.id.replace('tmdb://', '')
                                elif 'tvdb://' in guid.id:
                                    metadata['tvdb_id'] = guid.id.replace('tvdb://', '')
                        
                        _LOGGER.debug("Plex metadata retrieved: %s", metadata)
                        return metadata
                        
        except Exception as e:
            _LOGGER.error("Error fetching Plex metadata: %s", e)
            
        return None

    async def _extract_media_info_async(self, player, content_id):
        """Extract media information from player with async Plex API call."""
        try:
            # Fetch metadata from Plex API
            plex_metadata = await self.get_plex_metadata(content_id)
            if not plex_metadata:
                _LOGGER.debug("Failed to fetch Plex metadata")
                return None, None
                
            # Now process with the enhanced metadata
            attrs = player.attributes.copy()
            attrs.update(plex_metadata)
            
            # Re-run the extraction logic with enhanced metadata
            media_source = attrs.get("app_name", "").lower()
            
            # Try to detect media type
            media_type = None
            if attrs.get("media_content_type") == "movie":
                media_type = MEDIA_TYPE_MOVIE
            elif attrs.get("media_content_type") in ["tvshow", "episode"]:
                media_type = MEDIA_TYPE_EPISODE
            elif attrs.get("media_season") is not None or attrs.get("media_episode") is not None:
                media_type = MEDIA_TYPE_EPISODE
            
            # Extract IDs
            ids = {}
            if attrs.get("imdb_id"):
                ids["imdb"] = attrs.get("imdb_id")
            if attrs.get("tmdb_id"):
                ids["tmdb"] = attrs.get("tmdb_id")
            if attrs.get("tvdb_id"):
                ids["tvdb"] = attrs.get("tvdb_id")
            
            # Build media object
            media_obj = {}
            
            if media_type == MEDIA_TYPE_MOVIE:
                media_obj["movie"] = {
                    "title": attrs.get("media_title"),
                    "year": attrs.get("year"),
                }
                if ids:
                    media_obj["movie"]["ids"] = ids
                    
            elif media_type == MEDIA_TYPE_EPISODE:
                show_name = attrs.get("media_series_title")
                season = attrs.get("media_season")
                episode = attrs.get("media_episode")
                
                media_obj["show"] = {
                    "title": show_name,
                }
                if ids:
                    media_obj["show"]["ids"] = ids
                    
                media_obj["episode"] = {
                    "season": season,
                    "number": episode,
                }
            
            return media_type, media_obj
            
        except Exception as e:
            _LOGGER.error("Error in async media info extraction: %s", e)
            return None, None

    async def start_watching(self, media_obj: dict, progress: float):
        """Send start watching to Trakt."""
        if not self._update_watching:
            return True
            
        data = {
            **media_obj,
            "progress": progress,
            "app_version": "1.0",
            "app_date": datetime.now().isoformat(),
        }
        
        result = await self._api_request(SCROBBLE_START, data=data)
        if result:
            self._is_watching = True
            self._watching_started = time.time()
            _LOGGER.info("Started watching on Trakt")
            return True
        return False

    async def pause_watching(self, media_obj: dict, progress: float):
        """Send pause watching to Trakt."""
        if not self._update_watching or not self._is_watching:
            return True
            
        data = {
            **media_obj,
            "progress": progress,
        }
        
        result = await self._api_request(SCROBBLE_PAUSE, data=data)
        if result:
            _LOGGER.info("Paused watching on Trakt")
            return True
        return False

    async def scrobble(self, media_obj: dict, progress: float):
        """Scrobble to Trakt."""
        data = {
            **media_obj,
            "progress": progress,
            "app_version": "1.0",
            "app_date": datetime.now().isoformat(),
        }
        
        result = await self._api_request(SCROBBLE_STOP, data=data)
        if result:
            self._is_watching = False
            self._last_scrobbled = media_obj
            _LOGGER.info("Successfully scrobbled to Trakt")
            return True
        return False

    def calculate_progress(self, player):
        """Calculate the current playback progress."""
        position = player.attributes.get("media_position", 0)
        duration = player.attributes.get("media_duration", 0)
        
        # Handle position updated at
        last_updated = player.attributes.get("media_position_updated_at")
        if last_updated and player.state == STATE_PLAYING:
            if isinstance(last_updated, datetime):
                elapsed = dt_util.now() - dt_util.as_utc(last_updated)
                position += elapsed.total_seconds()
        
        if duration > 0:
            progress = min((position / duration) * 100, 100)
            return progress, position, duration
        
        return 0, position, duration

    def update(self):
        """Update the Trakt scrobbler."""
        if not self.check_entities():
            _LOGGER.debug("Entity checks failed - not updating")
            return
            
        for player_entity_id in self._media_players:
            player = self.hass.states.get(player_entity_id)
            if not player:
                continue
                
            # Only process if player is playing or paused
            if player.state not in [STATE_PLAYING, STATE_PAUSED]:
                continue
                
            # Extract media information
            media_type, media_obj = self._extract_media_info(player)
            
            # Handle async Plex processing
            if media_type == "PLEX_ASYNC_NEEDED":
                content_id = media_obj  # media_obj contains the content_id in this case
                _LOGGER.debug("Starting async Plex metadata fetch for %s", player_entity_id)
                # Create async task for Plex metadata fetch
                async def process_plex_metadata():
                    async_media_type, async_media_obj = await self._extract_media_info_async(player, content_id)
                    if async_media_type and async_media_obj:
                        # Process the media with the fetched metadata
                        await self._process_media(player, async_media_type, async_media_obj)
                
                task = self.hass.async_create_task(process_plex_metadata())
                task.add_done_callback(self._handle_task_result)
                continue
                
            if not media_type or not media_obj:
                _LOGGER.debug("Could not extract media info from %s", player_entity_id)
                continue
                
            # We found a valid player - process it
            _LOGGER.debug("Processing player %s", player_entity_id)
            
            # Process the media synchronously
            task = self.hass.async_create_task(self._process_media(player, media_type, media_obj))
            task.add_done_callback(self._handle_task_result)
            
            # We only process the first valid player
            break

    async def _process_media(self, player, media_type, media_obj):
        """Process media information and handle scrobbling."""
        try:
            # Calculate progress
            progress, position, duration = self.calculate_progress(player)
            self._progress = progress
            self._duration = duration
            
            # Skip if duration is too short, but be more lenient for episodes
            # Episodes can be very short (Bref, Kaamelott = 2 minutes)
            # Movies should be at least 5 minutes
            min_duration = MIN_EPISODE_DURATION_SECONDS if media_type == MEDIA_TYPE_EPISODE else MIN_DURATION_SECONDS
            if duration and duration < min_duration:
                content_type = "episode" if media_type == MEDIA_TYPE_EPISODE else "movie"
                _LOGGER.debug("%s duration too short (%s seconds), minimum is %s seconds", 
                             content_type.title(), duration, min_duration)
                return
            
            # Update internal state
            self._media_type = media_type
            self._current_media = media_obj
            
            # Extract display info
            if media_type == MEDIA_TYPE_MOVIE:
                self._title = media_obj["movie"]["title"]
                self._year = media_obj["movie"].get("year")
            else:
                self._show_name = media_obj["show"]["title"]
                self._season = media_obj["episode"]["season"]
                self._episode = media_obj["episode"]["number"]
                self._title = player.attributes.get("media_title")
            
            # Handle state changes
            if player.state == STATE_PLAYING:
                # Check if this is a new media
                if self._last_scrobbled != media_obj and not self._is_watching:
                    await self.start_watching(media_obj, progress)
                
                # Check if we should scrobble
                if progress >= self._scrobble_percentage and self._last_scrobbled != media_obj:
                    await self.scrobble(media_obj, progress)
                    
            elif player.state == STATE_PAUSED and self._is_watching:
                await self.pause_watching(media_obj, progress)
                
        except Exception as e:
            _LOGGER.error("Error processing media: %s", e)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def media_title(self):
        """Return the title of current media."""
        return self._title

    @property
    def media_series_title(self):
        """Return the series title if watching a show."""
        return self._show_name

    @property
    def media_season(self):
        """Return the season number."""
        return self._season

    @property
    def media_episode(self):
        """Return the episode number."""
        return self._episode

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self._progress is not None:
            attrs["progress"] = round(self._progress, 1)
        if self._media_type:
            attrs["media_type"] = self._media_type
        if self._is_watching:
            attrs["watching"] = True
        if self._year:
            attrs["year"] = self._year
        return attrs