---
name: evolve
description: Improve Claude OS itself. Turn friction, board priorities and roadmap items into one small, tested change. Runs nightly via the evolve daemon ("/evolve nightly"); the human can also run "/evolve" or "/evolve <idea>".
argument-hint: "[nightly | <idea>]"
---

# Evolve

One improvement per run. Small, tested, reversible, explained. The point is compounding:
a thousand small good changes, not one big risky one.

## 1. Orient

- `git log --oneline -15` (what changed recently; don't redo or undo it)
- `bin/cos friction --json` (open friction, the strongest signal). Friction marked
  `"outside": true` was logged from a session in another project (0009): fix it, but never
  quote its text in commits, `changes/` entries, pull request titles or bodies; describe the
  problem in your own generic words and refer to it by number.
- `bin/cos daemon logs board` (latest board minutes; look for "Priorities for next week")
- `docs/roadmap.md` (the "Next" section)
- `bin/cos log --days 3` (what the human actually did; failures are clues)

## 2. Choose one thing

In order: (a) open friction with a clear fix, (b) the board's top priority, (c) the
roadmap's next item, (d) a bug or rough edge you noticed while orienting. It must be finishable
in this session with tests, and touch roughly 300 lines or fewer. If nothing qualifies, stop
and say "Nothing worth changing tonight" without committing anything. That's a fine outcome.

If the change adds a syscall, a daemon, a permission, or touches safety (guard, laws,
`ALWAYS_DENIED`, `ask` rules), consult the board first (spawn the four board agents in
parallel with a short brief) and follow their conditions. A Guardian `reject` means stop.

## 3. Build it

- Follow `CLAUDE.md` ("Working on Claude OS itself"): stdlib only, existing style, tests.
- Add or update tests in `tests/`. Add a line under `## Unreleased` in `CHANGELOG.md`.
- Update docs that the change makes wrong (README, CLAUDE.md syscall table, skills).
- Add a lesson to `docs/lessons.md` if you learned something about macOS the hard way.

## 4. Verify

- `python3 -m unittest discover -s tests` passes.
  Also under macOS's own Python (`/usr/bin/python3 -m unittest discover -s tests`), the
  oldest one Claude OS supports, and `node --check ui/<file>.js` for any JavaScript you changed.
- `bin/cos guard --all` is clean (no personal data anywhere in the repo).
- Run the changed command for real, read-only, and look at the output.

## 5. Land it

- **Nightly** (you're on an `evolve/*` branch in your own clone, inside a sandbox):
  `git add -A` then `git commit -m "<imperative summary>"`, body explaining why, and
  `Addresses friction #N` if it does (merging closes those automatically). Never push,
  merge, or switch branches. Finish with a 2–4 line summary whose first line is the commit
  subject; it becomes the human's notification.
- **Interactive**: show the diff summary and test results, and ask the human whether to
  commit. They're root.

## Never

- Weaken the guard, the laws, the permission `ask` rules, or the daemon deny-list.
- Put anything personal in the repo: the public must learn nothing about this human.
- Add third-party dependencies, or network calls that send the human's data anywhere.
- Mutate the machine (no `clean apply`, `update apply`, daemon installs) during evolve.
