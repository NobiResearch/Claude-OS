# Changelog

User-visible changes to Ovenbird (called Claude OS until 0.8.0). Each pull request adds its
entry as a file in `changes/`; they're folded in here at each release (the desktop shows them
under **Unreleased** until then).

## Unreleased

## 0.8.0 — 2026-10-28

Claude OS becomes **Ovenbird**, gets a mark of its own and opens up to contributors. Claude now
works on it day and night, in the open: every pull request gets a guardian's review, and what's
merged can come to your Mac by itself if you want it to (decisions 0005 to 0022).

**Ovenbird**
- **Claude OS is now Ovenbird** ([0019](docs/decisions/0019-the-name.md)): the app, its menus,
  the desktop, the boot banner, notifications and the docs. "Claude" is Anthropic's trademark,
  so the name is our own, and the description says what it's built on: Claude Code. `cos`,
  `~/.claude-os` and everything macOS remembers (permissions, Music, Calendar) stay as they are.
- **A mark of its own: Courses** ([0022](docs/decisions/0022-courses.md)). The ovenbird's domed
  nest, built from four round-ended bars like courses of bricks, the top one in amber, the
  doorway a gap in the lower two. It's the app icon (dark, hand-drawn at 16 and 32 px), the menu
  bar icon (which macOS tints for light and dark menu bars), the README's header and the
  desktop's favicon. Nobi Research's mark is a gate. The brand kit is in `docs/brand/`.
- **The desktop wears the mark's colors:** neutral dark grays with one amber accent, Crown, and
  status colors that read clearly apart from it, with dark text on every colored fill. The mark
  replaces the diamond where it was the logo; the diamond stays where it marks things, and the
  terminal's accent follows the new color.
- **A new home:** [github.com/NobiResearch/Ovenbird](https://github.com/NobiResearch/Ovenbird).
  The old addresses redirect. If your checkout still points at one, run `git remote set-url
  origin https://github.com/NobiResearch/Ovenbird.git`, then, if **Keep Ovenbird up to date** is
  on, turn it off and on in Settings so it follows.

**Your Mac**
- **`cos security`**: FileVault, SIP, the firewall and Gatekeeper, what each does and how to
  turn it on. `cos security on firewall --yes` turns the firewall on through macOS's own
  password dialog. It only ever turns things on, and the desktop's Security card offers it
  while the firewall is off ([0008](docs/decisions/0008-firewall-switch.md)).
- **`cos backup`**: whether Time Machine is set up, about how much there is to back up, and
  which connected disk could hold it: format, size, whether it's big enough, and plainly when
  Time Machine would erase it. With no disk plugged in, it says what size to get. `cos backup
  setup` opens Time Machine's settings
  ([0012](docs/decisions/0012-backup-and-the-night-of-26-october.md)). `cos status`, the boot
  banner and the morning brief say "Time Machine isn't set up" as a quiet note, never a
  notification; pulse checks once a day with `tmutil destinationinfo`, which never mounts or
  names a backup disk. Back up another way? `cos config pulse.backup_check false`
  ([0005](docs/decisions/0005-radio-and-backup-signal.md)).
- **`cos net`**: is it the Wi-Fi, the router or the internet? A few seconds, one plain verdict,
  then the signal, the router, the internet and DNS. It gets the hard cases right too: DNS that
  hangs, Wi-Fi without an address, IPv6-only networks, a sign-in page that hijacks DNS, a broken
  IPv6 path, a VPN over a cable. It never reads the network's name or anything else that says
  where you are. `cos net --speed` measures throughput with macOS's own networkQuality, only when
  you ask ([0010](docs/decisions/0010-net.md)). Vitals has a Network card that does the same,
  and asks Claude (and so you) before a speed test, which uses real data.
- **`cos power`**: what keeps the Mac or display awake, from the processes holding sleep
  assertions and how long they've held them. Read-only. Contributed by
  [trleo](https://github.com/trleo).
- **`cos update`:** `update apply` shows progress, prints every warning and error with its
  details, names anything you asked to upgrade that's still outdated, and keeps the full output
  in `~/.claude-os/runs/updates/`. It says "couldn't check" for npm, the App Store or Rust when
  it can't reach them, or when a proxy or firewall refuses the npm registry, instead of "up to
  date". Downgrades (▼) and new version schemes (≠, say 9430 → 0.7.0) count as "look first" next
  to ▲ majors, and the Updates app leaves them unticked. A macOS update's version shows once.
- **`cos clean`** reports what it actually freed (old simulator runtimes counted 0 B when
  Xcode's simulator service was busy), and skips a cache a running tool holds, saying why. It's
  stricter about what it deletes: never through a symlinked folder; command cleanups run from the
  home folder; only items from your last scan, within a day; a downloaded folder with something
  recent inside isn't "old"; running apps keep their caches; Poetry's and JetBrains' folders
  aren't caches; `node_modules` needs a package.json and a lockfile; and `downloads-old trash`
  together is refused.
- **`cos status` and Vitals** read the load, swap and top processes correctly with a locale that
  writes decimals with a comma. Helper processes count as the app they belong to ("Firefox ×18
  7.3 GB"), tools inside an app bundle keep their own name, and a group's memory shows as
  approximate (≈). What macOS wouldn't tell them (inside Claude Code's sandbox, say) is left out
  instead of made up: no "0 cores", "of 0 B" or "swap 0 B" in `cos status`, the boot banner or
  the Vitals card, and unreadable swap is `null` in `--json`. The Vitals card's fix was
  contributed by [bfs2021](https://github.com/bfs2021).
- **`cos startup`** flags a launch agent or daemon whose plist names nothing to run as a
  leftover, and sizes its name column to the longest name.
- **Weather** alerts no longer warn about an hour that's already over.
- **Music:** pausing in Ovenbird's player keeps the paused song on screen and play resumes it,
  however long the pause, without swapping the cover back and forth. Playing music from the chat
  inside the app works. Today has a Radio chip: one click to a radio from a song you've been
  playing (`cos music radio --mine` in the terminal).
- **Clicking a notification opens what it's about:** the board's minutes, the morning brief,
  evolve's branches or Background jobs. The target comes from a fixed list, so a click only ever
  navigates.

**Keeping up to date** ([0011](docs/decisions/0011-catching-up-with-main.md))
- **Ovenbird notices what's merged.** The boot banner and `cos update` say when changes are
  merged on GitHub but not on this Mac yet, and name Ovenbird's safety files when they change.
  `cos update apply claude-os --yes` brings them in: fast-forward only, only on a clean `main`,
  only over GitHub's own pull request merges, and journaled with the way back. The Updates window
  shows it too, with a button that asks Claude to bring it in.
- **Keep Ovenbird up to date** (Settings › Permissions, off until you confirm it in the app's own
  dialog): what's merged on GitHub comes to this Mac by itself, when the app starts, when a
  terminal session starts, and while the app is closed. On this project's GitHub, Claude merges
  its own pull requests once CI passes and a guardian agent has reviewed them, without a person
  reading them first; the dialog and the README say so. While the app is open, **Update** in its
  menu bar restarts just its server onto the new code, and music keeps playing.
- The app's server keeps the code it started with until you click Update. Update waits for a
  running cleanup or update to finish, reloads the desktop with the new server's token (so
  windows don't say "missing or wrong token"), and isn't offered when a catch-up can't happen.
  View › Reload (⌘R) reloads for real.
- `cos config` can only turn the autonomy switches (Night shift, Keep up to date) off. Turning
  them on takes the app's own dialog, which code in the desktop page can't click.

**A downloadable Ovenbird.app** (built, not released yet; [0015](docs/decisions/0015-claude-os-for-everyone.md))
- `app/build.sh --release` builds it with nothing from the builder's Mac inside, scanned before
  it's signed, signed with Developer ID and the hardened runtime, notarized and stapled.
  `docs/releasing.md` has the steps. Building, notarizing and publishing all ask first.
- On first launch, a checklist shows what the Mac still needs (Apple's command line tools,
  Claude Code, Ovenbird itself), with one button each and nothing installed before a click.
  Two extras, the skills in Claude Code and the two-hourly vitals check, start off.
- It follows its app: open a newer Ovenbird.app and the code comes along. Updates says when a
  newer app is out (it asks GitHub at most once a day), and a warning says when the code needs a
  newer app. It has no night shift and no Branches tab.
- **Remove Ovenbird…** turns off its background jobs, removes its links and moves its code to the
  Trash. Your journal and memory go only if you say so.
- Ovenbird's tools always talk to the app you're using, even with another copy on the Mac, and
  `cos doctor`, `cos daemon list`, `daemon install` and `uninstall` know which background jobs
  belong to another copy and leave them alone.

**The desktop**
- In its first week on a Mac, Today shows a welcome card: where to look first, how to ask
  Claude, and that weather, calendar and Apple Music stay off until you turn them on. Feeds says
  what's happening on its first, slower load, and an empty Journal says what it's for.
- **Watch the board meet** ([0007](docs/decisions/0007-live-daemon-runs.md)): while a meeting
  runs, Evolution › Board shows each seat waiting, deliberating or voted, then the minutes.
  Settings and `cos daemon list` say when a background job is running, and the notification at
  the end says what happened.
- The Evolve window says when a branch's tests failed in the sandbox, when a branch changes
  Ovenbird's safety checks, and what Merge does (push, open a pull request, squash-merge once CI
  passes). Your OK in the Merge dialog covers the commit it showed; if the branch moved since,
  it asks you to look again.

**Claude at work on Ovenbird**
- **The repository is Claude's** ([0013](docs/decisions/0013-the-repository-is-claudes.md)):
  Claude pushes, opens pull requests and merges its own in the Ovenbird repository you own
  without asking. The Guardian still blocks private data, `main` takes only green pull
  requests, and deleting the repository still asks.
- **Every pull request gets a guardian's review before it merges**
  ([0020](docs/decisions/0020-every-pull-request-gets-a-review.md)), not only the ones that
  touch Ovenbird's safety files. `cos hook check <PR>` says when one is ready for that review,
  names the safety files it changes, and prints the exact merge command.
- **Night shift** (Settings › Permissions, off until you confirm it in the app's own dialog;
  [0006](docs/decisions/0006-night-shift-pushes.md)): while you're away, Claude pushes its own
  `night/…` branches, opens, edits and comments on pull requests, and reads from GitHub with your
  login, without a card. Never `main`, never a force push, never a change to `.github/`, and the
  switch never approves a merge. Every commit and pull request text is checked for private data first, and each push is
  in your journal and the next morning's brief.
- **Nightly evolve branches:** the boot banner, `cos evolve` and the Evolve window say when a
  branch's tests failed. `cos evolve merge` and the Evolve window's Merge take a branch that
  changes safety files only after a review (`--reviewed`), wait for CI to start before watching
  it, pin the merge to the commit that was checked, and name the pull request after the night's
  change. The nightly run itself never pushes or merges. The morning brief says when it hit
  something it couldn't record.
- **Daemons on a Pro or Max plan run without a dollar cap**: the cap was Claude Code's estimate
  at API prices, so on a flat plan it only cut runs short. Time limits still bound every run, and
  with an API key the caps stay. Background jobs can't schedule wakeups or timers.
- `cos friction add`, `cos remember` and `cos memory --forget` print one clear line instead of a
  traceback when private state can't be written.

**Safety and privacy**
- **The Guardian reads more before anything leaves the Mac:** every push, commit by commit
  (files, messages, and an author and committer address that must be GitHub's noreply); a pull
  request's title and body; and everything `gh` would publish (comments, reviews, issues, release
  notes, `gh api` fields), with body files only from the repository or the temp folder.
  `cos guard --text <file>` runs the same check on any file. It also catches your login name
  where it names you, a Mac name of the "Name's MacBook" kind, paths hidden in URLs and text
  inside pictures.
- **More things count as private:** Claude Code's account file, git's stored credentials,
  Docker, Kubernetes, Google Cloud, Azure, PyPI, Cargo, RubyGems, `pass`, and the histories
  shells and tools keep. The nightly evolve run can't read them, or `~/.ssh`, `~/.aws`,
  `~/.config/gh`, `~/.claude` and the Keychains, from its shell, the code it runs or its Read
  tool. `~/.claude-os` stays readable for now: the run's workspace and its input live there.
- **The nightly evolve run stays in its sandbox:** its tests run deny-by-default, with no Apple
  Events, no browser, no inherited environment and no network at all (their test servers use
  Unix sockets). It runs no hooks, edits only its own workspace and can't edit its Claude Code
  settings, and its clones copy git's objects instead of sharing them with your checkout.
- **Runs that read feeds get less:** the morning brief, the board and the app's chat no longer
  load your own allow rules (in the chat, git, gh and `python3` ask with a card; the morning and
  board runs can't use git), and background runs can't speak, notify or write the journal on a
  model's say-so, are denied everything `cos` refuses them, and never ask GitHub with your login.
  Their notifications are written by Ovenbird itself, and friction they log is marked as such;
  they can't close it.
- **Settings safe for strangers** ([0017](docs/decisions/0017-stranger-safe-settings.md)): in a
  fresh clone or download, `git`, `gh` and the tests show a card first, and a downloaded copy's
  own deny rules come back if they go missing. A `cos` command that changes something shows a
  card even when it's oddly written.
- `cos doctor` prints paths as `~/…`. A feed larger than 5 MB isn't read, a hand-edited setting
  that isn't a section no longer breaks Settings, and a package name starting with a dash is
  refused.

**Everywhere** ([0009](docs/decisions/0009-claude-os-everywhere.md))
- `/music`, `/tidy`, `/update` and `/startup` work in Claude Code from any folder on your Mac:
  `cos install` links them into `~/.claude/skills`. Their descriptions keep them out of your
  projects' own dependencies, clean-ups and video music, and nothing about the project you're in
  gets recorded. `cos uninstall` removes the links. `cos install --no-daemons` says which
  background jobs are still running.

**Contributors**
- Ovenbird is MIT, every version, including the ones published for a few days under the
  PolyForm Noncommercial License ([0014](docs/decisions/0014-license-and-contributions.md),
  [0016](docs/decisions/0016-back-to-mit.md)).
- New: CONTRIBUTING.md (what we want most, where a change goes, what we turn down), AI_POLICY.md
  ([0018](docs/decisions/0018-what-we-ask-of-contributors.md)), AGENTS.md, SECURITY.md with
  private reporting, a Code of Conduct, ACCESSIBILITY.md, pull request and issue templates, and
  GitHub Discussions for questions and rough ideas.
- The README and the architecture page say exactly what's enforced and who merges what.
- Each pull request records its changelog entry as its own file in `changes/`, so pull requests
  don't conflict over this file.
- Thanks to our first contributors, [trleo](https://github.com/trleo) and
  [bfs2021](https://github.com/bfs2021).

## 0.7.0 — 2026-10-25

Music that keeps going, and a safer Claude OS. Built overnight
([0005](docs/decisions/0005-radio-and-backup-signal.md)).

**Music**
- **Radio**: `cos music radio "<song> <artist>"` plays the song in Claude OS's own player,
  then keeps going with similar music from its Apple Music station (the artist's if the
  song has none); with no argument it starts from the song playing now. The `/music` skill
  uses radio for moods, and the desktop's Music app has a Radio button next to ⏭. If Apple
  Music has no station, the song plays alone and `cos` says so. (New: the first real
  playback test is still to come.)
- **Playlists play in Claude OS's own player**, from `cos music playlist <name>` or the
  desktop. Next, previous and shuffle go there too; `like` rates the song actually playing,
  even mid-playlist or mid-radio.

**Your day**
- **Notifications from Claude OS** (0004): with the setting on, alerts and the morning brief
  arrive with Claude OS's own name and icon; clicking one opens the desktop. The text goes
  through a private outbox in `~/.claude-os`, and the link that wakes the app carries
  nothing. Without permission (or with the app closed) they fall back to AppleScript.
- **Today's brief on the desktop**: once the morning daemon has written it, a "☕ Today's
  brief" chip leads Today and opens it. The brief talks to you as "you" and doesn't guess
  things about you.
- **`cos startup` no longer summons a password dialog.** On macOS 27, `sfltool dumpbtm`
  shows an admin password dialog; the audit now reads launch agents and daemons directly.
  `cos startup --full` (apps that open at login too) asks for an Allow first and is refused
  in background jobs. Scripts say "runs a script", not "unsigned code".

**Security** (a fresh review of everything since v0.2, plus what dogfooding found)
- `claude-os://` links that change something need this launch's nonce, so a web page or
  feed link can't make Claude OS play, rate or ask macOS for a permission; player answers
  carry a request id.
- Only http(s)/mailto links leave the app; feeds keep only http(s) links; Markdown links
  can't break out of their attribute; the CSP drops `'unsafe-inline'` styles.
- Evolve: the Guardian checks every commit and message a merge would publish; tests run on
  a fresh checkout of exactly the merged commit, in a sandbox with no internet that can't
  read `~/.ssh`, `~/.claude-os` and other private folders; no tests, no merge.
- Background jobs can't connect the calendar, set the weather place, add feeds, change
  config, play or rate music, write the memory, start another Claude, a server or a build.
  A feed item steering the morning brief can't plant "facts" in every boot banner.
- Weather coordinates join the Guardian's private terms.

## 0.6.0 — 2026-10-25

One player ([0004](docs/decisions/0004-v0.6-one-player.md)).

- **One player:** with Apple Music on, library songs play in Claude OS too (MusicKit
  `MusicLibraryRequest`), so now-playing, pause and love work the same for everything;
  the Music app is the fallback. `cos music unlike` removes a rating.
- **`cos startup`** and `/startup`: what starts with this Mac, from macOS's own login-items
  list plus code signatures, odd ones first (missing programs, unsigned code, unused for
  months). Read-only. A "Starts with your Mac" card in Vitals.
- **Swift tests:** the app's link parsing, the native bridge's origin check and the
  server's ready line are tested, in CI.
- Fixed: library songs reported durations in milliseconds; loving a library song used the
  catalog endpoint. README screenshots refreshed.

## 0.5.0 — 2026-10-25

Your day.

- **Calendar & Reminders** (decision 0002's deferred B): Claude OS.app reads today's and
  tomorrow's events (recurring ones expanded, via EventKit) and due reminders, only after
  you click **Connect** in Settings. Read-only. `cos cal`, the Today panel, the brief.
- **Weather alerts:** the forecast adds an hourly outlook ("rain likely around 15:00",
  "rain easing around 04:00", thunderstorms first); alerts become signals everywhere.
- **Like the right song:** `cos music like` loves the song playing in Claude OS's own player
  through the Apple Music ratings API, and only touches the Music app when that's what's
  playing (it used to heart whatever was paused in Music).

## 0.4.0 — 2026-10-25

Permissions when the human asks for them ([0003](docs/decisions/0003-permissions-on-request.md)).

- **Settings › Permissions:** "Apple Music in Claude OS" and "Weather", both off by default.
- **Claude OS plays Apple Music itself:** MusicKit's ApplicationMusicPlayer under the narrow
  "Media & Apple Music" permission plays any catalog song; `cos music play` drives it via
  `claude-os://music/…` URLs and `cos music now` shows it. (An Accessibility-based helper
  was tried first and removed: see the amendment in 0003.) Needs macOS 14+, an App ID with
  the MusicKit service, and a macOS development profile in `~/.claude-os` (`cos music setup`).
- **Weather:** `cos weather` (Open-Meteo, no key), on the Today panel and in the brief. Pick a
  city, or "Use my location" in the app (CoreLocation, rounded to ~1 km, stays on this Mac;
  the place joins the Guardian's private terms).
- **Signing:** local builds are signed with your own Apple Development identity when there
  is one, so macOS grants survive rebuilds; ad-hoc (loudly) otherwise and under daemons.
  `COS_BUNDLE_ID` sets the bundle id (MusicKit needs one registered in your account).
- **MIT license.** Shortcut setup now includes "Get Text from Input".

## 0.3.0 — 2026-10-24

Decided by the board's first meeting ([0002](docs/decisions/0002-v0.3-priorities.md)).

- **Music:** catalog playback through a "Claude OS Play" shortcut (Music's Play App
  Intent, no new permissions): `cos music setup`, `--source shortcut`; verifies what plays.
- **Clean:** `simulator-runtimes-old` target (older simulator OS images, newest per platform
  always kept, safety review), with last-used dates.
- **Trends:** pulse logs one snapshot a day (`~/.claude-os/trends.jsonl`); `cos status`
  shows the weekly disk trend once there's a week of data; `/api/trends`.
- **Demo mode:** `cos serve --demo`, a fictional Mac from one fixtures module with a
  scripted chat; README screenshots come from it.
- Dates in the desktop follow the browser's language.

## 0.2.0 — 2026-10-24

The desktop.

- **Claude OS.app** (`app/`): native AppKit shell with a WKWebView desktop, menu bar
  status item, global hotkey ⌃⌥Space, crash-restarting server, ad-hoc signed; `cos app`.
- **The desktop** (`ui/`, no build step): menu bar, dock, draggable/resizable windows,
  ⌘K palette, boot screen, and apps: Claude, Vitals, Storage, Updates, Music, Feeds,
  Evolution, Journal, Memory, Settings.
- **Claude in the app** (`lib/cos/chat.py`): headless Claude Code over stream-json;
  permission prompts become Allow/Deny cards answered by the human; approvals journaled.
- **`cos serve`** (`lib/cos/server.py`): loopback-only API with a per-launch token
  (never in argv or env), Host-header check, CSP, background jobs for approved actions.
- Music search results carry album artwork.

## 0.1.0 — 2026-10-24

The founding release.

- **Kernel:** `CLAUDE.md` laws and syscall table; SessionStart boot banner; status line.
- **Syscalls:** `status`, `clean` (24 targets with safety levels), `update` (macOS,
  Homebrew, npm, mas, rustup), `music` (library + catalog), `feeds` (RSS/Atom/RDF with
  read tracking), `log`, `friction`, `remember`/`memory`, `notify`, `say`, `brief`,
  `daemon`, `evolve`, `guard`, `doctor`, `install`/`uninstall`, `config`.
- **Apps:** `/music`, `/tidy`, `/update`, `/brief`, `/board`, `/lab`, `/evolve`.
- **Colleagues:** board seats `architect`, `guardian`, `steward`, `skeptic`; lab `scout`.
- **Daemons:** `pulse` (free), `morning`, `evolve`, `board` (opt-in, budget-capped).
- **Privacy:** Guardian pre-commit hook and whole-tree test.
