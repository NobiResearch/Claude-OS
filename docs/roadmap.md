# Roadmap

The evolve loop takes work from open friction first, then the board's weekly priorities,
then **Next** (top to bottom). Anyone, human or Claude, can add ideas. Keep items concrete:
what, where, and how we'll know it works.

## Next

0. **Demo mode for the desktop** (`cos serve --demo`): fake vitals, library and feeds, so
   screenshots for the README never show anyone's real machine.

1. **`cos cal`**: today's Calendar events and due Reminders via AppleScript (with timeouts),
   read-only. Add a "Today" line to `/brief`. Accept: works with no calendars, one, many.
2. **Trends in pulse**: append a daily snapshot (disk free, battery health, update count) to
   `~/.claude-os/trends.jsonl`; `cos status` shows a one-line trend ("disk −3 GB/week").
3. **Old simulator runtimes** as a `cos clean` target: `xcrun simctl runtime list -j` sizes,
   delete via `xcrun simctl runtime delete <id>`. Safety: review.
4. **`cos shortcuts`**: `list` and `run <name> [--input text]` bridge to the Shortcuts CLI,
   so the human's own automations become syscalls.
5. **Weather in the brief**: Open-Meteo (no key). Location from `cos config` (private),
   never inferred from IP without asking.
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
