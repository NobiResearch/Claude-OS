# 0020 — Every pull request gets a guardian's review

- **Status:** accepted
- **Date:** 2026-10-28
- **Decided by:** the board (night of 27–28 October), on the outside review's finding F2
- **Amends:** 0013

## Context

Under 0013, Claude merges its own pull requests once CI is green, and only those that touch
the safety files (`hook.PROTECTED`) get an independent guardian review first. The outside
review (Fable 5.1, finding F2) pointed out that the boundary guards the gate, not the code
that touches the Mac. `lib/cos/clean.py`, which decides what `clean apply` deletes, could merge
with no review. So could the desktop (`ui/`), and so could a test that a pull request brings
along to keep CI green.

The board considered widening `PROTECTED` to all code. Two seats said no: `protected()` also
drives what the human sees ("changes Ovenbird's own safety checks" on an update, evolve's
`--reviewed`, the boot banner's "the gate changed"). If those fired on every change, the human
would learn to ignore them. Tests and docs steer the next session too, so "all code" would still
leave gaps.

## Decision

- **Every pull request Claude merges gets a `guardian` agent's review of its diff first.**
  Then CI must be green, and it merges with `--match-head-commit`. That covers docs, tests and a
  one-line fix alike.
- **The hook never merges on its own.** `decide_merge` says a pull request is at best "ready once
  a guardian agent has reviewed it". A stranger's clone with Night shift on gets a card for every
  merge.
- **`cos hook check <PR>` judges the pull request whatever the switch says.** It names the safety
  files the change touches, which the review reads first, and prints the exact merge command.
- **`PROTECTED` and everything it shows the human stay as they are.** It now means "look here
  first", not "the only files that get a review".
- **An evolve branch merges through `cos evolve merge <branch> --yes`, which shows no card in a
  conversation** (0013 removed its ask rule). So Claude runs it only after the human's yes in
  this conversation, or after a guardian agent has reviewed that branch's diff, like any other
  pull request. The desktop's Merge dialog is the human's yes. A branch that changes the safety
  files gets a guardian agent's review even with the human's yes in a conversation, and only
  then merges with `--reviewed`; the desktop's Merge dialog still counts as that review (0013).
  `cos evolve discard` deletes a branch and its workspace, so it runs only on the human's yes.

## Consequences

- A guardian agent costs some usage per pull request, never a card or a ping.
- The owner's own merges still need no prompt (0013); the review is Claude's to run.
- `--match-head-commit` pins the commit CI checked. A fix after the review moves the head and
  gets another look.
- Follow-up: the Night shift switch's own words still promise merges: README's setup line, the
  Settings text in `ui/apps.js` and the app's consent dialog in `Confirm.swift`. They overstate
  what the switch grants, which is the safe direction, and get corrected with the app's next
  rebuild.
