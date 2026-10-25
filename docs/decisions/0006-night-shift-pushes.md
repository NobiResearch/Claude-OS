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

## Amendment, 2026-10-25 (weekly board)

The first weekly meeting found a gap in condition 5. The hook runs main's own code, but a
night shift also merges its own pull requests. A branch that loosened `core.py`, `cli.py`,
`evolve.py` (which holds `guard_branch`) or `server.py` (which flips the switch) could be
pushed and merged one night, and then the next night's checks would run on the loosened
code. Those four files are now protected too, so changes to them wait for the human. Most
night work still goes ahead: subsystem modules, the desktop (`ui/`), the app (`app/`), docs
and tests.

## Second amendment, 2026-10-25: push anything, merge the safe ones

The first amendment protected more files, and the human saw the cost straight away. Most
features touch `core`, `cli` or `server`, so most night work couldn't even be pushed, and
13 of the last 17 pull requests would have waited on the Mac until morning. They asked:
"maybe allow pr, and i can allow merges in the morning?" The board agreed that pushing
was the wrong place for the check. A push publishes, which the Guardian answers. A merge
is where code starts to run, so that's where the safety files belong.

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | Right split: privacy at the push, integrity at the merge. Pin the commit, read the files from local git, and make the protected list honest. |
| Guardian | amend | Pushing protected work is low-risk, but `.github/` must stay unpushed: a workflow can give itself a write token and merge pull requests. Today's check could be dodged by renaming a file. |
| Steward | amend | It unblocks nearly every night. Keep mornings light: one list, plain words, a small pile, and flag only the PRs that touch the safety checks. |
| Skeptic | amend | It's a tripwire, not a wall: one GitHub login, and several spellings slip past prefix rules. Write that down. No network calls the night can stall on. |

**Approved, with conditions.** The gaps the board found in the push check were fixed first,
in their own pull request (#30): renames, `lib/` shadowing, a failed diff read as "no
changes", and the hook running from something other than a clean main.

**Decision.**
1. **Pushing** a `night/*` branch no longer depends on which files it changes, except
   `.github/`. CI runs a branch's workflow on push, and a workflow can declare its own
   write token, so CI changes stay local for the human. Every other condition holds: the
   exact command, same repository, a plain GitHub remote, the Guardian on every commit and
   message, a clean main, and not a daemon.
2. **Merging is the gate.**
   - `gh pr merge`, `gh-axi pr merge`, `gh api`, `gh-axi api`, `gh alias set`,
     `gh extension install`, `gh stack` and `git -C|-c … push` now ask.
   - The hook approves exactly `gh pr merge <N> --squash --delete-branch
     --match-head-commit <sha>`, and only when all of these hold:
     - the PR is an open, non-draft PR of this repository, from `night/*` into main;
     - its head is that commit, and so is the local branch's;
     - every check finished green, `test` included;
     - local git (`--no-renames`) shows it touching no protected path;
     - the Guardian passes its commits and its title.

     It makes one `gh pr view` call, with a 15-second limit, and fails closed.
   - Read-only `gh api <path>` calls are let through.
   - `cos hook check <PR>` gives the same answer and prints the command to merge with, so
     the night shift merges only what it checked and leaves the rest open.
3. **What counts as protected** at merge:
   - the gate files from before;
   - `lib/cos/__init__.py` and `lib/cos/chat.py` (the app's Allow/Deny path);
   - anything in `lib/` outside `lib/cos/`, which would shadow the standard library;
   - `__pycache__/`, `*.pyc` and `*.pth`.
4. **CI's token is read-only** (`permissions: contents: read` in `test.yml`), whatever the
   repository default.
5. **Mornings.**
   - `cos evolve` and `cos hook check` list the night's open pull requests and what each
     waits for.
   - The brief shows one "Waiting for your merge" list in plain words and marks only the
     PRs that touch the safety checks themselves.
   - Each night branch starts from `origin/main`, and at most 3 wait at a time.
   - The human merges on GitHub, or says "merge them" in a session and approves each merge.

**A tripwire, not a wall.** Claude uses the human's own GitHub login, and GitHub's ruleset
can't tell the two apart. These rules stop drift and honest mistakes, not a compromised
session. Spellings they don't catch include:
- `gh` run by its full path, or through `command`;
- a script run with `python3 -` that calls the API;
- any new wrapper.

CLAUDE.md's law 1 forbids merging any other way.

**Daytime.** The Night shift switch is a setting, not a clock. While it's on, ordinary pull
requests merge without a prompt. A pull request that touches the gate prompts twice: once
to push it, once to merge it. The human accepted that.

**Not yet.** Merging the whole morning queue with one approval. A native confirmation for
turning Night shift on: the desktop page itself can call that endpoint, so a merged change
to `ui/` could flip it. A Guardian scan of pull request bodies before they're published
(titles are scanned at merge).
