---
name: startup
description: Explain what starts with this Mac (login items, launch agents and daemons, background items) and what's worth a look. Use when the human asks what runs at startup or login, why the Mac is slow to start, about background items, or whether something on their Mac is suspicious.
---

# Startup

## Steps

1. `bin/cos startup --json`. It's read-only: macOS's own login-items list, plus who signed
   each program.
2. **Lead with the answer**: how many things start, and whether anything needs attention.
3. **Items worth a look come first** (`findings`). For each one, say in plain language what it
   probably is (use the name, developer and path; you know most common apps and tools), why
   it was flagged, and what you'd do:
   - *program missing*: left behind by something that was removed; safe to remove the item.
   - *unsigned / ad hoc*: often a developer tool or something the human built (Homebrew
     builds are ad-hoc signed); only worrying if they don't recognize it.
   - *on but unused for months*: a candidate to turn off.
4. Then a short summary of the rest, grouped (apps, launch agents, daemons). No wall of items.
5. **Changing things:** point to System Settings › General › Login Items & Extensions. Removing
   a user launch agent (`launchctl bootout gui/$UID/<label>` plus deleting its plist in
   ~/Library/LaunchAgents) changes the Mac: explain exactly what you'd run and only do it
   when the human says yes. Never touch /Library/LaunchDaemons (needs admin).

## Rules

- Never call something malware without evidence; say what you know and what you don't.
- Item names stay in this conversation: don't write them into the repo or friction.
