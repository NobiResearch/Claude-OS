# 0019 — The name: Ovenbird

- **Status:** accepted
- **Date:** 2026-10-27
- **Decided by:** the owner picked it from the names that passed; the board set the conditions
  (all four seats)

## Context

"Claude" is Anthropic's trademark, and its guidelines don't let a third party put it in a
product's name ([the-name.md](../research/the-name.md)). In January 2026 Anthropic asked the
agent Clawdbot to rename because "Clawd" sounded like "Claude"; reportedly "Clawbot" was
refused too. The owner suggested "CladOS". All four seats voted to rename before the first
release, but not to anything that looks or sounds like "Claude". The worst outcome would be a
second, forced rename just as the project gets attention.

A naming round tested 114 names. Each was checked against GitHub, the Mac App Store, Homebrew
and the .dev/.app registries, and then five research scouts searched the web for AI tools,
companies, trademark hints and meanings. The owner picked Ovenbird. It was clean in every
check: no software, app or company uses it, ovenbird.dev, ovenbird.app, npm and PyPI are free,
and no trademark turned up (from web results only, not a USPTO or EUIPO search). The ovenbird
builds its own home and keeps working on it.

## Decision

- **The project is Ovenbird**, described as "an operating layer for your Mac, built on Claude
  Code". The description is the right place to name Claude: it says what Ovenbird works with,
  and it can change if Ovenbird ever works with other agents, while the name stays.
- **What people see changes:** the app (Ovenbird.app), its menus and windows, the desktop, the
  boot banner, notifications, the README and the docs. A release's code folder becomes
  `~/Library/Application Support/Ovenbird`. That's free to change now, since there has been no
  release.
- **What nobody sees stays, on purpose:** `cos`, `~/.claude-os`, `CLAUDE_OS_*`, the
  `claude-os://` scheme, the bundle and App IDs, the `com.claude-os.*` launchd labels, the
  `ClaudeOS` Swift target and the Info.plist keys. Changing them would mean migrations and new
  macOS permission prompts for nobody's benefit. Don't "fix" them.
- **History stays as written:** the decision records before this one, `changes/`,
  `CHANGELOG.md` and `docs/research/` keep saying "Claude OS".
- **The repository becomes NobiResearch/Ovenbird.** `core.REPOSITORY` and
  `AppConfig.repository` name it. The old name stays in `core.FORMER_REPOSITORIES` and
  `AppConfig.formerRepositories`, so a copy cloned from the old address still counts as this
  repository and stays locked down (`downloaded()`, 0015/0017).
- **Two standing rules, because the old address is trusted forever: never rename or delete the
  NobiResearch organization, and never create a repository named Claude-OS in it.** Either
  would let someone else serve code at github.com/NobiResearch/Claude-OS, which a release
  would then run.

## The switch, in order

1. The owner renames the repository on GitHub (Settings › Repository name), and only the
   repository (the standing rules above).
2. The live checkout's `origin` is set to the new address right away (worktrees share it), and
   this change merges.
3. The owner turns **Keep Ovenbird up to date** back on, because it remembers the exact
   address it follows (0011), so the new `origin` stops it until then.
4. `app/build.sh --install` puts Ovenbird.app in ~/Applications. The owner moves the old
   Claude OS.app to the Trash themselves; no script deletes it. Both have the same bundle ID,
   so macOS's permissions carry over.
5. The README's tour GIF is re-recorded from `docs/screenshots/README.md`.

## Consequences

- Each rename leaves an old address that has to be kept forever. That's why the name had to
  be one we won't be asked to change again.
- The orange diamond stays for now. A mark of its own is a separate decision.
- Claude is still Claude: the chat window and the docs name the model that lives here.
