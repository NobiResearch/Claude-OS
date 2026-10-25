# 0011 — Catching up with main

- **Status:** accepted (part one)
- **Date:** 2026-10-25
- **Decided by:** the board, from friction #16

## Context

The human merged two pull requests on GitHub, `cos net` among them, and then asked Claude
OS.app's chat "is my internet slow?". The chat runs from the live checkout, which was still
on the old main. It didn't know `cos net` existed, improvised, and logged friction asking for
the command that had just merged. Nothing brings a GitHub merge to the Mac until someone runs
`git pull`, and Claude only did that when it happened to know about a merge.

## Votes

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | A guarded fast-forward is mechanics: one function in a protected file (`evolve.py`), reused by `cos evolve merge`. Any change under `lib/cos/` leaves a running server with mixed versions, not just `server.py`. |
| Guardian | amend | Moving the code is a software upgrade under law 1, and anyone who clones this public repo would get the owner's main. Opt-in through the app's native dialog; GitHub only; no hooks or prompts during git; only over commits GitHub made; say loudly when the gate changes; journal the way back. |
| Steward | amend | Merging several times a day makes this frequent. Boot must never wait on the network for long. Never quit the app on its own; music plays in it. |
| Skeptic | amend | Never swap code under a running server or session. Fetch and report everywhere; fast-forward only where no old code is loaded. |

**Approved, with conditions, in two parts.** Moving the code automatically is part two and
waits for its opt-in switch. Part one reports, and moves the code when the human says so.

## Decision (part one)

- **`evolve.catch_up(apply, fetch, source)`** is the one place that moves the live checkout.
  `cos evolve merge` uses it too, instead of its own `git pull`. It moves only when:
  - the checkout is on main, with no uncommitted changes and no commits GitHub hasn't got;
  - origin is a GitHub URL and no `url.*.insteadOf` rule could send git elsewhere;
  - every incoming first-parent commit has one parent, GitHub as its committer and a
    `(#N)` subject: a squash-merged pull request, which is all main's ruleset allows;
  - it's not a background job (`CLAUDE_OS_DAEMON`, `COS_SANDBOXED`).
- **Git, hardened:** `-c core.hooksPath=/dev/null` (hooksPath is relative, so a merged
  `githooks/post-merge` would otherwise run during the fast-forward), no credential helper,
  `GIT_TERMINAL_PROMPT=0`, `--no-tags --no-recurse-submodules`, `merge --ff-only
  --no-overwrite-ignore`, hard timeouts, and a lock. Never a rebase or a reset.
- **Fetch and report:** the boot banner (not in daemons; at most one fetch every 10 minutes,
  4 s at most) and pulse fetch main and say what's merged and not on this Mac, and name the
  gate's files when they change. Neither moves the code.
- **`cos update`** lists Claude OS as a source, and **`cos update apply claude-os --yes`**
  moves it: an existing mutation, so it asks, it's refused in daemons, and it's journaled
  with the old commit and `git reset --keep <old>` to go back. It says what the running app
  and this session still have loaded (old CLAUDE.md, an app to reopen or rebuild).
- **The desktop** can't apply it yet (`/api/updates/apply` refuses the source): the running
  server would mix versions.

## Part two (next)

An opt-in **Keep Claude OS up to date** switch in Settings › Permissions, off by default and
turned on only in the app's native dialog, like Night shift. With it on, the fast-forward
happens only where no old code is loaded: when Claude OS.app's server starts (before it
serves, then it re-executes itself), in a terminal session's boot, and in pulse while the app
isn't running. Otherwise the desktop shows that an update is ready. The URL is pinned when
the switch is turned on.

## Not changed

`hook.clean_main` still compares the live checkout with `origin/main` two ways, so a
checkout that lags behind a change to the gate stops the night shift's merges. The Skeptic
called that a bug. The chair kept it: the gate that decides must be main's gate, and
catching up makes the lag short.
