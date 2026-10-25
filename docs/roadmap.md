# Roadmap

The evolve loop takes work from open friction first, then the board's weekly priorities,
then **Next** (top to bottom). Anyone, human or Claude, can add ideas. Keep items concrete:
what, where, and how we'll know it works.

## Next

1. **Claude OS everywhere** (research: [claude-code-plugin](research/claude-code-plugin.md);
   board first, it touches permissions and privacy): the repo as a local Claude Code plugin
   named `cos`, so `/music`, `/tidy`, `/update`, `/startup`, `/brief` work in any directory.
   First verify in-place loading from a local-directory marketplace on this Mac.
2. **Trend sparklines** in Vitals, once `trends.jsonl` holds 14+ days.
3. **`cos shortcuts`** (0004 conditions: `list` free; `run` only as a mutation): when there
   are shortcuts worth running.
4. **"Leave in time"** and **a brief timed to the first event**: when the calendar has
   events (0004, 0005). Calendar.app's own "Time to Leave" may already be enough.

## Hardening

- **Deny-by-default sandbox for model-written tests**: today it's allow-default minus
  writes, the network and private folders; move to an explicit allowlist (board, Guardian).

## Research (for `/lab`)

- Nothing open. Answered: [Apple Music catalog playback](research/apple-music-catalog-playback.md)
  (Claude OS's own MusicKit player), [Claude OS as a plugin](research/claude-code-plugin.md);
  the menu bar presence is Claude OS.app's status item.

## Ideas

- `cos net`: Wi-Fi quality, DNS, captive-portal and VPN checks (0005: its own proposal;
  the network name is personal and reading it needs Location).
- Focus modes via Shortcuts (`cos focus work|off`).
- Time Machine: last backup age, once it can be read without mounting the destination
  (0005; today `cos status` only says whether Time Machine is set up).
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
