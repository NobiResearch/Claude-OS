# 0011 — Catching up with main

- **Status:** accepted
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

## Decision (part two)

- **Keep Claude OS up to date**, a switch in Settings › Permissions: off by default, turned
  on only in Claude OS.app's native dialog (like Night shift), off in one click. `cos config`
  refuses to turn any `autonomy.*` switch on, so the dialog is the only way, Night shift's
  included. Turning it on pins origin's URL; if origin changes later, it only reports.
- With it on, `evolve.auto_catch_up` fast-forwards only where no old code is loaded:
  - when Claude OS.app's server starts, before any of the server is imported; if it moved,
    `cos serve` starts again on the new code (`os.execv`, once);
  - in a terminal session's boot, while the app isn't running;
  - in pulse, while the app isn't running.
  The app's chat sessions only report.
- **Update** in the desktop's menu bar appears when a restart would help: the checkout moved
  since the server started, or the switch is on and changes are waiting. It restarts only
  the server, after a confirm: the server exits with status 75, which Claude OS.app takes as
  planned (no crash count, no alert), and the new server catches up as it starts. Music
  keeps playing; the player lives in the app. A browser's `cos serve` can't be restarted
  this way, so it never offers it.
- The next session's banner says once what came in ("↑ Claude OS caught up with main"),
  and names the gate's files if they changed.

## Not changed

`hook.clean_main` still compares the live checkout with `origin/main` two ways, so a
checkout that lags behind a change to the gate stops the night shift's merges. The Skeptic
called that a bug. The chair kept it: the gate that decides must be main's gate, and
catching up makes the lag short.

## After an independent review (26 October)

Fixed before the switch was first turned on:

- `cos config` turns an `autonomy` switch off and nothing else; setting the whole group (or
  the pinned URL) was a way around the native dialog. A non-dict `autonomy` no longer
  crashes the server's start, and nothing around the catch-up can keep the app from its server.
- Only Claude OS.app's own server catches up at its start (`--exit-on-stdin-eof`, not from a
  chat), and never while another server runs. Every `cos serve` holds a shared lock for its
  life, so boot and pulse don't move code under a browser's server either (`code_in_use`).
- The commit everything is decided about is resolved once and is the one merged, under a
  lock taken before the checks; a server about to start waits for a move in progress and
  records the commit it loads before importing anything.
- A move that failed for a commit isn't offered again (no endless Update) until the human
  asks (`cos update apply claude-os --yes`).
- A pgrep error and a git error about where commits came from count as "can't tell", never
  "safe"; the one-time "caught up" line survives two sessions booting at once and isn't used
  up by a background job; git also runs with submodules and fsmonitor off.

## Part three: the server keeps the code it started with (26 October)

Friction #21: the live checkout moves after merges (Claude pulls it, `cos update apply`, the
switch at a boot or pulse) while Claude OS.app's server runs, and the server's routes import
their modules lazily, so it ran new modules beside old ones until the human clicked Update.

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend (A) | Pin the code at start: import every module (`pkgutil`, no hand-kept list) and serve `ui/` from memory. An idle restart belongs in the server, once per target. |
| Guardian | amend | Restarting onto code on disk is fine; onto what's waiting on GitHub while the app is open goes past what the switch's dialog promised. A restart cuts off a running job, the manual Update too. `auto_catch_up`'s why never reached the cache, so Update could be offered forever. |
| Steward | amend (A) | Wants no click, with the switch, idle by what the human did (not the page's polls), never losing a conversation, invisible. |
| Skeptic | amend | Pinning fixes correctness for a few lines; the restart is a convenience. Don't build it before the human says the click bothers them, and never reap a chat to make it fire. |

**Decided, now:**
- `cos serve` imports every Claude OS module before it serves (`server.pin_code`, ~50 ms) and
  reads `ui/` into memory (`server.read_ui`, regular files only, up to 5 MB each): the server
  stays one version, whatever moves the checkout. Jobs and new chats run the code on disk, as
  friction #16 wants. Nothing in either can keep the app from its server.
- Update refuses while a job runs (409, "… is still running; Update when it's done"). Once a
  restart is certain, `app.restarting` is set under a lock: no job starts and every POST
  answers 503 while the chats close.
- `auto_catch_up` caches its why, so a catch-up that can't happen isn't offered.
- Pulling the live checkout by hand runs with hooks off (`git -c core.hooksPath=/dev/null pull
  --ff-only`): its hooksPath is `githooks/`, and a merged commit could add a hook. CLAUDE.md
  says so (the human's go-ahead, 26 October).

**Deferred**, and the human agreed (26 October): the server restarting itself when idle. Once
many people contribute and merges come often, someone who only uses Claude OS should take new
code when they click Update, not whenever it merges. If it's ever built: only the app's
server with the switch on, zero chat sessions (never reaped for it), no job, no request from
the human for some minutes (polls don't count), at most once per (loaded commit, target),
journaled with the way back. Restarting onto what's waiting on GitHub needs the switch's
native dialog to say "while the app is open and idle", asked again.
