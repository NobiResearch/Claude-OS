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

## Consequences

- A guardian agent costs some usage per pull request, never a card or a ping.
- The owner's own merges still need no prompt (0013); the review is Claude's to run.
