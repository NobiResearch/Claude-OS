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

`cos hook pretool` looks up the pull request behind `gh pr merge|close|comment|review|edit|reopen`
and shows a card when it's from a fork, or by anyone but the signed-in account. Only a command
that runs `gh` counts: text that names one, in an `echo`, a commit message, a heredoc or a comment,
does nothing.

- **Claude's own pull requests show no card.** 0013 stands, so this isn't an ask rule for `gh`,
  which would stop every night.
- **A lookup that fails is a deny, not a card.** A card on a GitHub hiccup could hold a night for
  hours; letting the command through would skip the check. A deny tells Claude why, sends nothing,
  and a retry costs seconds.
- **A command names one pull request,** by number or link, or it's denied with the reason. So it
  gets one lookup, which fits the hook's 10 s, and a killed hook shows no card.
- **A command that moves first names the repository.** After a `cd` or a `GH_REPO`, `gh` could act
  on another repository's pull request with the same number, so it needs `-R` or a link, or it's
  denied with the reason. A `cd` after `gh` ran moves nothing.

## Not caught

This is a tripwire, like the rest of the hook. CLAUDE.md's rule still covers these, which show no
card: `gh api` writes, `gh issue comment` on a pull request's number, `gh pr ready`, `update-branch`
and `lock`, a flag's number standing in for the pull request (`gh pr comment --body 170`), a
quote inside a word (`g''h`), the human's own pull request in another repository, a wrapper it
doesn't know (`noglob`, `script`, `op run`), `gh` in a function or a `case`, a redirection before
it (`2>/dev/null gh`), and a rarer move (`chdir`, `env --chdir=x`, `sudo -D`).

## Not done

Fable also suggested dropping `python3 -` and `cd *` from the owner's local allows. Those are the
owner's settings and a separate question: dropping `cd *` would put a card on many ordinary commands.
