# Lessons

Things Ovenbird learned about macOS the hard way. Read before touching the same area;
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
- **`npm outdated` skips a package whose registry lookup comes back 403**, with no message
  (it takes a 403 for a private package). Behind a proxy or sandbox that refuses the registry,
  every lookup is a 403, so it prints `{}` and exits 0, which looks just like "up to date".
  `--loglevel=http` writes each lookup's status to stderr (`npm http fetch GET 403 <url>`).

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
- **`/usr/bin/git`, `python3`, `strings` and `nm` are xcrun shims, and xcrun can't run inside
  a sandbox:** it writes a cache in the per-user temp folder and reads Xcode's license
  outside. Put the real tools first on PATH. The command line tools keep all four in
  `usr/bin`; Xcode keeps `strings` and `nm` in `Toolchains/XcodeDefault.xctoolchain/usr/bin`,
  so finding only Xcode's `usr/bin` made the release tests fail in every evolve check.
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
- **MusicKit works in a Developer ID app, outside the App Store** (tested 26 October, decision
  0015): Developer ID signing with the hardened runtime, a Developer ID provisioning profile
  (all devices) for an App ID with MusicKit under App Services, and the `application-identifier`
  and `team-identifier` entitlements. A brand-new App ID can fail for a while with "Media API
  Token Service responded with status code: Not Found (404) … not registered as a valid client
  identifier" until Apple has caught up, and the app caches that failure until it's relaunched.
  *Rule:* after creating an App ID, wait a few minutes and test in a fresh launch; the log line
  `[com.apple.amp.iTunesCloud]` names the reason (`log show --predicate 'eventMessage CONTAINS
  "client identifier"'`).
- **Two Ovenbird apps on one Mac step on each other.** Both register `claude-os://`, and macOS
  sends those links to the one it prefers (the installed one), not the one you're testing; both
  write the per-launch `state/app.nonce`, so a command built for one is refused by the other;
  and `core.ensure_app` opens `~/Applications/Ovenbird.app` by name. *Rule:* run one at a time;
  to test another build, quit the installed app, send commands with `open -a <that app>`, and
  afterwards `lsregister -u` and trash the test build, then `lsregister -f` the installed one.

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

- **`sfltool dumpbtm`** is the login-items database behind System Settings. Without sudo
  it shows an **admin password dialog** (SecurityAgent) on macOS 27 and blocks until it's
  answered, so a background job that calls it hangs and leaves a dialog on the screen.
  Only run it when the human asked and knows the dialog is coming; the launchd plists in
  `~/Library/LaunchAgents`, `/Library/LaunchAgents` and `/Library/LaunchDaemons` (plus
  `launchctl print-disabled gui/<uid>` and `system`) need no permission at all. It writes
  home folders as `/Users/<uid>/…` and some executable paths relative to their bundle; map
  both before checking that files exist.
- **Scripts are never code-signed**: check for `#!` before calling `codesign`, or every
  shell-script agent looks like "unsigned code".

## Hardware

- **Battery health on Apple Silicon:** `ioreg -rn AppleSmartBattery` reports
  `"MaxCapacity" = <percent>` directly; `AppleRawMaxCapacity` may be absent.
- **Time Machine without side effects:** `tmutil destinationinfo -X` answers in
  milliseconds with a plist (an empty dict means no destination) and needs no permission.
  `tmutil latestbackup` can try to mount a network or removable destination; avoid it in
  background checks.

## Claude Code

- **`ask` rules always prompt, even in auto mode**, and an `allow` in `settings.local.json`
  can't override a project `ask`: deny, then ask, then allow apply across all settings files.
  To answer one prompt automatically, use a `PermissionRequest` hook. In that hook, exit
  code 2 means *deny*, so it must exit 0 and print nothing when unsure.
- **`--max-budget-usd` applies on a Pro or Max plan too.** It checks Claude Code's estimate at
  API prices and stops the run, even though nothing is charged.
- **A pending `ScheduleWakeup` keeps a headless `claude -p` alive** until it fires or the
  timeout kills it. The first weekly board meeting finished in 6 minutes and then sat for
  14 more. Daemons deny `ScheduleWakeup`, `CronCreate`, `CronDelete`, `Monitor` and
  `RemoteTrigger`; denied this way, a tool disappears from the run altogether.
- **Agent calls run in the background.** The `tool_result` arrives right away ("Async agent
  launched"), so it doesn't mean the agent is done. In `--output-format stream-json
  --verbose` (Claude Code 2.1), a `system`/`task_started` event carries the `tool_use_id`
  and `subagent_type`, and a `system`/`task_notification` event carries the `status` and a
  `summary` of the agent's answer. The agent's own messages come with `parent_tool_use_id`.
  Each turn ends in its own `result` event, so one run can have several. Text mode prints
  each turn's final text, and that's what the run files keep.
- **`Write(path)` permission rules aren't used for files.** Claude Code warns that only
  `Edit(path)` rules are checked, and they cover every file-editing tool.
- **macOS `pgrep` skips its own ancestors** unless you pass `-a`. Everything the app's chat
  runs is a descendant of Ovenbird.app, so `pgrep -x ClaudeOS` couldn't see the app from
  inside it, and `cos music radio` said "Ovenbird isn't running" from inside Ovenbird.
- **`git diff --name-only` shows a moved file under its new name only.** A check on paths
  needs `--no-renames`, or moving `.claude/settings.json` to `docs/` looks like adding a docs
  file. A failed `git diff` is also not "no changes": treat it as a reason to ask.
- **Local Network privacy covers ping.** Apple's TN3179 lists TCP and UDP, but a ping to the
  router from a third-party terminal app failed with `sendto: No route to host` while the
  router was right there in `arp -n`. Only Terminal.app, SSH, root and launchd daemons are
  exempt; everything else (an app's helpers, Ovenbird.app's chat, Warp, iTerm) needs the
  Local Network permission, and the first try may show the human an alert. `cos net` reads
  the ARP table instead, which sends no packets. CoreWLAN's signal properties need no
  permission; only the network's name and the like need Location.
- **A fast-forward runs the incoming tree's hooks.** With a relative `core.hooksPath`
  (`githooks`), `git merge --ff-only` runs the `post-merge` that the merge itself just
  brought in. Code that moves a checkout runs git with `-c core.hooksPath=/dev/null`.
- **`defaults` reads system preferences that a direct read can't.** Without Full Disk Access,
  `plutil` on `/Library/Preferences/com.apple.TimeMachine.plist` is denied, but `defaults
  export /Library/Preferences/com.apple.TimeMachine -` returns it through `cfprefsd`.
- **In zsh, `log` is a builtin.** Use `/usr/bin/log show …` for the unified log.
- **A PermissionRequest hook sees the whole Bash command.** `cd ~/.claude-os/dev/work &&
  git push -u origin night/x` isn't `git push -u origin night/x`, so the night shift's hook
  gave no answer and every such push asked the sleeping human. Run approved commands bare,
  one per call (worktrees share refs, so pushing from the live checkout works), and write
  commit messages and pull request bodies to files instead of heredocs.
- **Claude Code's sandbox and `core.run_sandboxed` allow opposite sockets.** Claude Code's
  (`sandbox.enabled`) refuses Unix sockets, lets a server listen on 127.0.0.1 with
  `network.allowLocalBinding`, and sets `TMPDIR` to `/tmp/claude-<uid>`, which every sandboxed
  Claude Code session on the Mac shares (so don't allow sockets there). `run_sandboxed`
  allows only Unix sockets in its own folder. Test servers use `helpers.local_server`, which
  works in both.
- **Claude Code's sandbox hides the Mac's vitals.** Inside it, `sysctl` (model, chip, cores,
  memory size, swap, uptime, load) and `ps` come back empty, and `fdesetup` can't tell, but
  `vm_stat`, `sw_vers` and `pmset` answer. `socketfilterfw --getglobalstate` reported the
  firewall off there while the unsandboxed pulse read it on: don't trust a sandboxed security
  reading, and print what couldn't be read as missing, not as zero (`status.known`).
- **An untrusted folder ignores its checked-in allow rules.** A headless run in a fresh
  worktree logs "Ignoring N permissions.allow entries from .claude/settings.json: this
  workspace has not been trusted", so it gets only what `--allowedTools` gives it.
- **Moving the repository to another owner breaks the pins on its address.** GitHub redirects
  the old URL, but `cos hook check` compares a pull request's URL with the checkout's origin,
  and catch-up only runs while origin matches the URL the human approved. After a transfer:
  `git remote set-url origin <new>` in the live checkout (worktrees share it), and the human
  turns Keep Ovenbird up to date off and on.
