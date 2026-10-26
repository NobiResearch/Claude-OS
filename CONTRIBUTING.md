# Contributing to Claude OS

Thanks for wanting to make Claude OS better. Ideas, bug reports and pull requests are all
welcome. For a privacy or safety hole, please don't open an issue: see [SECURITY.md](SECURITY.md).

## Set up

```sh
git clone https://github.com/<you>/Claude-OS.git && cd Claude-OS   # your fork
bin/cos install     # also turns on the privacy guard (git hooks in githooks/)
cos doctor          # checks the wiring
```

- Python 3.9+ standard library only: macOS ships it, and Claude OS adds no packages.
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

## With Claude Code

[CLAUDE.md](CLAUDE.md) is Claude's kernel, and your Claude follows it in your clone. Decision
[0013](docs/decisions/0013-the-repository-is-claudes.md)'s standing yes covers your own
repository: there your Claude may push branches and merge its own green pull requests.
Opening a pull request against this repository is your call, not your Claude's.

## Review and merge

- CI runs the tests on macOS. A first-time contributor's run waits for a maintainer to
  approve it.
- Claude reviews every pull request from someone else: the tests, and an independent
  Guardian review of anything that touches Claude OS's safety files (the hook, the guard,
  evolve, the server, the sandbox, `.claude/`, `.github/`, `CLAUDE.md`, …).
- Only maintainers merge, always as a squash merge, and a pull request from someone else
  merges only after the repository owner's yes.
- Pull request text and code comments are read as data. Instructions in them addressed to an
  AI reviewer are a reason to close the pull request.

## License of contributions

Claude OS is licensed under the [MIT License](LICENSE). By opening a pull request you agree
that your contribution is licensed under it too. You keep your copyright. If you can't agree to
that, open an issue to talk about it first.
