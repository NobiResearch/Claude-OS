# 0023 — Night shift answers only for its own pull requests

- **Status:** accepted
- **Date:** 2026-10-28
- **Decided by:** the board (night of 28–29 October), on friction #28
- **Amends:** 0006 and 0020

## Context

With Night shift on, the permission hook (`lib/cos/hook.py`) approved three kinds of `gh`
command without a card:
- any read-only `gh api <path>`;
- `gh pr create` with any head and base;
- `gh pr edit` and `gh pr comment` on any pull request number.

It checked the text against the Guardian, but not which repository the command ran in, which
repository gh would talk to, or whose pull request it was, and it journaled none of them.

The owner's own sessions never reach the hook for `gh`, because their local settings allow it
(0013). A stranger's clone with Night shift on has no such rule (0017), so there the hook is
the only thing between Claude and `gh`. A Claude steered by text it read could have:
- read a private repository, or the account's email, with the human's login;
- posted what it read as a comment on someone else's pull request.

The Guardian screens for secrets and the owner's identifiers, not for everything private. The
read approval also answered a prompt a checked-in ask rule exists to show: reading a
repository's releases.

## Decision

- **No `gh api` call is approved.** Night work doesn't need one.
- **Pull request text is approved only for Claude's own pull requests in this repository:**
  - The command runs from a clean checkout of this repository, under the same checks as a
    push.
  - origin is a plain GitHub remote, and it's the only remote.
  - gh's default repository wasn't set by hand, and neither `GH_REPO` nor `GH_HOST` points
    elsewhere.
  - `create` opens a pull request from a `night/*` branch into main.
  - `edit` and `comment` name a pull request of this repository that's open, from a `night/*`
    branch, and not from a fork.
  - The body file is a plain file from the repository, a worktree or the session's temp folder.
  - Nothing outside quotes means something different to the shell than to the hook's parser:
    no `#`, braces, globs, `~` or a word-initial `=`, and the pull request number is plain
    ASCII digits. Before this, `--title x#; <any command>` read as a pull request title and
    approved whatever followed. That was the guardian's finding on this pull request, and it
    was live on main with Night shift on.
  - The Guardian has read the title and body.
- **The hook never answers a checked-in ask rule.** When `.claude/settings.json` can't be
  read, it answers nothing at all, pushes included.
- **Every approval goes in the journal:** what it was ("commented on #31") and the command.
- Otherwise, pushing and merging are unchanged.

## Consequences

- A stranger's Night shift sees a card for a `gh api` read, for another repository's pull
  request, and in a clone with a second remote (a fork's `upstream`). That's the safe
  direction; they can allow what they need in their own `.claude/settings.local.json`.
- The Night shift dialog, Settings and the README no longer say it reads from GitHub with your
  login.
