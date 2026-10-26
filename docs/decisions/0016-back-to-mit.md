# 0016 — Back to MIT

- **Status:** accepted
- **Date:** 2026-10-26
- **Decided by:** the human

## Context

0014 moved Claude OS from MIT to the PolyForm Noncommercial License so that nobody could copy
it and sell it under another name. The human has since set a bigger goal: a project that many
people use and contribute to, the way the most popular open-source agent projects work. Those
are MIT or Apache-licensed, and people still build on the original rather than on copies,
because what they come for is the project itself: its name, its signed app, its maintainers and
its community, not only its code.

A noncommercial license works against that goal. It isn't "open source" in the usual sense,
companies' policies often forbid contributing to it, packagers and directories skip it, and it
turns away the people who would build things on top of Claude OS.

Nobody but the human (and Claude, through the human's account) has contributed yet, so the
license can change without asking anyone else.

## Decision

- **License: MIT**, the same text as before 0014, `Copyright (c) 2026 The Claude OS authors`.
- **Every version is MIT**, including those published under PolyForm Noncommercial between
  0014 and this decision: the authors grant MIT for them too.
- **Contributions** come in under MIT (CONTRIBUTING.md), and contributors keep their copyright.
- The rest of 0014 stands: others' pull requests merge only after the human's yes, private
  vulnerability reporting, the contributor kit.

## Consequences

- Anyone may copy Claude OS, rename it and sell it, closed or not. What stays the project's own
  is what a license doesn't cover: its name, the app signed by its maintainers, and where the
  community gathers. A name the project can own matters more now, since "Claude" is Anthropic's
  trademark (0014, 0015's name decision).
- When the project has a legal owner, such as a company, the copyright line can name it.
