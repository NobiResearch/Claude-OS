# 0001 — Founding architecture

- **Status:** accepted
- **Date:** 2026-10-24
- **Decided by:** the founder (Claude), before the board existed. The board may revisit any
  of this through `/board`.

## Context

Claude OS was given a blank repository, full creative freedom, and a Mac. The repository is
public. The goal: an operating layer Claude thrives in, that makes its human's life on the
Mac better, and that improves itself over time.

## Decisions

1. **Claude Code is the kernel.** No custom agent runtime. Claude Code already provides
   tools, permissions, hooks, skills, subagents and headless mode; Claude OS is
   configuration and syscalls on top. *Why:* the best runtime for Claude is the one built
   for Claude, and it keeps improving without us.
2. **Syscalls are deterministic Python (3.9+, stdlib only).** *Why:* macOS ships Python 3.9,
   so there's nothing to install; deterministic code is testable; judgment stays in skills
   where Claude is strong. Bash was rejected for parsing-heavy work; Swift for startup cost.
3. **Read-only by default, explicit to mutate.** Mutations need named targets and `--yes`,
   are journaled, and are gated by `ask` permission rules so the human sees the exact
   command. *Why:* the human is root.
4. **Private state lives outside the repository** in `~/.claude-os`, enforced by a
   pre-commit guard and a test. *Why:* the repository is public.
5. **LLM daemons are opt-in; the free daemon is on.** `pulse` installs by default; `morning`,
   `evolve` and `board` spend the human's Claude usage, so they wait for the human to
   enable them. *Why:* autonomy is earned, and cost is the human's call.
6. **Self-improvement happens on branches in separate worktrees, never on main and never
   pushed.** *Why:* compounding small improvements is the goal, but the human reviews what
   ships, and their checkout is never disturbed.
7. **A board with a veto.** Four seats with different mandates (fit, safety, value,
   restraint) and the Guardian can block. *Why:* a system that changes itself needs
   deliberate friction against bloat and risk.

## Consequences

- Claude OS only works fully on macOS with Claude Code installed.
- Catalog music playback is best-effort until a better route is found (see roadmap).
- Every new capability starts life as a syscall plus a skill, which keeps the surface
  small and the mechanics testable.
