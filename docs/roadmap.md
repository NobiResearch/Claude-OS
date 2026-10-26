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

## Hardening

- Nothing open. Done: the sandbox for model-written tests is deny-by-default (Apple Events,
  LaunchServices, the home folder and the parent's environment are out of reach) and has no
  network: the tests' servers listen on Unix sockets in the run's own folder. The morning
  merge queue is moot since 0013: Claude merges green pull requests as they're ready.

## Research (for `/lab`)

- Nothing open. Answered: [a daily mix without an LLM](research/daily-mix.md) (Apple's own
  personal mixes through MusicKit: one fixed `claude-os://music/mix`), [Time Machine's last
  backup date](research/time-machine-last-backup.md) (`defaults export` reads it without Full
  Disk Access; verify with a real destination), [Apple Music catalog playback](research/apple-music-catalog-playback.md)
  (Claude OS's own MusicKit player), [Claude OS as a plugin](research/claude-code-plugin.md);
  the menu bar presence is Claude OS.app's status item.

## Ideas

- A Network card in Vitals for `cos net` (0010), once friction shows it's asked for.
- Focus modes via Shortcuts (`cos focus work|off`).
- Time Machine's last backup age, once it can be read without Full Disk Access or mounting
  (0005, 0012; `cos backup` covers setting it up).
- **Morning station** (0012, Steward): a Today card that starts a radio seeded from a song
  the human played or liked this week, one click, no LLM. A full daily mix needs a queue in
  the player, and must never be picked in a run that reads feeds (Guardian).
- `cos power`: what keeps the Mac or display awake (`pmset -g assertions`), once friction
  asks; deliberate keepers (caffeinate, keep-awake apps) mustn't become nightly signals.
- Photo library duplicate report (read-only).
- Mail triage. Privacy-heavy: board review first.

## Done

- v0.1: status, clean, update, music, feeds, journal/friction/memory, daemons, evolve
  plumbing, guard, board, lab.
- v0.2: Claude OS.app, the desktop, Claude chat with Allow/Deny cards, `cos serve`.
- v0.3: Shortcuts music route, old simulator runtimes, trend logging, demo mode.
- v0.4: permissions on request (0003): Claude OS's own Apple Music player, weather +
  location, stable signing.
- v0.5: calendar & reminders, weather alerts, loving the right song.
- v0.6: one player (library via MusicKit), `cos startup`, Swift tests (0004).
- v0.7: radio and playlists in the one player, native notifications, Today's brief, the
  security review's fixes, `cos startup` without a password dialog (0005).
- Since v0.7 (Unreleased): the night shift's pull requests and merges (0006), the board and
  daemons live on the desktop (0007), `cos security` and the firewall switch (0008), `/music`
  `/tidy` `/update` `/startup` in any folder through skill links rather than a plugin (0009),
  the Guardian on pull request text, and Night shift turned on only in the app's own dialog.
