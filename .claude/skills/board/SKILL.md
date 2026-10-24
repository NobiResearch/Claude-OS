---
name: board
description: Convene the Claude OS board (Architect, Guardian, Steward, Skeptic) to decide on a proposal, a design choice, or an evolve branch. Use for any non-trivial change to Claude OS, when the human asks "what does the board think", or weekly ("/board weekly").
argument-hint: "<proposal> | weekly"
---

# The Board

Four seats, one chair (you). The board exists so Claude OS grows deliberately instead of
just growing. You chair: you frame the question, you don't vote, you write the decision.

| seat | agent | asks |
|---|---|---|
| Architect | `architect` | Does it fit the system? Is it the simplest design that works? |
| Guardian | `guardian` | Is it safe, private, reversible? What could it leak or destroy? |
| Steward | `steward` | Does it make the human's life better, noticeably and often? |
| Skeptic | `skeptic` | Why not? What's the cheaper alternative? What breaks? |

## A proposal

1. **Frame it** in a brief: the proposal, the problem it solves (cite friction ids or journal
   evidence), the alternatives you know, and the files involved.
2. **Convene**: spawn all four agents *in parallel* (one message, four Agent calls), each with
   the same brief. Ask each for their seat's verdict in their standard format.
3. **Decide.** Tally the votes. Majority approve → approved; any Guardian `reject` is a veto
   until its condition is met; amendments that two or more seats ask for become conditions.
4. **Record.** Print the minutes: question, each seat's vote and top reason, decision,
   conditions. If the decision changes how Claude OS is built, write
   `docs/decisions/NNNN-<slug>.md` (next number; see existing ones) — and keep personal data
   out of it; the repo is public.

## Weekly review (`/board weekly`)

1. Gather evidence: `bin/cos evolve` (branches waiting) and `bin/cos evolve review <branch>`
   for each, `bin/cos friction --all --json`, `bin/cos log --days 7`, `docs/roadmap.md`, and
   the last minutes in `bin/cos daemon logs board`.
2. Brief the board on: what evolve shipped this week, what friction recurred, what the human
   actually used (journal), and the top 5 roadmap candidates.
3. Each seat ranks the candidates and flags any evolve branch they'd reject.
4. Output minutes ending with **"Priorities for next week:"** — an ordered list of at most
   three items. The evolve loop reads these minutes, so be specific: name files, commands,
   and acceptance criteria.

In a headless run, output only the minutes.
