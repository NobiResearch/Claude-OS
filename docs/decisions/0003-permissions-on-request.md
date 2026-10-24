# 0003 — Permissions when the human asks for them

- **Status:** accepted
- **Date:** 2026-10-24
- **Decided by:** the board (second meeting), on the human's request

## Context

The Shortcuts route for catalog music (0002) failed in practice: `shortcuts run` hands the
shortcut a file, and Music's Play action silently does nothing with it. The human then
asked directly for permission-based features behind toggles: "You are on my computer and
you are my OS, so allowing stuff is the point... let's not limit ourself because of 'rules
and privacy'... take it up with the board."

## Votes

| Proposal | Architect | Guardian | Steward | Skeptic | Result |
|---|---|---|---|---|---|
| S: sign local builds with the developer's own identity | approve | amend | approve | approve | **approved, first** |
| M2: a separate "Music Helper" app with its own Accessibility grant | amend | amend | reject | amend | **approved** |
| W: weather: a city field, plus a "Use my location" toggle | amend | amend | approve | amend | **approved** |
| M1: grant Accessibility to Claude OS.app itself | reject | amend | amend | reject | not approved (2–2) |

The Guardian **lifted its 0002 veto**: the human is root, asked for this explicitly, and
their click on macOS's own prompt is the consent the laws require.

## Why a helper, not the app

macOS charges privacy permissions to the *responsible* app, and every process an app
launches inherits its grants. An Accessibility grant to Claude OS.app would reach every
Claude session the app spawns. A helper launched with `open` is its own responsible
process, so the grant stays with code that only knows four fixed commands.

## Decision and conditions

1. **Signing (S):** `app/build.sh` signs with the first "Apple Development" identity it finds
   (pinned by hash, never written to the repo), ad-hoc otherwise and always ad-hoc under
   daemons; it says loudly when it falls back, because grants then reset on every build.
2. **Full Music control (M2):** off by default. The toggle in Settings asks macOS to grant
   *Claude OS Music Helper*. The helper presses Music's own controls through the
   accessibility API: no keystrokes, no matching on (localized) labels, never activates
   Music. `cos music play` verifies what's playing afterwards and falls back to today's
   behavior. Never from daemons. Turning it off opens the Accessibility pane, because only
   macOS can revoke the grant.
3. **Weather (W):** off until the human chooses. A city first; "Use my location" asks macOS
   for Location only when clicked. Coordinates are rounded to ~1 km, live only in
   `~/.claude-os/config.json`, never in the journal, trends, friction or commits, and the
   city name joins the Guardian's private terms. Open-Meteo gets only rounded coordinates.

## Amendment (same day): MusicKit instead of the helper

In practice the helper never became trusted: the human switched it on under Accessibility,
yet `AXIsProcessTrusted()` stayed false however it was launched (`open`, nested or
standalone, as a launchd job), with a valid signature. The human then pointed at the right
tool: **"Media & Apple Music"**, the permission for MusicKit.

On macOS 14+, MusicKit's `ApplicationMusicPlayer` plays any catalog song with the human's
subscription, through Apple's own API. That's strictly narrower than Accessibility (music
only, no input synthesis), so the chair adopted it under this decision's conditions rather
than reconvening: the board approved permission-based music control; this is a smaller
permission for the same feature. The helper is removed.

- Claude OS.app plays catalog songs itself (`app/Sources/ClaudeOS/Player.swift`); `cos`
  drives it with `claude-os://music/…` URLs and reads `~/.claude-os/state/player.json`. A
  stray link can at most play or pause a song.
- "Apple Music in Claude OS" in Settings, off by default; turning it off opens the Media
  & Apple Music pane so the human can revoke the grant.
- MusicKit needs the app's bundle id registered with the MusicKit service in the signing
  team's developer account (`COS_BUNDLE_ID` for anyone building their own copy).
- `MusicLibrary.add` isn't available on macOS, so catalog songs can't be added to the
  library; they play in Claude OS, and library songs still play in Music.
