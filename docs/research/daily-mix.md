# A daily "music picked for you" button, without an LLM picking songs

- **Asked:** 2026-10-26, by the board (0012: the Steward's "Morning station"; the Guardian
  doesn't want a model choosing songs in a run that also reads feeds)
- **Status:** answered; not built

## Answer

Apple already picks the songs. MusicKit's **`MusicPersonalRecommendationsRequest`** (macOS
13+) returns the human's "Made for You" groups, and their personal mixes (Favorites, Chill,
Get Up!, New Music) are playlists of kind `Playlist.Kind.personalMix` (ids starting `pl.pm-`),
refreshed weekly. Claude OS's player can play one the way it already plays playlists. It
needs only the Media & Apple Music permission the player already has; playing needs the
subscription the player already uses.

## Evidence

- MusicKit's Swift interface in the macOS 27 SDK: `MusicPersonalRecommendationsRequest`
  and its response (groups with `title`, `reason`, `nextRefreshDate`, `albums`, `playlists`,
  `stations`), `Playlist.Kind.personalMix`, `MusicRecentlyPlayedRequest` and
  `MusicRecentlyPlayedContainerRequest` (verified by reading the SDK's `.swiftinterface`).
- [WWDC22: Explore more content with MusicKit](https://developer.apple.com/videos/play/wwdc2022/110347/);
  Apple Music API: [Get all recommendations](https://developer.apple.com/documentation/applemusicapi/get-all-recommendations),
  [the user's personal station](https://developer.apple.com/documentation/applemusicapi/get-the-user's-personal-apple-music-station)
  (`/v1/catalog/{storefront}/stations?filter[identity]=personal`, through `MusicDataRequest`).
- Queues of separate catalog songs work in the API (`ApplicationMusicPlayer.Queue(for:)`,
  `insert(_:position:)` at `.afterCurrentEntry` or `.tail`), but a developer reports that on
  macOS a queue mixing catalog songs the human also owns fails or drops songs (FB23707746,
  July 2026, unanswered) ([thread](https://developer.apple.com/forums/thread/832470)). Unverified here.
- Each recommendation group holds at most 12 items ([forum](https://developer.apple.com/forums/thread/772794));
  group titles are localized, so pick by kind and id, never by name.
- Heavy rotation (`/v1/me/history/heavy-rotation`) is often empty; Apple points to the
  recently-played endpoints instead ([forum](https://developer.apple.com/forums/thread/677297)).

## Recommendation

One fixed command with no parameters, `claude-os://music/mix`: the app asks for the
recommendations, plays the first `personalMix` playlist (the human can pick a favourite mix
once in Settings, kept by its `pl.pm-` id), and falls back to the personal station, then the
most recent recently-played playlist or station. No song lists, no model, nothing a feed item
could steer. A Today card's Play button and the brief can both point at it.

## Open questions (unverified)

- Does a personal mix play cleanly when the human owns some of its songs?
- Does playback in Claude OS's player count toward Apple's listening history?
- Are `pl.pm-` ids stable week to week? What does a non-US storefront return?
