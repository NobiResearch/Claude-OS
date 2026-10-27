# 0018 — What we ask of contributors

- **Status:** accepted
- **Date:** 2026-10-27
- **Decided by:** the board (all four seats: approve with amendments)

## Context

The research on growing the project ([growing-the-project.md](../research/growing-the-project.md))
expects most outside pull requests to be written by agents. Maintainers in a Linux Foundation
survey (October 2026) estimate a quarter of incoming pull requests are low-quality AI output.
Projects that grew well say plainly what they want, where a change belongs and what they turn
down. Hermes Agent's rubric also steers its triage bot.

CONTRIBUTING.md and AGENTS.md already had the house rules and the review process, but no list
of wanted work, no guide to where a change goes, no list of what we turn down, and nothing about
how a change was written. Nobody from outside has contributed yet. Writing this down now beats
writing it in the middle of a stranger's first pull request.

## Decision

- **[AI_POLICY.md](../../AI_POLICY.md)**, short. It opens honestly: Claude writes most of
  Claude OS and its owner answers for it, so contributors answer for what their agents write.
  It applies to pull requests from outside: name the tool and model (no transcripts or session
  links), have run the change and be able to explain it, and write "What and why" in your own
  words, with help with the English welcome. How a change was written doesn't change how it's
  reviewed.
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** gets three sections: "What we want most" (an idea
  issue before anything new), "Where a change goes" (pointing to
  [architecture.md](../architecture.md#layers)), and "What we turn down, even when it's well
  built", with a reason for each item. AGENTS.md gets one paragraph for the agent, and the pull
  request template gets "Written with" and one checkbox.
- **An idea issue comes before the core.** New commands, skills, daemons and desktop features
  start as an idea issue, so the board decides before anyone builds. Bug reports and fixes
  don't need one.
- **The owner closes.** Closing or commenting on someone else's pull request is outward-facing,
  like merging it (0014). Claude drafts a short reason that says what would make the change
  welcome, and posts it after the owner's yes.
- **No triage bot.** No bot, CI job or daemon applies this rubric or reads issue or pull request
  text. Claude applies it only in a conversation with the owner, and `gh` stays in the
  background jobs' `ALWAYS_DENIED`.

## Consequences

- Claude's own pull requests stay under 0013. Their footer says Claude wrote them, and Claude
  never ticks a box that speaks for the human.
- Closing pull requests that address an AI reviewer deters, but it isn't the defense. The
  defense is structural: no token near untrusted text, the owner's yes, and the safety review.
- The rules live in one place each: AI_POLICY.md has what's about AI, CONTRIBUTING.md has the
  rest, and AGENTS.md and the template link to them. If they drift, CONTRIBUTING.md wins.
- Revisit closing when there's enough volume that the owner's yes on each close becomes the
  bottleneck.
