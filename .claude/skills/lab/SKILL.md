---
name: lab
description: The research lab. Investigate a question with parallel scouts and turn findings into decisions or roadmap items. Use when the human (or evolve, or the board) asks "is there a better way to…", "what tools exist for…", "how could Ovenbird do X", or wants a topic researched.
argument-hint: "<question>"
---

# The Lab

You run the lab; the `scout` agents do the legwork.

## Steps

1. **Sharpen the question** into one sentence plus what a useful answer looks like (a
   recommendation? a comparison? a working snippet?).
2. **Split it** into 2–3 independent angles. Example, "can Ovenbird control Spotify too?":
   (a) official APIs and auth on macOS, (b) AppleScript/URL-scheme support today,
   (c) how other open-source tools do it.
3. **Dispatch** one `scout` per angle, in parallel (one message, several Agent calls). Give
   each the angle, what's already known (from `docs/lessons.md`, `docs/research/`), and the
   answer shape you want back.
4. **Synthesize**: the answer, the evidence, the confidence, and the recommendation. Mark
   anything unverified as such. Never present a scout's guess as fact.
5. **File it**: write `docs/research/<slug>.md` (public; no personal data), and add concrete
   follow-ups to `docs/roadmap.md` under "Ideas" or "Next" as appropriate. In interactive
   mode, ask before editing files.

Cheap first: if one quick search answers it, skip the scouts.
