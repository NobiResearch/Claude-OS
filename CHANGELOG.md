# Changelog

User-visible changes to Claude OS. Evolve runs add entries under **Unreleased**.

## Unreleased

## 0.4.0 — 2026-10-25

Permissions when the human asks for them ([0003](docs/decisions/0003-permissions-on-request.md)).

- **Settings › Permissions:** "Full Music control" and "Weather", both off by default.
- **Claude OS Music Helper.app:** a tiny helper with its *own* Accessibility grant (started
  with `open`, so Claude OS.app and its chats never inherit it). It presses Music's own
  controls through the accessibility API (no keystrokes, no label matching); `cos music
  play` uses it for catalog songs, then verifies what's playing.
- **Weather:** `cos weather` (Open-Meteo, no key), on the Today panel and in the brief. Pick a
  city, or "Use my location" in the app (CoreLocation, rounded to ~1 km, stays on this Mac;
  the place joins the Guardian's private terms).
- **Signing:** local builds are signed with your own Apple Development identity when there
  is one, so macOS grants survive rebuilds; ad-hoc (loudly) otherwise and under daemons.
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
