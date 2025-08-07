# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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