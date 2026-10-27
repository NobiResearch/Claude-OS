# Architecture

Ovenbird doesn't replace macOS. It's a layer that makes the Mac legible and operable by
Claude, and makes Claude useful to the person who owns the Mac. The kernel is Claude Code;
everything here is what that kernel boots into.

```
                 you ── "find me a chill song" / "do I need to clean up?"
                  │
          ┌───────▼────────┐   CLAUDE.md (the kernel: laws, syscall table)
          │  Claude Code   │◄─ SessionStart hook: `cos boot` → vitals, signals, memory
          │  in this repo  │   status line: `cos statusline`
          └──┬─────┬────┬──┘
     skills  │     │    │  agents
  ┌──────────▼┐  ┌─▼────▼──────────────────┐
  │ /music    │  │ board: architect,       │
  │ /tidy     │  │   guardian, steward,    │
  │ /update   │  │   skeptic               │
  │ /brief    │  │ lab: scout × n          │
  │ /board    │  └─────────────────────────┘
  │ /lab      │
  │ /evolve   │
  └─────┬─────┘
        │  bin/cos <syscall>   (deterministic, read-only unless --yes, journaled)
  ┌─────▼──────────────────────────────────────────────────────────┐
  │ lib/cos: status · clean · updates · music · feeds · mem ·      │
  │          daemon · evolve · guard · shell · system · core       │
  └─────┬───────────────────────────────┬──────────────────────────┘
        │ osascript, sysctl, brew,      │ ~/.claude-os  (private, never in git)
        │ xcrun, softwareupdate, …      │   journal/ friction.json memory.md
        ▼                               │   cache/ runs/ worktrees/ config.json
      macOS                             ▼
                              launchd: com.claude-os.{pulse,morning,evolve,board}
```

## The desktop

```
 Ovenbird.app (app/, AppKit)          cos serve (lib/cos/server.py, 127.0.0.1 only)
 ┌───────────────────────────┐  READY  ┌─────────────────────────────────────────────┐
 │ window: WKWebView ────────┼── http ─▶ ui/  (menu bar, dock, windows, apps)       │
 │ status item, ⌃⌥Space      │  token  │ /api/*  → syscalls (reads) and jobs (cos … --yes)│
 │ child process + stdin pipe┼────────▶│ /api/chat → chat.Session ──stdin/stdout──▶ claude -p
 └───────────────────────────┘         │            can_use_tool ⇄ Allow/Deny card      │
                                       └─────────────────────────────────────────────┘
```

`claude-os://` links that change something (play, rate, permission prompts) carry the
launch's nonce from `~/.claude-os/state/app.nonce` (0600); the app refuses them otherwise,
so a web page or feed link can't make Ovenbird act. The app launches `cos serve --exit-on-stdin-eof`; the server generates a token and prints it
only on its READY line, to the pipe the app owns, so other processes can't read it from
`ps` or the environment. The web desktop sends it as a header on every API call. A human
click on Reclaim/Upgrade/Merge is the approval: the server runs the same `cos … --yes`
command a terminal would, as a background job, and journals it.

Claude sessions are `claude -p --input-format stream-json --output-format stream-json
--permission-prompt-tool stdio` in this repo. Pre-approved tools (read-only syscalls) just
run; everything else arrives as a `can_use_tool` control request, becomes a card in the
chat, and the human's click goes back as the `control_response`.

## Layers

**Syscalls** (`lib/cos/*.py`, exposed as `bin/cos`). Mechanics only: measure, list,
play, fetch, parse. Each is fast, stdlib-only, never raises on a missing tool, has a
timeout on every external call, prints human text by default and JSON with `--json`.
Anything that changes the machine needs explicit targets plus `--yes`, and writes a
journal entry.

**Apps** (`.claude/skills/*/SKILL.md`). Judgment: how to answer "do I need to clean up my
Mac?", how to pick a song for a mood, how to triage updates. Skills call syscalls; they
don't reimplement them.

**Colleagues** (`.claude/agents/`). The board (four seats with distinct mandates, the
Guardian holding a veto) decides how Ovenbird changes. The lab's scouts research questions
in parallel.

**Daemons** (`etc/daemons.json` → launchd). `pulse` is plain Python and keeps caches warm
so boot and the status line stay instant; it also fetches main and notes what's merged on
GitHub but not on this Mac (decision 0011); with Keep Ovenbird up to date on, it also
fast-forwards while the app is closed. Boot's one network call is that same fetch, at
most every 10 minutes. The LLM daemons (`morning`,
`evolve`, `board`) run headless Claude Code with an allowlist, a deny-list no definition
can override (`ALWAYS_DENIED`) and a timeout. They're opt-in. A budget cap applies when
Claude is billed per token (an API key); on a Pro or Max plan the timeout is the limit.

Defense in depth for headless runs, strongest first:

1. `cos` itself refuses every mutating command when `CLAUDE_OS_DAEMON` is set, however the
   command is spelled (`cli.check_mutation`).
2. Evolve's shell runs in Claude Code's sandbox (writes confined to its worktree, no
   network), and the tests it wrote run under `sandbox-exec` with a throwaway `HOME`.
3. `cos evolve merge` re-runs the Guardian over the branch and its tests before
   fast-forwarding, so nothing reaches `main` unchecked, whatever happened during the run.
4. No daemon gets web access: they read untrusted text (RSS), so they get no way to send
   anything out.
5. Tool allow/deny lists and permission `ask` rules.

**Memory** (`~/.claude-os`). The journal records what happened; friction records what went
wrong; memory records who the human is. Boot shows the latter two to Claude every session.

## The improvement loop

```
 friction ──┐                      ┌──► evolve/<date> branch (own worktree)
 journal  ──┼──► nightly /evolve ──┤        tests + guard must pass
 roadmap  ──┤      (one change)    └──► notification ──► human: cos evolve review/merge
 board ─────┘                                                    │
   ▲  weekly /board: what shipped, what recurred, top 3 next ◄───┘
```

Evolve never pushes, never merges, never touches the human's checkout. Merging an evolve
branch closes the friction items its commits name.

## Privacy model

The repository is public; the human's life is not. Rules, in order of enforcement:

1. State lives in `~/.claude-os` (mode 700), outside the repository.
2. `.gitignore` excludes the usual suspects anyway.
3. The Guardian pre-commit hook (`cos guard`) blocks private files, credentials, API keys,
   this user's home path and git email, machine-generated commit emails
   (`you@Your-Mac.local`, which leak your login and computer name), plus any extra terms
   listed in `~/.claude-os/guard.json` (`{"extra": ["…"]}`).
4. The pre-push hook (`cos guard --push`) runs the same scan over every commit a push would
   publish that the remote doesn't have yet, one by one, root commits and merges included,
   with its message, plus an annotated tag's tagger and message, and blocks any author,
   committer or tagger address that isn't GitHub's noreply. A push it can't check doesn't go out.
5. A test (`test_repository_is_clean`) runs the same scan over the whole tree.
