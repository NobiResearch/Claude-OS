# 0024 — No Night shift switch: nothing approves a prompt for Claude

- **Status:** accepted
- **Date:** 2026-10-30
- **Decided by:** the human ("Yes do them all"), on Fable's review of 29 October (F7)
- **Supersedes:** the switch and its PermissionRequest hook in 0006 and 0023

## Context

0006 added a PermissionRequest hook, `cos hook permission`. With **Night shift** turned on in
the app's own dialog, it approved Claude's `git push -u origin night/*`. 0023 extended it to
the text of Claude's own pull requests, and narrowed it.

Since 0013 the owner's own settings allow git and gh, so for the owner no prompt ever comes
and the hook never ran. In anyone else's clone, git and gh show Claude Code's normal card
(0017), and that card is the right answer for someone else's repository: the switch was a
way to turn it off. What it kept costing was real:
- about 400 lines of command parsing;
- a native dialog, a settings route and a Settings row;
- a section in every review of the safety files.

Fable's review called it dead weight for the owner and a risk for everyone else.

## Decision

- The PermissionRequest hook, the `cos hook permission` command, the Night shift switch
  (`autonomy.night_shift`), its settings route, the app's dialog for it and its Settings row
  are gone. Nothing in Ovenbird answers a permission prompt on the human's behalf.
- What the hook checked before a push stays, as a check Claude runs by hand:
  `cos hook check <branch>` says whether the branch is clean to push. That means:
  - it's a `night/*` branch of this repository;
  - the Guardian has read every commit and message;
  - nothing in `.github/` changes, since CI runs a branch's workflow the moment it's pushed.
  `cos hook check <PR>` still says whether a pull request is ready for its guardian review
  (0020) and prints the exact merge command.
- The PreToolUse hook (`cos hook pretool`, 0017) stays as it is. Its job is different: it
  shows a card, it never approves one.
- An old `autonomy.night_shift` in a config file is ignored. `cos config` doesn't set it either
  way.

## Consequences

- In the owner's repository nothing changes: git and gh were already allowed.
- In someone else's clone, Claude's pushes and pull requests always show a card. Their
  repository, their yes.
- The night shift is still a thing Claude does: a session the human starts before bed. It
  just has no switch.
- Fewer safety files to review. `cos hook check <branch>` before every push is the same gate
  as before, run on purpose instead of from a prompt.
