# Security

Claude OS sees a lot of a Mac: files, music, the calendar, the network. A hole in it matters,
so please report one privately.

## How to report

Use GitHub's private vulnerability reporting: the repository's **Security** tab, then
**Report a vulnerability**
([direct link](https://github.com/markusskov/Claude-OS/security/advisories/new)). Please don't
open a public issue or pull request for it. Say what you found, how to reproduce it, and what
it lets someone do. Leave your own private data out of the report.

## What counts

- Private data reaching the repository or GitHub past the Guardian: the pre-commit and
  pre-push hooks, or the scan of pull request text.
- A way out of the sandbox that runs model-written tests (`core.run_sandboxed`): reading the
  home folder, reaching the network or another app, writing outside its own folders.
- A command that changes the Mac without the human's yes, or that runs from a background job.
- The desktop's local server answering without its per-launch token, or another website
  driving it.
- Code from GitHub reaching a Mac outside [decision 0011](docs/decisions/0011-catching-up-with-main.md)'s
  rules.

## What happens next

We'll confirm we got your report, work on a fix privately, and publish it with a security
advisory. We'll credit you unless you'd rather we didn't.
