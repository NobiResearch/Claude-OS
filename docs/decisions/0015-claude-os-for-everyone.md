# 0015 — Claude OS for everyone: a signed, downloadable app

- **Status:** accepted with conditions; step by step, each waiting for the one before
- **Date:** 2026-10-26
- **Decided by:** the board, on the human's "yes, start it"

## Context

The human wants people who aren't developers to use Claude OS, with Apple Music as one click.
Today everyone builds Claude OS.app themselves, and its own Apple Music player (MusicKit) works
only for an app Apple can tie to a developer team. "Sign in with Apple" doesn't help: it's
identity, not Apple Music access. A person's own access is macOS's "Allow access to Apple Music"
prompt, which Claude OS already shows. What's missing is an app built and signed once, by the
project, that anyone can download. The human has a paid developer account with a personal
Developer ID Application certificate; their current provisioning profile is a Development
profile for one registered Mac.

## Votes

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | A Developer ID app that clones the code is the smallest shape that works (catch-up, Update and CLAUDE.md all expect a git checkout). The hardened runtime needs entitlements for Calendar, Location and Apple Events; nothing may fall back to ad hoc. |
| Guardian | amend | Today's build would ship the home path, the builder's PATH and a Development profile (this Mac's hardware id, the team name) in every copy, and no scan covers build output. Publishing isn't gated, and the signature carries the human's legal name forever. |
| Steward | amend | It's a bet on future users, so the riskiest step goes first. For a non-developer the first launch is the whole experience: one checklist, nothing installed before a click, plain words. |
| Skeptic | amend | The premise is untested: if MusicKit refuses a Developer ID app, the promise is gone. A signed app is one hurdle of four (the command line tools, Claude Code, a sign-in, a subscription); keep the installer small. |

## Decision

0. **Gates first.**
   - `app/` is a safety path (`hook.PROTECTED`): its build, signing and setup code merges after a guardian review.
   - A daemon's model may not run `gh` or `gh-axi` (`ALWAYS_DENIED`). Code a daemon calls still reads GitHub (catch-up fetches, the brief lists pull requests), but nothing a daemon runs opens, merges or publishes anything (`cos evolve merge` is refused in daemons).
   - `ask` rules for `gh release*`, `gh-axi release*`, `gh api *releases*`, `gh-axi api *releases*` and `xcrun notarytool*` (rules that only add a prompt, so Claude could add them). A release is published with `gh release`, never another way. When step 3 lands, `app/build.sh --release*` and `./app/build.sh --release*` get `ask` rules too, since the notarization inside it never shows as a command of its own.
   - Releases are built only on the human's Mac, never in CI. The certificate and notary credentials never become GitHub secrets.
1. **Test that MusicKit works, before anything else is built.**
   - A Developer ID–signed, hardened-runtime build plays a catalog song through MusicKit after "Allow".
   - It uses a new neutral App ID with MusicKit, not one derived from the human's name, and its Developer ID provisioning profile.
   - It runs from `build/` against the existing checkout, with the human's own app quit, and goes to the Trash afterwards. Then `claude-os://` opens the human's app again. This test build is never notarized or uploaded: it's today's build, with the home path and PATH baked in.
   - The full check (notarized, a quarantined download, a second macOS user account; Calendar, Location, notifications and Music automation all prompt and work) comes before the first public release.
   - If MusicKit fails, stop and bring it back to the board.
2. **The human's name.** Before anything is public, the human sees exactly what a downloader sees ("Developer ID Application: <full name>") and gives an explicit yes, or waits for an organization account.
3. **`app/build.sh --release`.** `app/build.sh` without the flag behaves exactly as today.
   - It writes no `ClaudeOSRoot` or `ClaudeOSPath`, and bakes the release commit's SHA.
   - It strips the binary.
   - It takes only an explicitly named Developer ID profile (all devices, no device list) for the release App ID, whose `Name` and `AppIDName` are neutral. It checks the profile by parsing it.
   - Its entitlements come from an allowlist, never `get-task-allow`, `disable-library-validation`, `allow-jit` or the like.
   - It signs with `--options runtime --timestamp` and notarizes with a Keychain profile only.
   - It refuses under `CLAUDE_OS_DAEMON`, `COS_SANDBOXED` or `CI`, on a dirty tree, or off `origin/main`, and fails rather than falling back to ad hoc.
   - Before embedding the profile and signing, it scans Info.plist, the binary (`strings`, `nm`) and the resources with the Guardian's patterns, and any hit stops it. (The profile and the signature carry the team's name by design, so they're checked by parsing, not by the scan.)
4. **The app finds its code without baked paths.** The order is: Info.plist (dev builds), `CLAUDE_OS_ROOT` (dev builds only), the `cos` link, then `~/Library/Application Support/Claude OS`. A release build checks what it found before running it (`bin/cos`, `lib/cos`, and an origin of `github.com/markusskov/Claude-OS`). PATH is a fixed list. The app records where it is in `~/.claude-os/state/app.json` for `cos` to read. First-launch setup code that lands outside `app/` (a new `lib/cos/` module, say) joins `hook.PROTECTED` too.
5. **First launch: one native checklist, nothing before a click.**
   - Command line tools: checked with `xcode-select -p`, which never prompts, before any `git` or `python3` shim runs. `xcode-select --install` only on a click.
   - Claude Code: a link to Anthropic's page or the command to paste. Never a script piped to a shell.
   - The clone: `github.com/markusskov/Claude-OS` at the release commit, with catch-up's git hardening, into an empty `~/Library/Application Support/Claude OS`.
   - Existing installs: adopt one or stop. Never re-point another checkout's daemons, links or hooks.
   - Opt-ins: `cos install`'s extras (skills in `~/.claude/skills`, the pulse daemon) are opt-ins that start off.
   - Downloaded copies get a `settings.local.json` that denies `gh` and `git push`. The night shift is hidden unless origin is the person's own repository.
   - "Remove Claude OS" undoes only what this copy added and moves the checkout to the Trash. `~/.claude-os` (the journal, memory) goes to the Trash only after its own yes.
   - It never asks for Full Disk Access, Accessibility or Screen Recording.
6. **Updates.**
   - No Sparkle and no app that replaces itself.
   - The app only says a newer release exists: a quiet line in Updates, at most once a day.
   - Keep up to date stays off by default. Downloaded copies follow the releases the human cuts, not raw main. If they ever follow main, the switch's dialog says plainly that Claude merges some changes without a human's review.
   - Python that gets ahead of an older app says "download Claude OS.app X" instead of breaking.
7. **Publishing.**
   - A GitHub Release only on the human's yes in the conversation, each time, never from a daemon.
   - The notes say, in plain words: what you need (macOS 14+, Claude Code and a Claude plan, Apple Music for music), what first launch adds and how to remove it, that it's PolyForm Noncommercial (binaries too), and that it isn't made or endorsed by Anthropic.
   - The notes pass `cos guard --text`.

## Not now

An installer that sets up Claude Code itself, an organization developer account, and the App Store,
whose sandbox can't run what Claude OS does.
