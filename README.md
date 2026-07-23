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
- 📅 Trakt data sensors (upcoming, next-to-watch, watchlist, stats, recommendations) and action services, so one Trakt app covers everything

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

## Trakt sensors

Because this integration already holds your one Trakt app, it can also expose
Trakt data as sensors, so you don't need the separate `sensor.trakt`
integration. Enable the groups you want in the integration options (upcoming and
next-to-watch are on by default):

| Sensor | What it exposes |
|---|---|
| `sensor.upcoming_shows` / `sensor.upcoming_movies` | Your upcoming calendar. Attributes include a `data` array in Upcoming Media Card format. |
| `sensor.next_to_watch` | The next unwatched, already-aired episode for each in-progress show. |
| `sensor.watchlist` | Items on your Trakt watchlist. |
| `sensor.stats` | Movies/episodes watched, shows, total minutes/days. |
| `sensor.recommended_shows` / `sensor.recommended_movies` | Personalized recommendations. |

## Trakt Card

The integration ships its own dashboard card, `custom:trakt-card`, and registers
it automatically. You do not need to install anything or add a Lovelace resource:
open your dashboard, click **Add card**, and pick **Trakt Card** from the list.

It has a **visual editor**: pick a view from the dropdown and the matching sensor
is filled in for you. Views whose sensor group is disabled are marked with `(?)`
(enable those groups in the integration options to use them).

The card has one option that matters, `view`, which selects what it shows. Each
view reads the matching sensor:

| `view` | Entity | Shows |
|---|---|---|
| `upcoming` | `sensor.upcoming_shows` or `sensor.upcoming_movies` | Your upcoming calendar with posters. |
| `next_to_watch` | `sensor.next_to_watch` | The next episode to watch per in-progress show, with a "mark watched" button. |
| `watchlist` | `sensor.watchlist` | Your Trakt watchlist. |
| `stats` | `sensor.stats` | A summary of your watch stats. |
| `recommendations` | `sensor.recommended_shows` or `sensor.recommended_movies` | Recommendations, with an "add to watchlist" button. |

### Options

| Option | Default | Description |
|---|---|---|
| `view` | `upcoming` | One of the views above. |
| `entity` | matches the view | The sensor to read. Set this only if your entity ids differ from the defaults. |
| `title` | the view name | Optional card title. |

### Examples

Upcoming episodes with posters:

```yaml
type: custom:trakt-card
view: upcoming
entity: sensor.upcoming_shows
title: Upcoming Episodes
```

Next episode to watch (with a mark-watched button on each item):

```yaml
type: custom:trakt-card
view: next_to_watch
entity: sensor.next_to_watch
```

Recommendations (with an add-to-watchlist button on each item):

```yaml
type: custom:trakt-card
view: recommendations
entity: sensor.recommended_shows
```

Your watch stats:

```yaml
type: custom:trakt-card
view: stats
entity: sensor.stats
```

The card is localized (English, French, German, Spanish) and follows your Home
Assistant language.

## Trakt actions

You can also act on Trakt from automations and scripts. Each service accepts an
id (`trakt`, `imdb`, `tmdb` or `tvdb`) or a `title` to look the item up. The
Trakt Card uses these services for its buttons.

`trakt_scrobbler.add_to_watchlist` / `remove_from_watchlist` add or remove a
movie or show:

```yaml
service: trakt_scrobbler.add_to_watchlist
data:
  media_type: show   # movie or show
  imdb: tt0826760    # or tmdb / tvdb / trakt, or a title
```

`trakt_scrobbler.mark_watched` marks a movie or an episode as watched:

```yaml
service: trakt_scrobbler.mark_watched
data:
  media_type: episode   # movie or episode
  tmdb: "32368"         # show id for episodes
  season: 3
  episode: 9
```

For a movie, pass `media_type: movie` with a movie id (or `title` and `year`).

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