---
name: tidy
description: Answer "do I need to clean up my Mac?" and reclaim disk space on this Mac safely. Use when the human asks about the Mac's disk space or storage, a slow or full Mac, its caches, or cleaning up the Mac. Not for cleaning up, refactoring or tidying code or a project.
argument-hint: "[--deep]"
---

> Works from any folder on this Mac ([0009](../../../docs/decisions/0009-claude-os-everywhere.md)). Run syscalls as `cos …`; in the Claude OS folder, `bin/cos …` is the same. Whatever you `cos remember` or `cos friction add` is about the human or this Mac, never the project or client you're working in.

# Tidy

## Steps

1. **Look first.** Run `cos status` and `cos clean --json` (add `--deep` if they ask
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
5. **Apply** exactly what they approved: `cos clean apply <id> <id> --yes`.
   The permission prompt will show the human the exact command; that's intended.
6. **Report** what was freed and the new free space (`cos status`).

## Rules

- Never `rm -rf` user folders yourself; go through `cos clean apply`. If a target is
  missing, propose it as friction (`cos friction add "clean: add target for X"`).
- Never empty the Trash or delete downloads without naming them to the human first.
- If they say "just do the safe ones": apply every `safe` target, nothing else.
