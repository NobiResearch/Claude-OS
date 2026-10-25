# Roadmap

The evolve loop takes work from open friction first, then the board's weekly priorities,
then **Next** (top to bottom). Anyone, human or Claude, can add ideas. Keep items concrete:
what, where, and how we'll know it works.

## Next

1. **Backup signal** (decision 0005, approved with conditions; read them there):
   `status.backup()` runs `tmutil destinationinfo -X` (plist; `core.run` with a timeout) and
   returns `{"configured": bool}` or `None` when unknown. `cos status` and `daemon.pulse()`
   refresh a `backup` cache when it's older than a day; `status.signals()` adds a `note` (never `warn`) "Time Machine isn't set up"
   when the cache says not configured, unless `config pulse.backup_check` is false (add it
   to `DEFAULT_CONFIG`, default true). No `tmutil latestbackup`, no destination names in the
   text. Done when: tests with fixture plists (empty dict, one destination, command failure,
   garbage output) pass; `cos status` shows the note on a Mac without Time Machine; the
   `/tidy` or `/update` skill doesn't need to change.
2. **Radio in the one player** (0005): being built interactively.
3. **Trend sparklines** in Vitals, once `trends.jsonl` holds 14+ days.
4. **`cos shortcuts`** (0004 conditions: `list` free; `run` only as a mutation): when there
   are shortcuts worth running.
5. **"Leave in time"** and **a brief timed to the first event**: when the calendar has
   events (0004, 0005). Calendar.app's own "Time to Leave" may already be enough.

## Hardening

- **Deny-by-default sandbox for model-written tests**: today it's allow-default minus
  writes, the network and private folders; move to an explicit allowlist (board, Guardian).

## Research (for `/lab`)

- What's the cheapest, sturdiest menu bar presence? (SwiftBar plugin vs. a tiny Swift app.)
- Packaging Claude OS skills as a Claude Code plugin so they work from any directory.

## Ideas

- `cos net`: Wi-Fi quality, DNS, captive-portal and VPN checks (0005: its own proposal;
  the network name is personal and reading it needs Location).
- Focus modes via Shortcuts (`cos focus work|off`).
- Time Machine: last backup age as a pulse signal.
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
- After v0.6: native notifications, the security review's fixes, playlists in the one player.
