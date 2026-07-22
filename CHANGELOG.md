# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-07-22

### Added
- **Trakt data sensors** (one integration, one Trakt app, so you no longer need the separate `sensor.trakt`):
  - `sensor.upcoming_shows` / `sensor.upcoming_movies`: your upcoming calendar, with attributes in both a native form and an **Upcoming Media Card**-compatible `data` array (drop-in replacement).
  - `sensor.next_to_watch`: the next unwatched, already-aired episode for each in-progress show.
  - `sensor.watchlist`: your Trakt watchlist.
  - `sensor.stats`: movies/episodes watched, shows, total minutes/days.
  - `sensor.recommended_shows` / `sensor.recommended_movies`: personalized recommendations.
- **Action services** to write to Trakt from automations:
  - `add_to_watchlist`, `remove_from_watchlist`, `mark_watched` (by ids or title).
- **Per-group toggles** in the options so you only get the sensors you want (upcoming and next-to-watch on by default), plus an upcoming-window setting in days.
- All entities are grouped under a single Trakt device.

### Changed
- A shared data update coordinator fetches Trakt data on a polling interval, separate from real-time scrobbling. Rate limits are respected (next-to-watch caps how many shows it checks per refresh).

## [1.2.0] - 2026-07-22

### Added
- **Built-in Trakt app**: setup no longer requires creating your own Trakt API application or pasting a client id/secret. The config flow goes straight to device authorization: open the activation URL, enter the code, done. Manual client id/secret entry remains available as a fallback.
- **Plex PIN authentication**: connect Plex through the standard plex.tv PIN flow instead of pasting an `X-Plex-Token` by hand (which expires). The token obtained this way is durable.
- **Plex server auto-discovery**: after authorizing, the integration lists your Plex Media Servers and lets you pick one, probing which connections actually respond so it doesn't point at an offline server.
- **Plex library selection**: choose which Plex libraries to scrobble and import from. Personal/home video libraries can be excluded so they never reach Trakt (applied to both real-time scrobbling and history import).
- **Import Plex history into Trakt (backfill)**: a service `trakt_scrobbler.import_plex_history` and an optional step during setup to backfill your Trakt history from Plex, using the real watch dates. Useful when migrating from another tracker (e.g. TV Time).
  - Only the token owner's watches are imported, never other Plex users' history.
  - Deduplicated against your existing Trakt history, so re-running is safe.
  - Items without ids are resolved by Trakt title search, and unmatched titles (personal videos) are skipped.
  - A `dry_run` mode logs what would be added without sending anything.
- **Automatic periodic history sync**: optional setting to keep Trakt in sync with recent Plex history on an interval.

### Changed
- Shared Plex-to-Trakt mapping (guid parsing, Trakt search) between the real-time scrobbler and the history import so both behave consistently.
- Completed French, German and Spanish translations for all setup and options steps.

## [1.1.0] - 2025-08-07

### Added
- Smart fallback search for TV shows when TMDB IDs don't match between Plex and Trakt
- Rate limiting protection with automatic request throttling (1.5s between POST requests)
- Support for very short episodes (1 minute minimum for shows like "Bref", "Kaamelott")
- Adaptive scrobble threshold (50% for episodes under 5 minutes, 80% for normal content)
- Direct sync to Trakt history using `/sync/history` API
- Enhanced Plex metadata extraction via Plex API
- Debug mode configuration option
- Comprehensive README with clear supported/unsupported sources

### Changed
- Improved logging with cleaner, more professional output
- Removed excessive debug logs for production use
- Removed emoji characters from log messages
- Better error handling for rate limiting (429 errors)
- Optimized API calls to reduce unnecessary requests

### Fixed
- Fixed issue where episodes weren't marked as watched despite successful API responses
- Fixed TMDB ID mismatch between Plex (1017098) and Trakt (60715) for shows like "Bref"
- Fixed scrobbling for very short episodes being incorrectly filtered out
- Fixed OAuth token refresh mechanism
- Fixed duplicate scrobbling prevention

## [1.0.0] - 2025-08-01

### Initial Release
- OAuth2 authentication with Trakt.tv using Device Flow
- Automatic scrobbling of movies and TV shows
- Support for multiple media players
- Configurable scrobble percentage threshold
- "Currently Watching" status updates
- Conditional scrobbling based on entities (presence, switches)
- Multi-language support (EN, FR, ES, DE)
- Plex server integration for enhanced metadata
- Support for standard media players with proper metadata