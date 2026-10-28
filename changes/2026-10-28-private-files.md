- **Two more things count as private:** Claude Code's account file (`~/.claude.json` and its
  backup) and your shell histories (zsh's and bash's). The nightly evolve run can't read them,
  the code it writes and tests can't either, and a pull request text can't be taken from them.
