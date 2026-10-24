---
name: tidy
description: Answer "do I need to clean up my Mac?" and reclaim disk space safely. Use when the human asks about disk space, storage, a slow or full Mac, caches, or cleaning up.
argument-hint: "[--deep]"
---

# Tidy

## Steps

1. **Look first.** Run `bin/cos status` and `bin/cos clean --json` (add `--deep` if they ask
   for a thorough pass; it also finds stale `node_modules` and files over 2 GB).
2. **Answer the actual question first.** Do they *need* to clean up? Judge it by free space
   (under ~15% or ~30 GB is tight; over ~25% is comfortable), the trend if you know it, and
   what they do (developers accumulate Xcode and package caches fast). Say it plainly in one
   or two sentences.
3. **Show the opportunity** as a short table, biggest first: size, safety, what it is, and
   what it costs them to reclaim it (e.g. "next Xcode build is slower", "simulators lose
   their installed apps").
   - `safe`: recommend these as a bundle.
   - `review`: show the details (e.g. which simulators, which caches) and let them choose.
   - `careful`: list only. Explain how to handle it by hand (Finder, `hf cache`, etc).
4. **Ask** which targets to reclaim. Never apply without a yes in this conversation.
5. **Apply** exactly what they approved: `bin/cos clean apply <id> <id> --yes`.
   The permission prompt will show the human the exact command; that's intended.
6. **Report** what was freed and the new free space (`bin/cos status`).

## Rules

- Never `rm -rf` user folders yourself; go through `cos clean apply`. If a target is
  missing, propose it as friction (`bin/cos friction add "clean: add target for X"`).
- Never empty the Trash or delete downloads without naming them to the human first.
- If they say "just do the safe ones": apply every `safe` target, nothing else.
