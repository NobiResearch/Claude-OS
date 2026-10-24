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
- **`sandbox-exec` works for untrusted code** (deny network, allow writes only to chosen
  paths), but sandboxes don't nest.
- **zsh doesn't word-split unquoted variables.** `cmd $args` passes one argument. Use arrays
  or `eval "set -- $args"` when testing command lines from a list.

## Hardware

- **Battery health on Apple Silicon:** `ioreg -rn AppleSmartBattery` reports
  `"MaxCapacity" = <percent>` directly; `AppleRawMaxCapacity` may be absent.
