# Roadmap

The evolve loop takes work from open friction first, then the board's weekly priorities,
then **Next** (top to bottom). Anyone, human or Claude, can add ideas. Keep items concrete:
what, where, and how we'll know it works.

## Next

1. **`cos cal`** (v0.4, board 0002): today's Calendar events and due Reminders, read-only,
   behind a user-initiated "Connect Calendar" button so the permission prompt is expected.
   Recurring events must expand correctly (AppleScript doesn't; consider EventKit).
2. **Trend sparklines** in Vitals, once `trends.jsonl` holds 14+ days.
3. **Calibrate the music helper** on more macOS versions (`inspect` dumps Music's
   accessibility tree; keep matching by structure, never by localized labels).
4. **`cos shortcuts`**: `list` and `run <name> [--input text]` bridge to the Shortcuts CLI,
   so the human's own automations become syscalls.
5. **Weather alerts**: a pulse signal for rain/snow/storm in the next hours (weather shipped
   in v0.4; see 0003).
6. **Startup audit** `cos startup`: login items, LaunchAgents and LaunchDaemons, with
   what each one is and whether it's signed. Read-only.

## Research (for `/lab`)

- Reliable Apple Music *catalog* playback without UI scripting: MusicKit helper app? A
  Shortcuts action that accepts a catalog item? URL parameters? Start from
  [what we know](research/apple-music-catalog-playback.md).
- What's the cheapest, sturdiest menu bar presence? (SwiftBar plugin vs. a tiny Swift app.)
- Packaging Claude OS skills as a Claude Code plugin so they work from any directory.

## Ideas

- `cos net`: Wi-Fi quality, DNS, captive-portal and VPN checks.
- Focus modes via Shortcuts (`cos focus work|off`).
- Time Machine: last backup age as a pulse signal.
- Photo library duplicate report (read-only).
- Mail triage. Privacy-heavy: board review first.

## Done

- v0.1: status, clean, update, music, feeds, journal/friction/memory, daemons, evolve
  plumbing, guard, board, lab.
- v0.2: Claude OS.app, the desktop, Claude chat with Allow/Deny cards, `cos serve`.
- v0.3: Shortcuts music route, old simulator runtimes, trend logging, demo mode.
- v0.4: permissions on request (0003): Music Helper, weather + location, stable signing.
