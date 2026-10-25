# 0008 — One switch: turning the firewall on

- **Status:** accepted
- **Date:** 2026-10-25
- **Decided by:** the board, from friction #8

## Context

The human saw "firewall is off" in the desktop and asked the chat to turn it on. There was
no syscall for it, so the chat improvised `osascript … with administrator privileges`. It
worked after one password dialog, and the chat logged friction #8. macOS ships with the
firewall off, so everyone who runs Claude OS sees that note and has no way to act on it.

## Votes

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | A fixed admin command is mechanics, so it belongs in a syscall shaped like `clean`/`clean apply`. Firewall only, and the posture reader moves next to it. |
| Guardian | amend | Claude OS's first code that runs as root must be protected and use fixed literals. The dialog should name Claude OS, a cancel is detected by its number, and the state is checked afterwards. Never FileVault (its recovery key would land in transcripts). |
| Steward | amend | It happened once and is fixed. Asking for the Mac password should stay rare and only happen when the human starts it. A button that asks the chat beats a new route. |
| Skeptic | amend | Over-built for one occurrence. Gatekeeper's global switch is gone from spctl since macOS 15. If anything, the firewall only, and no server route that runs root code. |

**Approved, with conditions.** The seats split two and two on a syscall versus only a recipe
and links. The chair chose the smallest syscall, the firewall only, because the improvised
version is what the friction was about. It follows every safety condition.

## Decision

- **`cos security`** (read-only) shows FileVault, SIP, the firewall and Gatekeeper: what
  each does, and how to turn it on. FileVault and Gatekeeper get their System Settings
  path, SIP gets the Recovery steps. `status` reads the posture through this module.
- **`cos security on firewall --yes`** is a mutation.
  - It's written canonically, has ask rules, is refused in daemons and is journaled.
  - It refuses by itself under `CLAUDE_OS_DAEMON` or `COS_SANDBOXED`.
  - It runs one complete literal through `/usr/bin/osascript`, with a 120 s AppleScript
    timeout: `socketfilterfw --setglobalstate on`, with the prompt "Claude OS wants to turn
    on the macOS firewall."
  - There's no `off`, nothing is ever filled into the script, and argparse only accepts the
    names in `SWITCHES`.
  - It reads the state again afterwards and trusts that, not the exit code. A cancel is
    error -128, whatever the system language. "Accepted but still off" means the Mac is
    probably managed by an organization.
- **Protected.** `lib/cos/security.py` is on the night shift's protected list, and it
  imports nothing but `core`.
- **The desktop.** The Security card shows "Turn on the firewall…" only while it's off.
  The button asks the chat, so the Allow card and the password dialog both still happen.
  There's no server route that runs root code.
- **A registry test** checks that every mutation in `cli.MUTATING` has an ask rule (except
  opening and installing Claude OS's own app) and is denied to daemons.

## Not chosen

- Gatekeeper and stealth mode switches.
- Any FileVault or SIP command.
- A server route that runs the command from a button.
- A general "run as admin" helper.
