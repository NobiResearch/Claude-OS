---
name: brief
description: The daily briefing. State of the Mac, what needs attention, and the best of the unread feeds, summarized with taste. Use when the human asks for a brief, a morning summary, "what's new", or "catch me up". The morning daemon runs it headless at 08:00.
---

# Brief

Write a briefing the human would actually want to read with their coffee. Two minutes, no more.

## Gather

- `bin/cos status --json`: vitals and signals.
- `bin/cos update --json` (cached data is fine; don't `--fetch` here).
- `bin/cos feeds --since 24 --json --limit 80`: last day's unread items.
- `bin/cos friction` and `bin/cos evolve`: what the OS itself needs.
- The boot banner's memory: what they care about.

## Write

Plain Markdown, this shape:

```
# Good morning — <weekday, date>

**Mac:** one line. Free space, anything that needs attention (or "all quiet").
**Updates:** one line, only if there's something worth doing.

## Worth your time
3–6 items from the feeds. For each: **title** — one sentence on why *this* human would care,
then the link. Prefer depth over news. Skip duplicates across feeds.

## One more thing
A single delightful item: a surprising idea, a beautiful essay, an xkcd. Optional.

## Claude OS
Only if there's something: an evolve branch waiting for review, or open friction.
```

## Rules

- When you're done, mark the feeds read so tomorrow starts fresh: `bin/cos feeds mark-read`.
- In a headless run (the boot banner says "headless daemon run"), output only the brief:
  no questions, no preamble. Your output is saved and the first line becomes the
  notification, so make the first line the greeting.
- Interests in memory beat generic newsworthiness. If you learn what they skip, remember it.
