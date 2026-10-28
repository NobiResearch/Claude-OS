- **More things count as private:** Claude Code's account file (`~/.claude.json` and its
  backup), more logins (git's stored credentials, Docker, Kubernetes, Google Cloud, Azure, PyPI,
  Cargo, RubyGems, `pass`), and the histories shells and tools keep (zsh, bash, fish, Python,
  Node, psql, MySQL, SQLite, less, Vim), where they keep them by default. The nightly evolve
  run can't read them, the code it writes and tests can't either, and a pull request text can't
  be taken from them.
