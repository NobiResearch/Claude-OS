# 0013 — The repository is Claude's

- **Status:** accepted; where its allows live is amended by [0017](0017-stranger-safe-settings.md), and which pull requests get a review by [0020](0020-every-pull-request-gets-a-review.md)
- **Date:** 2026-10-26
- **Decided by:** the human. It supersedes the GitHub parts of [0006](0006-night-shift-pushes.md).

## Context

Law 1 counted pushing to GitHub as outward-facing, so the project's `.claude/settings.json`
had `ask` rules for `git push`, `gh pr create|edit|comment|merge`, `gh api`, `gh issue` and
`cos evolve merge|discard`. The human still got those prompts with
`--dangerously-skip-permissions` on. 0006 approved a few exact command shapes through a
PermissionRequest hook while the Night shift switch was on. Any other shape, such as
`cd … && git push` or a commit message written with a heredoc, still landed on the human's
screen. On the night of 26 October that stalled the night shift. Through the next morning,
merging and opening pull requests kept asking.

The human: "It is YOUR repo. Every gh action should be available … You are ALLOWED to use
github in the Claude OS repo."

## Decision

- **No prompts for GitHub in this repository.** `git`, `gh` and `gh-axi` are allowed. Their
  `ask` rules are gone, along with those for `cos evolve merge` and `cos evolve discard`.
  Claude commits, pushes branches, opens and comments on pull requests, and squash-merges
  them when CI is green.
- **Deleting the repository still asks** (`gh repo delete`).
- **What still protects the human isn't a prompt:**
  - the Guardian's pre-commit and pre-push hooks (0012), which block private data in every
    commit and push;
  - `bin/cos guard --text` on pull request text before it's posted;
  - main's ruleset: squash merges only, and the `test` check must pass;
  - merges pinned with `--match-head-commit`, so what merges is what CI checked;
  - an independent `guardian` agent review of any pull request that changes Claude OS's
    safety files (`cos hook check <PR>` names them) before Claude merges it.
- **Headless daemons still can't push.** The nightly evolve run executes code a model wrote,
  unattended, and nobody looks at it when it runs. `cos evolve merge` from a conversation
  is now allowed.
- **Claude didn't grant this to itself.** Claude Code's auto mode refuses to let Claude edit
  its own permission rules, so the human applied the settings and law changes.

## Consequences

- The Night shift switch no longer gates GitHub in a conversation. Its hook only runs when a
  prompt would show, and git and gh no longer prompt. Removing the switch is left for later.
- The repository is public, so anyone who clones it gets the same freedom in their copy. What
  protects them is the Guardian hooks (`cos doctor` checks they're installed), not a prompt.
