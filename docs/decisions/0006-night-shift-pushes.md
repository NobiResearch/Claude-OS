# 0006 — Night shift: Claude pushes its own branches while the human sleeps

- **Status:** accepted
- **Date:** 2026-10-25
- **Decided by:** the board (fifth meeting), on the human's request

## Context

The human leaves the Mac on overnight and asks Claude to keep building Claude OS: work in a
worktree, test, push a branch, open a pull request, wait for CI, squash-merge. The first
night, one `git push` waited on a permission prompt from 03:07 to 07:51. The human called it
"a real blocker on night shifts". The cause is the repository's own
`ask: Bash(git push*)` rule, in place since 0.1. In Claude Code, ask rules always prompt,
even in auto mode. An allow rule in `settings.local.json` can't override them, because deny,
then ask, then allow apply across every settings file. Auto mode's classifier would
otherwise allow feature-branch pushes, and `gh pr merge` already ran without a prompt. The
GitHub ruleset on `main` requires a pull request, a passing `test` check and a squash merge.

This partly reverses 0001's "evolve never pushes". That still holds for the evolve daemon,
which never pushes. The night shift is an interactive session the human started.

## Votes

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | Right layer: a deterministic hook next to `cos boot`. Reuse `evolve.guard_branch`, and keep the toggle out of the requester's reach. |
| Guardian | amend | The push is the moment things go public. Check every commit and message with main's own code, and refuse branches that touch the gate. |
| Steward | amend | It removes the biggest blocker and adds no pings. Show the night's pushes in the morning brief. |
| Skeptic | amend | Not over-built compared with deleting the rule. Exit code 2 means deny, so fail closed and quietly. Write this record. |

**Approved, with conditions.**

## Decision

The public `ask: Bash(git push*)` stays, so anyone who clones still gets asked. A
`PermissionRequest` hook, `bin/cos hook permission`, answers the prompt instead of the human
only when **all** of these hold:

1. **Night shift is on.** `autonomy.night_shift` in `~/.claude-os/config.json` is off by
   default. The human turns it on in Settings › Permissions, where the app's per-launch token
   makes the click theirs, or with `cos config`, which asks. Claude may not edit that file
   (deny rules on Edit and Write), and CLAUDE.md tells it never to flip the switch.
2. **The command is exactly `git push [-q|--quiet] -u origin night/<name>`.** It runs on its
   own. Anything outside `[A-Za-z0-9._/ -]` is refused, so there are no quotes, `$`, `;`,
   `&`, `|`, redirections, globs, `:`, `+`, `@` or newlines. That leaves no `-c`, `-C`, env
   prefixes, refspecs, force, delete, tags or push options. The branch must be `night/…`, and
   can't be `main` or `master`, end in either, or contain `..`.
3. **It's this repository**: the same git directory as the live checkout. The push URL must
   equal the fetch URL, which catches `pushurl` and `pushInsteadOf` redirects, and it must be
   a plain GitHub remote.
4. **The Guardian passes**, using main's own code. The hook runs from the live checkout, never
   from the branch. It scans every commit in `origin/main..branch`, its files and its message.
5. **The branch leaves the gate alone.** It must not touch `.claude/`, `.github/`, `githooks/`,
   `bin/`, `CLAUDE.md`, `etc/daemons.json`, `lib/cos/guard.py`, `lib/cos/hook.py` or
   `lib/cos/daemon.py`. Those changes wait for the human. The night shift checks first with
   `cos hook check <branch>` and leaves such a branch for the morning, so it never stalls on a
   prompt nobody can answer.
6. **It's not a daemon**, meaning `CLAUDE_OS_DAEMON` is unset.

Any doubt, error or timeout prints nothing, so the human's normal prompt appears. The hook
always exits 0, and its settings entry ends in `|| true`, because for this hook exit code 2
means deny. Every push it approves, and every push prompt it lets through, goes in the
journal. The morning brief lists the night's pushes.

## Not chosen

- **Deleting the ask rule.** It's one line, but it hands the decision to an opaque classifier
  for every clone, day and night.
- **Headless `dontAsk` night shifts.** These also need the ask rule gone, and they lose the
  interactive session.
- **`bypassPermissions`.** It skips everything.
- **A `pre-push` git hook as the main safety.** It runs the branch's own copy of the guard,
  which the branch can change. The permission hook runs main's copy. A pre-push hook would
  still help pushes the human approves; it's on the roadmap.
