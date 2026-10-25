---
name: update
description: Keep macOS and installed software up to date. Use when the human asks about updates, outdated packages, dependencies, Homebrew, npm globals, App Store apps, or security patches.
---

# Update

## Steps

1. **Check.** `bin/cos update --fetch --json` (refreshes Homebrew metadata; ~10–60s).
2. **Triage** into three groups and keep it short:
   - **Do now**: macOS security updates, and anything that is a security fix you know of.
   - **Routine**: patch/minor bumps of Homebrew formulae, casks, npm globals. Batch them.
   - **Look first**: major-version bumps (▲), downgrades where "latest" is lower than what's
     installed (▼, usually a tap or formula rollback: say so, don't apply by default), new
     version schemes (≠, a build number became a version), pinned packages, and things that
     tend to break toolchains (python, node, openssl, postgres, llvm). Say why in a few words.
3. **Ask** what to apply. Offer a sensible default ("routine now, majors later?").
4. **Apply** what's approved:
   - `bin/cos update apply brew --yes` (all) or `bin/cos update apply brew <names…> --yes`
   - `bin/cos update apply npm [names…] --yes`, `bin/cos update apply mas --yes`
   - macOS: `bin/cos update apply macos` opens System Settings; installing needs the
     human's password and a restart. Never try `sudo softwareupdate`.
5. **Verify** with `bin/cos update` and report what changed and anything that failed.

## Rules

- Long upgrades can take many minutes; tell the human before starting a big batch.
- If an upgrade fails, show the last lines of output and log friction if it looks like
  something Claude OS should handle better.
