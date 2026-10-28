# Roadmap

The evolve loop takes work from open friction first, then the board's weekly priorities,
then **Next** (top to bottom). Anyone, human or Claude, can add ideas. Keep items concrete:
what, where, and how we'll know it works.

## Next

1. **Trend sparklines** in Vitals, once `trends.jsonl` holds 14+ days.
2. **`cos shortcuts`** (0004 conditions: `list` free; `run` only as a mutation): when there
   are shortcuts worth running.
3. **"Leave in time"** and **a brief timed to the first event**: when the calendar has
   events (0004, 0005). Calendar.app's own "Time to Leave" may already be enough.
4. **A light and dark app icon** (0022): docs/brand has both variants as Icon Composer layers,
   but following macOS's appearance needs an `.icon` compiled by Xcode's `actool`, which the
   build doesn't use yet (it needs only the Command Line Tools). Take a second look at the light
   icon's likeness to Reminders first.

## Hardening

- Done: the sandbox for model-written tests runs any Xcode in `/Applications` that's
  selected, under whatever name (friction #24). It's deny-by-default (Apple Events,
  LaunchServices, the home folder and the parent's environment are out of reach) and has no
  network: the tests' servers listen on Unix sockets in the run's own folder. The morning
  merge queue is moot since 0013: Claude merges green pull requests as they're ready.

## Research (for `/lab`)

- **Growing the project** ([research](research/growing-the-project.md)): what Hermes Agent
  did that a small project can copy. The name is settled (0019); every public step is the
  human's.
- Nothing else open. Answered: [a daily mix without an LLM](research/daily-mix.md) (Apple's own
  personal mixes through MusicKit: one fixed `claude-os://music/mix`), [Time Machine's last
  backup date](research/time-machine-last-backup.md) (`defaults export` reads it without Full
  Disk Access; verify with a real destination), [Apple Music catalog playback](research/apple-music-catalog-playback.md)
  (Ovenbird's own MusicKit player), [Ovenbird as a plugin](research/claude-code-plugin.md);
  the menu bar presence is Ovenbird.app's status item.

## Ideas

- Focus modes via Shortcuts (`cos focus work|off`).
- Time Machine's last backup age, once it can be read without Full Disk Access or mounting
  (0005, 0012; `cos backup` covers setting it up).
- **A daily mix**: Apple's own personal mixes through MusicKit, one fixed `claude-os://music/mix`
  ([research](research/daily-mix.md)). Waits until the human asks (0012); never picked in a
  run that reads feeds (Guardian).
- `cos power`: what keeps the Mac or display awake (`pmset -g assertions`), once friction
  asks; deliberate keepers (caffeinate, keep-awake apps) mustn't become nightly signals.
- Photo library duplicate report (read-only).
- **A community skills catalog** ([research](research/growing-the-project.md)): one
  `catalog/<name>.yaml` per pull request, pinned to an exact commit and installed by `cos`;
  the Guardian scans each one, and a human merges it. Board first, after 0017: an installed
  skill is code Claude runs.
- **Credit contributors**: when a maintainer finishes someone's pull request in a new one, keep
  them as `Co-authored-by:` and say so on the original; release notes name every contributor.
- **A Homebrew tap** ([research](research/growing-the-project.md)): `brew install --cask
  <owner>/tap/<name>` once there's a release; no `auto_updates` (the app only links to new
  versions), `arch: :arm64`, a `zap` that leaves `~/.claude-os` alone. Creating the tap's
  repository is the human's call; Homebrew's main repository waits for 30 days and 75 stars.
- **Trust first in the README**: a short threat model in plain words (read-only by default,
  `--yes`, the journal, no Full Disk Access or Accessibility, what merges on its own).
- Mail triage. Privacy-heavy: board review first.

## Done

- v0.1: status, clean, update, music, feeds, journal/friction/memory, daemons, evolve
  plumbing, guard, board, lab.
- v0.2: Ovenbird.app, the desktop, Claude chat with Allow/Deny cards, `cos serve`.
- v0.3: Shortcuts music route, old simulator runtimes, trend logging, demo mode.
- v0.4: permissions on request (0003): Ovenbird's own Apple Music player, weather +
  location, stable signing.
- v0.5: calendar & reminders, weather alerts, loving the right song.
- v0.6: one player (library via MusicKit), `cos startup`, Swift tests (0004).
- v0.7: radio and playlists in the one player, native notifications, Today's brief, the
  security review's fixes, `cos startup` without a password dialog (0005).
- Since v0.7 (Unreleased): the night shift's pull requests and merges (0006), the board and
  daemons live on the desktop (0007), `cos security` and the firewall switch (0008), `/music`
  `/tidy` `/update` `/startup` in any folder through skill links rather than a plugin (0009),
  the Guardian on pull request text, Night shift turned on only in the app's own dialog, and
  Today's Radio chip: one click to a radio from a song you've been playing (0012's "morning
  station").
