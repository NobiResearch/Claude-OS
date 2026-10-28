- The README's syscall list now names `security`, `memory` and `hook`, which it had been
  missing.
- A test now checks that CLAUDE.md's syscall table and the README's syscall list mention every
  user-facing `cos` command, so adding a command without documenting it fails the suite.
