# 0025 — A card for someone else's pull request

- **Status:** accepted
- **Date:** 2026-10-31
- **Decided by:** the human ("yes to all 6"), on Fable's review of 29 October (F1)
- **Amends:** 0014 and 0018, which made that yes a rule

## Context

0014 and 0018 say a pull request from anyone else merges, closes or gets a comment only after
the human's yes. That yes was a rule in CLAUDE.md and nothing else. An outside pull request's body,
comments and diff are read in the owner's session, the one session where `gh` runs with no card,
so text written to steer Claude lands exactly where it could act.

## Decision

`cos hook pretool` looks up the pull request behind `gh pr merge|close|comment|review|edit` and
shows a card when it's from a fork, or by anyone but the signed-in account.

- **Claude's own pull requests show no card.** 0013 stands, so this isn't an ask rule for `gh`,
  which would stop every night.
- **A lookup that fails is a deny, not a card.** A card on a GitHub hiccup could hold a night for
  hours; letting the command through would skip the check. A deny tells Claude why, sends nothing,
  and a retry costs seconds.
- **The command has to name one pull request,** by number or link, or it's denied with the reason.
  A current-branch or branch-name lookup could check a different pull request from the one `gh` acts
  on, for instance after a `cd`.

## Not caught

This is a tripwire, like the rest of the hook. `gh api` writes, `gh issue comment` on a pull
request's number and `gh pr reopen` show no card. CLAUDE.md's rule still covers them.

## Not done

Fable also suggested dropping `python3 -` and `cd *` from the owner's local allows. Those are the
owner's settings and a separate question: dropping `cd *` would put a card on many ordinary commands.
