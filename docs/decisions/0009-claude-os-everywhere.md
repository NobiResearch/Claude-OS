# 0009 — Claude OS everywhere: four Mac skills in any folder

- **Status:** accepted
- **Date:** 2026-10-25
- **Decided by:** the board, on the human's request ("proceed with claude os everywhere to the board")

## Context

The human works in about a dozen other project folders. To ask for music without leaving a
work session, Claude OS's skills had to load outside its own repo. The research
([claude-code-plugin](../research/claude-code-plugin.md)) suggested a plugin with the repo
root as plugin root.

## Votes

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | Never make the repo root a plugin root: every default component path would load everywhere. Keep repo-owned runs (the 08:00 brief, the app's buttons) independent of the human's install. |
| Guardian | amend | Code that loads in every session must be protected; outside the repo there are no ask rules. Friction from client work must not reach public commits, and the brief must not pull the human's data into work sessions. Uninstall must undo it. |
| Steward | amend | Music is what they'd use from work. Skills that fire by mistake in work sessions cost more than a missing one: narrow the descriptions, test the phrasings, nothing about them in work sessions unless asked. |
| Skeptic | amend | Most of it already exists (`cos` is on PATH). Moving the skills out of `.claude/` loosens the night-shift gate and breaks the 08:00 brief. Cheapest: links in `~/.claude/skills`, if Claude Code follows them. Test first. |

**Approved, with conditions.** Three seats asked for a test first. With the human's yes, it
ran on this Mac with a throwaway probe skill:
- a link in `~/.claude/skills/` loads in a session outside the repo;
- it reads edits live (`PROBE-v1` became `PROBE-v2` with no reinstall);
- a link to one of the repo's own skills appears only once inside the repo.

So the cheapest design works, and there's no plugin.

## Decision

1. **`cos install` links four skills** into `~/.claude/skills/`: `music`, `tidy`, `update`
   and `startup`. They stay in `.claude/skills/`, where the night shift can't change them
   unseen, and load live from the checkout.
   - `brief`, `board`, `evolve` and `lab` stay repo-only, so the 08:00 brief and the app's
     buttons don't change.
   - Install never replaces a skill of the same name that isn't Claude OS's, and
     `--no-skills` skips this step.
   - `cos uninstall` removes only its own links, and `cos doctor` reports them.
   - `lib/cos/system.py`, which decides what gets linked, is protected.
2. **The skills call `cos`, not `bin/cos`.** Their descriptions say *this Mac* and what
   they're not for: a project's dependencies, cleaning up code, music for a video, a
   project's startup code. A real check with headless sessions in a scratch project
   (`package.json`, shell access off) confirmed it:
   - "update the dependencies", "clean up this codebase" and "background music for my video"
     triggered none of them;
   - "what's outdated on my Mac?", "do I need to clean up my Mac?" and "play some chill
     radio music" triggered the right one.
3. **Privacy.**
   - The skills say that what they remember or log is about the human or the Mac, never the
     project or client at hand.
   - Friction logged from another folder is stored with `"outside": true`, never its path.
     Evolve fixes it without quoting it in commits, `changes/` entries or pull requests.
   - `music` reads `cos memory` only when choosing by taste.
4. **No hooks and no session-start line** in other folders. Every `cos` command outside
   the repo asks, which is the safe default.
5. **The missing ask rules** for `cos app install|open` are added, and the registry test
   now covers every mutation with no exceptions.

## Not chosen

- **A plugin with the repo root as plugin root.** It would put every default component path
  into every session.
- **A plugin in a `plugin/` folder.** Not needed now that links work.
- **A permission hook for read-only `cos` outside the repo.** That's a later decision, if the
  prompts annoy.
- **A session-start signals line.** The pulse notification already covers it.
