---
name: brief
description: The daily briefing. State of the Mac, what needs attention, and the best of the unread feeds, summarized with taste. Use when the human asks for a brief, a morning summary, "what's new", or "catch me up". The morning daemon runs it headless at 08:00.
---

# Brief

Write a briefing the human would actually want to read with their coffee. Two minutes, no more.

## Gather

- `bin/cos status --json`: vitals and signals.
- `bin/cos weather --json`: today's weather and any alert, if the human has chosen a place.
- `bin/cos cal --json`: today's events and due reminders, if they've connected the calendar.
- `bin/cos update --json` (cached data is fine; don't `--fetch` here).
- `bin/cos feeds --since 24 --json --limit 80`: last day's unread items.
- `bin/cos friction` and `bin/cos evolve`: what the OS itself needs.
- `bin/cos log --days 1 --kind action`: anything the night shift pushed ("night shift: pushed …").
- The boot banner's memory: what they care about.

## Write

Plain Markdown, this shape:

```
# Good morning — <weekday, date>

**Weather:** one line, only if configured ("13°, light rain later; take a jacket").
**Today:** the day's shape in one or two lines (first meeting, anything unusual, reminders due),
only if the calendar is connected. Never list every event.
**Mac:** one line. Free space, anything that needs attention (or "all quiet").
**Updates:** one line, only if there's something worth doing.

## Worth your time
3–6 items from the feeds. For each: **title** — one sentence on why *this* human would care,
then the link. Prefer depth over news. Skip duplicates across feeds.

## One more thing
A single delightful item: a surprising idea, a beautiful essay, an xkcd. Optional.

## Claude OS
Only if there's something: an evolve branch waiting for review, open friction, or one line
listing what the night shift pushed ("Night shift: pushed night/x, night/y"). Nothing on quiet nights.
```

## Rules

- When you're done, mark the feeds read so tomorrow starts fresh: `bin/cos feeds mark-read`.
- In a headless run (the boot banner says "headless daemon run"), output only the brief:
  no questions, no preamble. Your output is saved and the first line becomes the
  notification, so make the first line the greeting.
- Interests in memory beat generic newsworthiness. If you learn what they skip, remember it
  (interactive only: a headless run can't write memory, since a feed item could be steering it).
- Talk to the human as "you". Don't assume their gender, job, age or anything else memory
  doesn't say; "why you'd care" should rest on what you actually know.
