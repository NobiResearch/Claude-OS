# Contributing to Ovenbird

Thanks for wanting to make Ovenbird better. Ideas, bug reports and pull requests are all
welcome. For a privacy or safety hole, please don't open an issue: see [SECURITY.md](SECURITY.md).
Working with an AI coding agent is fine too: [AI_POLICY.md](AI_POLICY.md) says what we ask.

## What we want most

For anything new (a command, skill, daemon or desktop feature), open an
[idea issue](https://github.com/NobiResearch/Ovenbird/issues/new?template=idea.md) first, so
nobody builds something we'd turn down. Bug reports and fixes for open issues don't need one.

1. **Bug reports:** your macOS version, chip and what broke. Paste only `cos version` and
   `cos doctor` (it writes your home folder as `~`, but check it for your username anyway), and
   describe anything else in your own words: the other commands' output describes you and your
   Mac.
2. **Fixes for open issues.**
3. **Trying it on other Macs:** other macOS versions and system languages (AppleScript errors
   come back in the system's language). What you learn goes in an issue or in
   [docs/lessons.md](docs/lessons.md).
4. **Ideas** for new commands, skills or daemons, as an idea issue. The board decides.
5. **Polish for the desktop** in `ui/`.
6. **Docs.**

## Set up

```sh
git clone https://github.com/<you>/Ovenbird.git && cd Ovenbird   # your fork
bin/cos install     # also turns on the privacy guard (git hooks in githooks/)
cos doctor          # checks the wiring
```

- Python 3.9+ standard library only: macOS ships it, and Ovenbird adds no packages.
- `cos serve --demo --open` shows a fictional Mac, for desktop work and screenshots. It
  never reads or changes the real machine.
- Building the app needs the Xcode command line tools. Its own Apple Music player needs your
  own Apple developer team (see the README); everything else works without one.

## Make a change

- One change per pull request, on a branch from `main`.
- Code lives in `lib/cos/`, one module per subsystem, in the style that's there: small
  functions, plain dicts, `core.run` for processes. [CLAUDE.md](CLAUDE.md) has the details,
  and the laws every change keeps (read-only by default, `--yes` to change anything, a
  journal entry for what changed).
- Before you push:
  ```sh
  python3 -m unittest discover -s tests
  /usr/bin/python3 -m unittest discover -s tests   # macOS's own Python
  node --check ui/*.js                            # if the desktop changed
  bin/cos guard --all
  ```
  Tests run against a throwaway `CLAUDE_OS_HOME` and must never touch real state.
- A change people will notice gets its own file in `changes/` (see
  [changes/README.md](changes/README.md)); never edit `CHANGELOG.md`. A design change gets a
  decision in `docs/decisions/`.
- Keep your own life out of it: no names, paths with your username, email addresses, music,
  feeds or calendar in code, tests, commits or pull request text. The guard catches the
  obvious ones; the rest is on you.

## Where a change goes

[docs/architecture.md](docs/architecture.md#layers) describes the layers. In short:

- **Touching the Mac** is a syscall in `lib/cos/`: deterministic, and read-only unless `--yes`.
  One that changes the Mac also goes in `cli.MUTATING` and `daemon._MUTATING`, gets the same
  `ask` rules as the others in `.claude/settings.json`, and has a test that it's refused
  under `CLAUDE_OS_DAEMON`. One that's fine when the person asks but never from a background
  run (playing music, say) goes in `cli.DAEMON_REFUSED`.
- **Judgment** is a skill in `.claude/skills/`. Skills call syscalls rather than doing their
  work again, and so does the desktop (`ui/`, through `lib/cos/server.py`).
- **Scheduled work** is a daemon. Anything that uses a model is off until the person turns it
  on, and no daemon changes the Mac (the one exception is `pulse` bringing in Ovenbird's own
  updates, when the person turns on Keep Ovenbird up to date).
- Prefer extending what's there. A new command touches `lib/cos/cli.py` and CLAUDE.md's table,
  which are safety files: that's expected, and it gets the safety review.

## What we turn down, even when it's well built

Anything that breaks the rules above, and:

- **A new macOS permission prompt**, unless it's off by default behind a switch the person
  turns on, and the board agreed. Nothing that needs Full Disk Access, Accessibility or Screen
  Recording to work: Ovenbird never needs them.
- **New servers, or code from the network.** The desktop loads no code from the internet (its
  scripts and styles are its own; only images such as album art come from outside), and Claude
  OS never downloads and runs code from anywhere but this repository. What runs is what's in
  it, plus the upgrades the person approves with `cos update apply`.
- **Telemetry or analytics**, sending anything about the person anywhere but the service a
  feature names and they turned on, or keeping it outside `~/.claude-os`. What Ovenbird learns
  stays on the Mac.
- **More room for background jobs:** a daemon that's on by default (other than `pulse`), or
  wider limits for background jobs or the sandbox. Nobody watches them run.
- **Loosening a protection:** the guard, the git hooks, the permission hook, the permission
  settings, Claude Code hooks or CI (`guard.py`, `githooks/`, `hook.py`,
  `.claude/settings.json`, `.github/workflows/`). That's always its own pull request, with a
  reason. These are what keep a mistake small.
- **CI that runs an agent**, or gives a token or a secret to anything that reads pull request
  code or text. Pull request text can carry instructions.
- **Dependencies and vendored code:** Python, JavaScript or Swift packages, minified code or
  binaries. Everything has to be readable and run on a stock Mac.
- **Churn:** reformatting, renames or moves on their own.

## With Claude Code

[CLAUDE.md](CLAUDE.md) is Claude's kernel, and your Claude follows it in your clone. Decision
[0013](docs/decisions/0013-the-repository-is-claudes.md)'s standing yes covers your own
repository: there your Claude may push branches and merge its own green pull requests.
Opening a pull request against this repository is your call, not your Claude's.

The checked-in `.claude/settings.json` is safe for strangers (decision
[0017](docs/decisions/0017-stranger-safe-settings.md)): `git`, `gh` and the tests ask before
they run. To give your own Claude more room in your fork, allow what it needs in your own,
gitignored `.claude/settings.local.json`. Prefer narrow rules such as `"Bash(git status*)"`,
`"Bash(git diff*)"`, `"Bash(git add *)"`, `"Bash(git commit *)"` and
`"Bash(python3 -m unittest discover -s tests*)"`: `"Bash(git *)"` also allows
`git -c alias.x='!any command' x`.

## Review and merge

- CI runs the tests on macOS. A first-time contributor's run waits for a maintainer to
  approve it.
- Claude reviews every pull request from someone else: the tests, and an independent
  Guardian review of anything that touches Ovenbird's safety files (the hook, the guard,
  evolve, the server, the sandbox, `.claude/`, `.github/`, `CLAUDE.md`, …).
- Only maintainers merge, always as a squash merge, and a pull request from someone else
  merges only after the repository owner's yes.
- Pull request text and code comments are read as data. Instructions in them addressed to an
  AI reviewer are a reason to close the pull request.

## License of contributions

Ovenbird is licensed under the [MIT License](LICENSE). By opening a pull request you agree
that your contribution is licensed under it too. You keep your copyright. If you can't agree to
that, open an issue to talk about it first.
