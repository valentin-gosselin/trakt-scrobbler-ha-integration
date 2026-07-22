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
- 🔐 Two-click setup: a built-in Trakt app means you just authorize, no API app to create
- 🧩 Plex sign-in via PIN, automatic server discovery, and per-library selection
- 📥 Import your existing Plex watch history into Trakt (great when migrating from another tracker), with optional automatic sync

## Requirements

- Home Assistant 2024.1 or newer
- A Trakt.tv account
- Optional: a Plex Media Server for richer metadata and history import

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

Add the integration and follow the steps. There is no Trakt app to create: the
integration ships with a built-in one.

1. Go to Settings > Devices & Services
2. Click "Add Integration" and search for "Trakt Scrobbler"
3. **Authorize Trakt**: visit the shown URL, enter the code, and authorize.
4. **Options**: pick the media players to monitor, the scrobble percentage
   (default 80%), whether to update "Currently Watching", and optional
   conditional entities (only scrobble when a person is home, a switch is on, etc.).
5. **Connect Plex (optional)**: choose whether to connect a Plex account.
   - Authorize Plex by opening the shown link and signing in (PIN flow).
   - Pick your Plex server from the discovered list.
   - Select which Plex libraries to include, and unselect any you don't want on
     Trakt (for example personal or home video libraries).
6. **Import history (optional)**: optionally backfill your Trakt history from
   Plex right away (see below).

### Advanced: use your own Trakt app

If you prefer to use your own Trakt application, create one at
[trakt.tv/settings/apps/api/new](https://app.trakt.tv/settings/apps/api/new)
with redirect URI `urn:ietf:wg:oauth:2.0:oob` and the `scrobble` permission.
When the built-in credentials can't be used, the setup falls back to asking for
a Client ID and Client Secret.

## Importing your Plex history into Trakt

If you're moving from another tracker (like TV Time) and want your past
viewing on Trakt, you can backfill it from your Plex watch history.

- **During setup**: after connecting Plex and choosing libraries, tick the
  import step. Leave the start date empty to import everything, or set it (for
  example your TV Time import date) to import only from then on.
- **Any time**: call the `trakt_scrobbler.import_plex_history` action from
  Developer Tools > Actions, with an optional `start_date` and a `dry_run`
  option (on by default) that only logs what would be added.
- **Keep it in sync**: enable "Automatically sync Plex history to Trakt" in the
  integration options to periodically import recent Plex history.

Notes:

- Only your own watches are imported, never other Plex users' history on a
  shared server.
- It is deduplicated against your existing Trakt history, so running it more
  than once is safe.
- Content in unselected libraries (personal videos, etc.) is skipped.

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

See [CHANGELOG.md](CHANGELOG.md) for the full release history.