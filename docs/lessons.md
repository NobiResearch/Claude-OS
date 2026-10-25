# Lessons

Things Claude OS learned about macOS the hard way. Read before touching the same area;
add to it when you learn something new. Each lesson: what happened, the rule.

## Apple Events and AppleScript

- **Apple Events hang behind dialogs.** A modal sheet in the target app, or a permission
  prompt, blocks `osascript` indefinitely (eventually `-1712`, AppleEvent timed out).
  *Rule:* every `osascript` call has a timeout (`core.osascript` enforces it). macOS has no
  `timeout(1)`; in a shell, `perl -e 'alarm shift; exec @ARGV' 8 osascript …` works.
- **UI scripting summons the human.** `tell application "System Events" to … click …`
  triggers an Automation/Accessibility permission prompt for the terminal app. Only the
  human can answer it, and the script hangs meanwhile.
  *Rule:* no System Events UI scripting without asking first.
- **Errors come back localized.** On a non-English system, AppleScript error text is
  translated. *Rule:* branch on exit codes and error numbers, never on message text.
- **`player state as text` stays English** (`playing`, `paused`, `stopped`) even when the
  UI language isn't, so it's safe to compare.

## Apple Music

- **Volume 0 is a trap.** Starting playback with Music's volume at 0 shows a modal "volume
  is turned all the way down" warning that blocks playback and Apple Events until a human
  clicks OK. *Rule:* never set volume 0; to "mute", pause.
- **The catalog isn't scriptable.** AppleScript can only address library tracks.
  `open location "music://music.apple.com/<cc>/album/…?i=<id>"` navigates Music to the
  album page (with the song highlighted) but doesn't play it. Pressing `play` afterwards
  *sometimes* starts the page's container from track 1, and sometimes does nothing.
  *Rule:* library first; for catalog picks, prefer the single release (track 1), confirm
  with `player state`, and if it doesn't start, tell the human it's open and waiting.
- **Streams start slowly.** Subscription tracks can take several seconds to begin after
  `play`. *Rule:* press play once, then poll; repeated `play` calls can restart buffering.
- **The iTunes Search API** (`itunes.apple.com/search`, no key) finds catalog songs. Use
  the storefront from `AppleLocale` (`en_GB` → `gb`).

## Networking

- **python.org Python ships without CA certificates** until its "Install Certificates"
  script runs. *Rule:* `core.ssl_context()` adds macOS's bundle at `/etc/ssl/cert.pem`.
- **Some sites 403 Python's TLS fingerprint** while accepting `curl` with the same
  User-Agent. *Rule:* `core.curl_get` as a fallback on 403/429/503.

## Disk and developer tools

- **CoreSimulator touches every device folder**, so modification times say nothing about
  whether a simulator is used. `xcrun simctl list devices -j` includes `dataPathSize`, so
  no `du` is needed. *Rule:* "stale" means "older runtime than the newest installed".
- **`~/.Trash` is unreadable without Full Disk Access.** Finder can still count items
  (`count items of trash`), and `empty trash` works.
- **`softwareupdate -l`** detail lines end with a trailing comma, and it takes a few seconds
  even when nothing is available.
- **`brew outdated` is fast without auto-update.** Set `HOMEBREW_NO_AUTO_UPDATE=1`;
  `brew update` is the slow, networked step, so make it opt-in (`--fetch`).

## Git, files and shells

- **Git invents an email** like `login@Your-MacBook.local` when `user.email` is unset, and
  bakes your login and computer name into every commit you push. *Rule:* the Guardian
  blocks commits with machine-generated emails.
- **Finder resolves symlinks.** `tell application "Finder" to delete (POSIX file p as alias)`
  trashes the link's *target*. *Rule:* never hand Finder a symlink.
- **APFS is case-insensitive by default:** `~/code` and `~/Code` are the same folder, so
  dedupe paths by inode, not by name.
- **`(deny network-outbound (remote ip))` also blocks 127.0.0.1**; add
  `(allow network-outbound (remote ip "localhost:*"))` after it for local test servers. In
  sandbox profiles the later rule wins, which also lets you re-allow reading the working
  directory after denying a parent folder.
- **A guard that only checks the final diff misses history**: a file added and then deleted
  is still pushed. Check every commit (and its message) before publishing.
- **`sandbox-exec` works for untrusted code** (deny network, allow writes only to chosen
  paths), but sandboxes don't nest.
- **zsh doesn't word-split unquoted variables.** `cmd $args` passes one argument. Use arrays
  or `eval "set -- $args"` when testing command lines from a list.

## The app

- **Claude Code's permission bridge:** run `claude -p` with `--input-format stream-json
  --output-format stream-json --permission-prompt-tool stdio`, send an `initialize`
  control request first, and prompts arrive as `control_request` / `can_use_tool`. Answer
  with `control_response` → `{"behavior": "allow", "updatedInput": …}` or `"deny"`.
  Without the initialize handshake, `--permission-prompts host` just auto-denies.
- **Secrets in argv leak.** Any same-user process can read another's arguments with `ps`.
  Hand tokens over a pipe the parent owns.
- **A random port is a new origin** every launch, so localStorage resets. `cos serve`
  prefers port 7357 and falls back to a free one.
- **`Object.assign(el.style, {"--x": 1})` silently does nothing**; CSS custom properties
  need `style.setProperty`.
- **Focusing an input inside an `overflow: hidden` container still scrolls it.** Use
  `focus({preventScroll: true})` and pin the desktop's scroll position.

- **`toLocaleDateString(undefined)` follows the OS, not the browser language.** Pass
  `navigator.language` when output must match the page (e.g. English screenshots).

## Permissions (TCC)

- **macOS charges privacy permissions to the "responsible" app**, and everything an app
  launches inherits its grants. Give a capability its own small app, started with `open`,
  when only that code should have it (decision 0003).
- **An Accessibility grant didn't take** for a dev-signed `LSUIElement` helper on macOS 27:
  switched on in System Settings, valid signature, yet `AXIsProcessTrusted()` stayed false
  from every launch path. Unexplained; prefer narrower, purpose-built permissions anyway.
- **MusicKit on macOS:** `ApplicationMusicPlayer` (macOS 14+) and catalog requests work;
  `SystemMusicPlayer` and `MusicLibrary.add` don't exist on macOS. iTunes Search API
  `trackId`s are Apple Music catalog ids.
- **"Failed to request developer token"** means MusicKit can't identify the app. An App ID
  with the MusicKit service isn't enough: the app also needs an embedded macOS development
  provisioning profile (App ID + certificate + this Mac) and the
  `com.apple.application-identifier` entitlement in its signature. Ad-hoc signing can't
  carry that entitlement (macOS refuses to launch it).
- **MusicKit library songs differ from catalog songs:** `duration` comes back in
  milliseconds, and their ids are library ids (`i.…`) with their own ratings endpoint
  (`/v1/me/ratings/library-songs/…`).
- **`MusicPlayer.State.playbackStatus` lags commands** by a few hundred milliseconds; wait
  before reporting state.
- **Ad-hoc signatures change every build**, and grants are tied to the signature, so they
  silently reset. Sign local builds with a stable identity.
- **`shortcuts run --input-path` hands the shortcut a file, not text.** Actions expecting
  text or entities need "Get Text from Input" first.
- **`open -W` always exits 0** and can return early ("Unable to block on application")
  when the app exits within milliseconds. Read the app's own output (`--stdout`), not
  `open`'s exit code; the helper lingers 100 ms before exiting.
- **Turning a feature off doesn't revoke a macOS grant.** Only the human can, in System
  Settings; open the pane for them.

## System

- **`sfltool dumpbtm`** (no sudo needed) is the login-items database behind System Settings.
  It writes home folders as `/Users/<uid>/…` and some executable paths relative to their
  bundle; map both before checking that files exist.

## Hardware

- **Battery health on Apple Silicon:** `ioreg -rn AppleSmartBattery` reports
  `"MaxCapacity" = <percent>` directly; `AppleRawMaxCapacity` may be absent.
