# Trakt Scrobbler for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/valentin-gosselin/trakt-scrobbler-ha-integration.svg)](https://github.com/valentin-gosselin/trakt-scrobbler-ha-integration/releases)

A Home Assistant integration that automatically scrobbles what you're watching from your media players to Trakt.tv.

## Features

- 🎬 Automatically scrobble movies and TV shows to Trakt.tv
- 📺 Support for multiple media players
- ⚙️ Configurable scrobble threshold (default 80%)
- 👀 Update "Currently Watching" status on Trakt
- 🏠 Conditional scrobbling based on presence or switches
- 🔐 Secure OAuth2 authentication with Device Flow

## Requirements

- Home Assistant 2023.1 or newer
- A Trakt.tv account
- A Trakt API application (free)

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS:
   - Repository: `https://github.com/valentin-gosselin/trakt-scrobbler-ha-integration`
   - Category: `Integration`
2. Click "Install"
3. Restart Home Assistant

### Manual Installation

1. Copy the `trakt_scrobbler` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

### Step 1: Create a Trakt Application

1. Go to [Trakt Apps](https://trakt.tv/oauth/applications)
2. Click "New Application"
3. Fill in the details:
   - **Name**: Home Assistant Scrobbler (or any name you prefer)
   - **Description**: Scrobbles from Home Assistant
   - **Redirect URI**: `urn:ietf:wg:oauth:2.0:oob`
   - **Javascript (cors) origins**: Leave empty
   - **Permissions**: Check "scrobble"
4. Save the application
5. Note your **Client ID** and **Client Secret**

### Step 2: Add Integration in Home Assistant

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Trakt Scrobbler"
4. Enter your Client ID and Client Secret
5. Follow the device authorization flow:
   - Visit the provided URL
   - Enter the code shown
   - Authorize the application
6. Configure your options:
   - Select media players to monitor
   - Set scrobble percentage (default 80%)
   - Enable/disable "Currently Watching" updates
   - Optional: Add entities for conditional scrobbling

## Configuration Options

### Media Players
Select which media players to monitor for scrobbling. The integration will check each player in order and scrobble from the first one that's playing.

### Scrobble Percentage
The percentage of the media that must be watched before it's scrobbled to Trakt. Default is 80% (Trakt's recommendation).

### Update Currently Watching
When enabled, the integration will update your "Currently Watching" status on Trakt when you start playing something.

### Conditional Entities
You can add entities (switches, input_booleans, or persons) that must be in a certain state for scrobbling to occur:
- **Switches/Input Booleans**: Must be "on"
- **Persons**: Must be "home"

This is useful for:
- Only scrobbling when you're home
- Having a "Do Not Scrobble" switch
- Creating complex automation conditions

## Supported Media Players

The integration works with media players that provide proper media metadata:

### ✅ Fully Supported
- **Plex** - Full metadata support including Plex API integration
- **Jellyfin** - Works with TMDB/IMDB IDs
- **Emby** - Works with TMDB/IMDB IDs  
- **Kodi** - Works with TMDB/IMDB IDs

### ⚠️ Limited Support
- **Apple TV** - Only if playing from supported sources (Plex, etc.)
- **Chromecast** - Only if casting from supported sources

### ❌ Not Supported
- **Netflix** - Does not expose metadata
- **Prime Video** - Does not expose metadata
- **Disney+** - Does not expose metadata
- **HBO Max** - Does not expose metadata
- **YouTube** - Does not expose metadata
- Most streaming services do not provide the necessary metadata

### Required Attributes

For movies:
- `media_title`: Movie title
- `media_content_type`: Should be "movie"
- Optional: `tmdb_id`, `imdb_id`, `year`

For TV shows:
- `media_series_title`: Show name
- `media_season`: Season number
- `media_episode`: Episode number
- `media_content_type`: Should be "tvshow" or "episode"
- Optional: `tmdb_id`, `imdb_id`, `tvdb_id`

## Troubleshooting

### Nothing is being scrobbled
1. Check that your media player is providing the necessary attributes
2. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.trakt_scrobbler: debug
   ```
3. Check the logs for error messages

### "Currently Watching" not updating
- Make sure the option is enabled in the integration options
- Check that your Trakt app has the "scrobble" permission

### Token expired
- Go to the integration options and reconfigure it
- You'll need to go through the device authorization flow again

## Development

This integration is based on the [Last.fm Scrobbler](https://github.com/valentin-gosselin/lastfm-scrobbler-ha-integration) by the same author.

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

### Local Development

1. Clone the repository
2. Copy to your Home Assistant development environment
3. Enable debug logging
4. Test your changes

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you find this integration useful, please:
- ⭐ Star the repository
- 🐛 Report issues on GitHub
- 💡 Suggest features
- 🤝 Contribute code

## Changelog

### 1.0.0
- Initial release
- OAuth2 authentication with device flow
- Movie and TV show scrobbling
- Configurable options
- Multi-language support (EN, FR)