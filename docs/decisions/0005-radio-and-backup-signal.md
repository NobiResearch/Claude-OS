# 0005 — radio in the one player, a quiet backup signal

- **Status:** accepted
- **Date:** 2026-10-25
- **Decided by:** the board (fourth meeting, overnight)

## Question

What should Claude OS build next? Candidates: (a) "leave in time" notifications, (b)
`cos shortcuts`, (c) backup health and `cos net` as pulse signals, (d) a brief timed to
the first calendar event, (e) radio: after a song chosen for a mood, keep playing similar
music through Apple Music's station for it.

## Votes

| Candidate | Architect | Guardian | Steward | Skeptic | Decision |
|---|---|---|---|---|---|
| (e) radio | amend | approve, conditions | amend | amend | **build** |
| (c) backup signal | amend | amend | amend | amend | **build, backup only** |
| (b) `cos shortcuts` | reject (tonight) | amend | reject | reject | wait for demand |
| (a) leave in time | reject | reject | reject | reject | wait for calendar events |
| (d) brief timing | reject | reject | reject | reject | wait for calendar events |
| `cos net` | cut | defer | cut | cut | own proposal later |

Music is by far the most-used app, and a mood request ("something chill") ends after one
song. Calendar features have nothing to work on yet, and Calendar.app already has "Time to
Leave". Nothing in Claude OS says when a Mac has no backup.

## Conditions

**(e) radio**
- One surface: `cos music radio [<query>]`. Seeded from the catalog: with a query, the best
  catalog pick; without one, the current song's catalog id (a library-only song gets a
  clear error). `cos music play` is unchanged.
- The app's `radio?id=<digits>` command sits behind the same nonce and Apple Music switch
  as `play`. It tries the song's station, then the artist's station, then plays the song
  alone, and says which in `player.json` (`radio`, `station`).
- While a queue moves by itself (a playlist or a station), now-playing follows the queue's
  current entry; if that isn't a song, `love` refuses instead of rating the seed.
- `like` journals the song from the player's answer, not from the state read before it.
- Refused in daemons (`DAEMON_REFUSED`, `_MUTATING`), with a test.
- The `/music` skill uses radio for moods and activities, named songs stay single, and it
  stops anchoring on fixed example songs (check `music history`, rotate).
- Tests use made-up songs and artists, never ones from the human's history.

**(c) backup signal**
- `tmutil destinationinfo -X` only (a plist, so it works in any system language), with a
  timeout; an empty dict means "Time Machine isn't set up". Any failure means unknown, and
  unknown means no signal. No `tmutil latestbackup` for now: it tries to mount the
  destination, which can fail or prompt for a network or removable volume.
- Level `note`, never `warn`, so pulse never notifies about it. Generic text, no
  destination names or mount points. The only suggestion is opening Time Machine settings;
  never `tmutil enable|setdestination|startbackup`.
- Pulse refreshes a daily cache (`backup`) that `signals()` reads, like updates and clean.
- `pulse.backup_check` (default on) turns it off, for people who back up another way.
