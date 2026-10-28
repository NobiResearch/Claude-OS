- **Night shift answers only for its own pull requests** (decision 0023). It no longer
  approves any `gh api` call, and it approves pull request text only for Claude's own `night/…`
  pull requests in this repository, from a clean checkout whose only remote is origin. It never
  answers a prompt one of the checked-in ask rules exists to show, and every approval goes in
  your journal.
