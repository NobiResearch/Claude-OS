# 0017 — Settings that are safe for strangers

- **Status:** accepted; it merges after the human has moved their own allows
- **Date:** 2026-10-26
- **Decided by:** the board (four seats, F first for three of them; the Guardian makes it a
  gate for the first public release)

## Context

0013 gave Claude GitHub in the human's own repository by allowing `git *`, `gh *` and
`gh-axi *` in the checked-in `.claude/settings.json`. That file is what everyone who clones
Claude OS, or downloads its app (0015), runs. For them, `Bash(git *)` lets a prompt-injected
Claude (one line in a feed headline or a web page is enough) run anything without a card:

- `git -c alias.x='!cmd' x` or `-c core.pager=…` run any command;
- `git -C ~/other/repo clean -fdx` or `reset --hard` destroy work outside the Trash;
- `git config --global` changes their git;
- `git clean -fdX` deletes a download's gitignored deny list.

`gh *` acts with their own GitHub login (`gh api -X DELETE …`), and `python3 -m unittest *`
runs code from any folder. A download's `settings.local.json` denies `gh` and `git push` only.

## Decision

- **The checked-in settings are safe for a stranger.** They allow without a card only Claude
  OS's own syscalls (read-only unless `--yes`; the mutating ones ask) and a few read-only
  system commands (`sw_vers`, `pmset -g`, `mdfind`, `shortcuts list`). No `git`, `gh`,
  `gh-axi` or `python3 -m unittest`: those show a card, and the person decides. The `ask`
  rules for releases, notarization and deleting the repository stay.
- **The owner's freedom moves to their own gitignored `.claude/settings.local.json`:**
  `git *`, `gh *`, `gh-axi *` and `python3 -m unittest *`. 0013 stands for the human's own
  repository, and nothing changes for them. Claude doesn't write its own allow rules: the
  human applies them, before this change merges, so the night shift never starts asking.
  Anyone can do the same in their own fork (CONTRIBUTING.md says how).
- **A download's deny list comes back.** `system.keep_download_settings` puts
  `core.DOWNLOAD_DENY` (the app's list, checked by a test) back into a downloaded copy's
  `settings.local.json` whenever Claude OS starts (`cos boot`, `cos serve`), keeping rules the
  person added.
- **The night shift's hook approves nothing while the switch is off, or in a downloaded copy.**
  Before, it let read-only `gh api` calls and Guardian-checked pull request text through
  whatever the switch said, which for a stranger's clone would have meant `gh` without a card.
  The owner never needed that: their own `gh *` allow means the hook doesn't fire for them.
- **`cos app` on its own** (it builds and installs the app) asks, like `cos app install`.
- **A test holds the line.** `test_security.TestStrangerSafeSettings` fails if the checked-in
  settings allow anything outside a vetted list, and in particular any `git`, `gh`, `python`,
  `sh`, `bash` or `curl` rule.

## Consequences

- People who clone Claude OS to work on it see a card for `git` and `gh`, the safe default.
  CONTRIBUTING.md shows how to allow the narrow ones in their own fork.
- The background jobs aren't affected: each runs with its own explicit `--allowedTools`.
- `keep_download_settings` never loses a person's file: one it can't read is moved aside
  (`settings.local.json.broken-<time>`), and one that's a link is left alone.

## Known gaps, before the first public release

- `Bash(cos *)` allows every `cos` command, and the mutating ones are caught by `ask` rules,
  a deny list over an open door. Claude Code matches rule strings as written, so an odd
  spelling (two spaces, quotes around a word) might slip past an `ask` (not verified).
  Replace it with an allowlist of read-only subcommands, or a PreToolUse hook that sends any
  mutating `cos` to a card.
- In a stranger's clone, `cos evolve merge <branch> --yes` pushes, opens a pull request and
  merges through its own subprocesses (an evolve branch has to exist first).
- `cos remember` can carry injected text into every boot banner.
