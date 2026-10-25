# Changelog

User-visible changes to Claude OS. Evolve runs add entries under **Unreleased**.

## Unreleased

- **Radio** (decision 0005): `cos music radio "<song> <artist>"` plays the song in Claude
  OS's own player, then keeps going with similar music from its Apple Music station (the
  artist's if the song has none); with no argument it starts from the song playing now.
  `next` skips within it, and `like` rates the song actually playing. If Apple Music has no
  station, the song plays alone and `cos` says so. The `/music` skill uses radio for moods,
  and the desktop's Music app has a Radio button next to ⏭.
  *Not yet tried on real playback (built overnight).*

- **Playlists play in Claude OS's own player** (with "Apple Music in Claude OS" on), from
  `cos music playlist <name>` or the desktop's Music app. Next, previous and shuffle go to
  that player too, so "not this one" skips inside the playlist; `next` on a single song
  stops it. The Music app is still the fallback.

- **Security review fixes** (a fresh review of everything since v0.2):
  - `claude-os://` links that change something (play, rate, permission prompts) need this
    launch's nonce from `~/.claude-os/state/app.nonce`, so a web page or feed link can't make
    Claude OS act; the player also honours the "Apple Music in Claude OS" switch.
  - Only http(s)/mailto links leave the app, and feeds keep only http(s) links.
  - Markdown links can no longer break out of their attribute; the desktop's CSP drops
    `'unsafe-inline'` styles.
  - Evolve: the Guardian checks every commit and message a merge would publish (not just
    the final diff); tests run on a fresh checkout of exactly the merged commit, inside a
    sandbox that can reach localhost but not the internet and can't read `~/.ssh`,
    `~/.claude-os` and other private folders; no tests, no merge.
  - Background jobs can't connect the calendar, set the weather place, add feeds, change
    config or play/rate music; those also ask first in interactive sessions.
  - Player answers carry a request id, so a stale state file can't pass for success.
  - The morning brief no longer launches Claude OS just to refresh the calendar.
  - Weather coordinates join the Guardian's private terms; a notification falls back to
    AppleScript if the app can't be woken.

- **Notifications from Claude OS** (decision 0004): with the new setting on, alerts and the
  morning brief arrive with Claude OS's own name and icon, and clicking one opens the
  desktop. The text goes through a private outbox in `~/.claude-os`; the link that wakes the
  app carries nothing, so no web page can make Claude OS say anything. Permission is asked
  only when you flip the switch; without it (or with the app closed) notifications fall back
  to AppleScript.

## 0.6.0 — 2026-10-25

One player ([0004](docs/decisions/0004-v0.6-one-player.md)).

- **One player:** with Apple Music on, library songs play in Claude OS too (MusicKit
  `MusicLibraryRequest`), so now-playing, pause and love work the same for everything;
  the Music app is the fallback. `cos music unlike` removes a rating.
- **`cos startup`** and `/startup`: what starts with this Mac, from macOS's own login-items
  list plus code signatures, odd ones first (missing programs, unsigned code, unused for
  months). Read-only. A "Starts with your Mac" card in Vitals.
- **Swift tests:** the app's link parsing, the native bridge's origin check and the
  server's ready line are tested, in CI.
- Fixed: library songs reported durations in milliseconds; loving a library song used the
  catalog endpoint. README screenshots refreshed.

## 0.5.0 — 2026-10-25

Your day.

- **Calendar & Reminders** (decision 0002's deferred B): Claude OS.app reads today's and
  tomorrow's events (recurring ones expanded, via EventKit) and due reminders, only after
  you click **Connect** in Settings. Read-only. `cos cal`, the Today panel, the brief.
- **Weather alerts:** the forecast adds an hourly outlook ("rain likely around 15:00",
  "rain easing around 04:00", thunderstorms first); alerts become signals everywhere.
- **Like the right song:** `cos music like` loves the song playing in Claude OS's own player
  through the Apple Music ratings API, and only touches the Music app when that's what's
  playing (it used to heart whatever was paused in Music).

## 0.4.0 — 2026-10-25

Permissions when the human asks for them ([0003](docs/decisions/0003-permissions-on-request.md)).

- **Settings › Permissions:** "Apple Music in Claude OS" and "Weather", both off by default.
- **Claude OS plays Apple Music itself:** MusicKit's ApplicationMusicPlayer under the narrow
  "Media & Apple Music" permission plays any catalog song; `cos music play` drives it via
  `claude-os://music/…` URLs and `cos music now` shows it. (An Accessibility-based helper
  was tried first and removed: see the amendment in 0003.) Needs macOS 14+, an App ID with
  the MusicKit service, and a macOS development profile in `~/.claude-os` (`cos music setup`).
- **Weather:** `cos weather` (Open-Meteo, no key), on the Today panel and in the brief. Pick a
  city, or "Use my location" in the app (CoreLocation, rounded to ~1 km, stays on this Mac;
  the place joins the Guardian's private terms).
- **Signing:** local builds are signed with your own Apple Development identity when there
  is one, so macOS grants survive rebuilds; ad-hoc (loudly) otherwise and under daemons.
  `COS_BUNDLE_ID` sets the bundle id (MusicKit needs one registered in your account).
- **MIT license.** Shortcut setup now includes "Get Text from Input".

## 0.3.0 — 2026-10-24

Decided by the board's first meeting ([0002](docs/decisions/0002-v0.3-priorities.md)).

- **Music:** catalog playback through a "Claude OS Play" shortcut (Music's Play App
  Intent, no new permissions): `cos music setup`, `--source shortcut`; verifies what plays.
- **Clean:** `simulator-runtimes-old` target (older simulator OS images, newest per platform
  always kept, safety review), with last-used dates.
- **Trends:** pulse logs one snapshot a day (`~/.claude-os/trends.jsonl`); `cos status`
  shows the weekly disk trend once there's a week of data; `/api/trends`.
- **Demo mode:** `cos serve --demo`, a fictional Mac from one fixtures module with a
  scripted chat; README screenshots come from it.
- Dates in the desktop follow the browser's language.

## 0.2.0 — 2026-10-24

The desktop.

- **Claude OS.app** (`app/`): native AppKit shell with a WKWebView desktop, menu bar
  status item, global hotkey ⌃⌥Space, crash-restarting server, ad-hoc signed; `cos app`.
- **The desktop** (`ui/`, no build step): menu bar, dock, draggable/resizable windows,
  ⌘K palette, boot screen, and apps: Claude, Vitals, Storage, Updates, Music, Feeds,
  Evolution, Journal, Memory, Settings.
- **Claude in the app** (`lib/cos/chat.py`): headless Claude Code over stream-json;
  permission prompts become Allow/Deny cards answered by the human; approvals journaled.
- **`cos serve`** (`lib/cos/server.py`): loopback-only API with a per-launch token
  (never in argv or env), Host-header check, CSP, background jobs for approved actions.
- Music search results carry album artwork.

## 0.1.0 — 2026-10-24

The founding release.

- **Kernel:** `CLAUDE.md` laws and syscall table; SessionStart boot banner; status line.
- **Syscalls:** `status`, `clean` (24 targets with safety levels), `update` (macOS,
  Homebrew, npm, mas, rustup), `music` (library + catalog), `feeds` (RSS/Atom/RDF with
  read tracking), `log`, `friction`, `remember`/`memory`, `notify`, `say`, `brief`,
  `daemon`, `evolve`, `guard`, `doctor`, `install`/`uninstall`, `config`.
- **Apps:** `/music`, `/tidy`, `/update`, `/brief`, `/board`, `/lab`, `/evolve`.
- **Colleagues:** board seats `architect`, `guardian`, `steward`, `skeptic`; lab `scout`.
- **Daemons:** `pulse` (free), `morning`, `evolve`, `board` (opt-in, budget-capped).
- **Privacy:** Guardian pre-commit hook and whole-tree test.
