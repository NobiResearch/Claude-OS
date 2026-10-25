# Changelog

User-visible changes to Claude OS. Evolve runs add entries under **Unreleased**.

## Unreleased

- **`cos security`**: FileVault, SIP, the firewall and Gatekeeper, what each does and how to
  turn it on. `cos security on firewall --yes` turns the firewall on through macOS's own
  password dialog, which says Claude OS is asking. It only ever turns things on. The
  desktop's Security card offers it while the firewall is off
  ([0008](docs/decisions/0008-firewall-switch.md)).

- `cos update` says "couldn't check" for npm, the App Store or Rust when it can't reach them
  (offline, say), instead of a reassuring "up to date".

- `cos clean` reports what it actually freed: deleting old simulator runtimes counted 0 B when
  Xcode's simulator service was busy, and now counts each runtime it deleted. A cache that a
  running tool holds (uv, while an MCP server runs through `uvx`) is skipped, with a
  sentence saying why, instead of waiting minutes and freeing nothing.

- **Night shift opens pull requests for everything and merges the safe ones.** Work that
  touches Claude OS's core no longer stays on your Mac until morning. It's pushed, CI
  runs, and the pull request waits for your merge; everything else merges by itself. The
  morning brief lists what waits ("Waiting for your merge"), and `cos hook check` shows
  it too. Merges, and the commands that could merge another way, now ask unless the night
  shift's check passes ([0006](docs/decisions/0006-night-shift-pushes.md), second
  amendment).

- Night shift's push check closes four gaps the board found: a moved file now counts under
  its old name too, a file in `lib/` that could shadow Python's own modules counts as a
  safety file, a failed `git diff` asks you instead of passing, and the hook only approves
  while it runs from a clean main.

- Pausing in Claude OS's player keeps the paused song on screen, and play resumes it, however
  long the pause. Before, it fell back to whatever the Music app last had. Play and pause
  also no longer swap the cover image back and forth.

- Playing music from the chat inside Claude OS works. The check for "is Claude OS running?"
  couldn't see the app from inside the app, so radio and songs said it wasn't running.

- **Clicking a notification opens what it's about**: the board's minutes, the morning brief,
  evolve's branches or Background jobs. The click target comes from a fixed list, so a click
  only ever navigates.

- **Watch the board meet.** While a meeting runs, Evolution › Board shows "In session" and
  each seat waiting, deliberating or voted. When it ends, the minutes appear in the same
  place without the chatter that came before them. Settings and `cos daemon list` say when
  a background job is running. The notification at the end now says what happened ("Board
  minutes — weekly review", or that it ran out of time) instead of the run's first line
  ([0007](docs/decisions/0007-live-daemon-runs.md)).
- Background jobs can't schedule wakeups or timers any more. The first weekly meeting
  finished in 6 minutes and then waited 14 more on a wakeup it had set itself.

- Night shift: branches that change `core.py`, `cli.py`, `evolve.py` or `server.py` now
  wait for you too, because the night shift's own checks rely on them (amendment to 0006,
  from the first weekly board meeting).

- `cos friction add`, `cos remember` and `cos memory --forget` print one clear line instead
  of a traceback when private state can't be written (as in a sandboxed run).

- **Night shift** (Settings › Permissions, off by default): while you're away, Claude can
  push its own `night/…` branches and open pull requests for Claude OS without stalling on
  a prompt until morning. Never `main`, never a force push. Every commit and message is
  checked for private data first, and branches that change Claude OS's own permissions,
  laws, CI or guard still wait for you. Each push is journaled and listed in the next
  morning's brief. `cos hook check <branch>` shows what it would decide
  ([0006](docs/decisions/0006-night-shift-pushes.md)).

- **Daemons on a Pro or Max plan run without a dollar cap.** The cap is Claude Code's
  estimate at API prices, so on a flat plan it only cut runs short (a weekly board meeting
  could stop halfway). The daemons' time limits still bound every run. With an API key,
  which bills per token, the caps stay.

- **Backup signal**: `cos status`, the boot banner and the morning brief say "Time Machine
  isn't set up" when it isn't, as a quiet note (never a notification). Pulse checks once a
  day with `tmutil destinationinfo`, which never mounts or names a backup disk. Back up
  another way? `cos config pulse.backup_check false`
  ([0005](docs/decisions/0005-radio-and-backup-signal.md)).
- **Updates flag downgrades and new version schemes.** When Homebrew or npm's "latest" is
  *lower* than what's installed, `cos update` marks it ▼ (downgrade); when a build number
  or year turns into an ordinary version (say 9430 → 0.7.0), it's marked ≠ instead of a
  misleading "major". Both count as "look first" next to ▲ majors, and the desktop's
  Updates app leaves them unticked.

## 0.7.0 — 2026-10-25

Music that keeps going, and a safer Claude OS. Built overnight
([0005](docs/decisions/0005-radio-and-backup-signal.md)).

**Music**
- **Radio**: `cos music radio "<song> <artist>"` plays the song in Claude OS's own player,
  then keeps going with similar music from its Apple Music station (the artist's if the
  song has none); with no argument it starts from the song playing now. The `/music` skill
  uses radio for moods, and the desktop's Music app has a Radio button next to ⏭. If Apple
  Music has no station, the song plays alone and `cos` says so. (New: the first real
  playback test is still to come.)
- **Playlists play in Claude OS's own player**, from `cos music playlist <name>` or the
  desktop. Next, previous and shuffle go there too; `like` rates the song actually playing,
  even mid-playlist or mid-radio.

**Your day**
- **Notifications from Claude OS** (0004): with the setting on, alerts and the morning brief
  arrive with Claude OS's own name and icon; clicking one opens the desktop. The text goes
  through a private outbox in `~/.claude-os`, and the link that wakes the app carries
  nothing. Without permission (or with the app closed) they fall back to AppleScript.
- **Today's brief on the desktop**: once the morning daemon has written it, a "☕ Today's
  brief" chip leads Today and opens it. The brief talks to you as "you" and doesn't guess
  things about you.
- **`cos startup` no longer summons a password dialog.** On macOS 27, `sfltool dumpbtm`
  shows an admin password dialog; the audit now reads launch agents and daemons directly.
  `cos startup --full` (apps that open at login too) asks for an Allow first and is refused
  in background jobs. Scripts say "runs a script", not "unsigned code".

**Security** (a fresh review of everything since v0.2, plus what dogfooding found)
- `claude-os://` links that change something need this launch's nonce, so a web page or
  feed link can't make Claude OS play, rate or ask macOS for a permission; player answers
  carry a request id.
- Only http(s)/mailto links leave the app; feeds keep only http(s) links; Markdown links
  can't break out of their attribute; the CSP drops `'unsafe-inline'` styles.
- Evolve: the Guardian checks every commit and message a merge would publish; tests run on
  a fresh checkout of exactly the merged commit, in a sandbox with no internet that can't
  read `~/.ssh`, `~/.claude-os` and other private folders; no tests, no merge.
- Background jobs can't connect the calendar, set the weather place, add feeds, change
  config, play or rate music, write the memory, start another Claude, a server or a build.
  A feed item steering the morning brief can't plant "facts" in every boot banner.
- Weather coordinates join the Guardian's private terms.

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
