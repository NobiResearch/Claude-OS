- **Night shift answers only for its own pull requests** (decision 0023). It no longer
  approves any `gh api` call, and it approves pull request text only for Claude's own `night/…`
  pull requests in this repository, from a checkout whose only remote is origin. It never
  answers a prompt one of the checked-in ask rules exists to show, and every approval goes in
  your journal.
- **Fixed: with Night shift on, a crafted pull request command could carry another command
  past the hook.** The hook read `--title x#; <command>` as a title, while the shell ran the
  command after it. Now anything outside quotes that the shell reads differently (`#`, braces,
  globs, `~`, `=`, `!`) makes the hook answer nothing, and so does a body file it can't be sure
  gh would read the same way.
