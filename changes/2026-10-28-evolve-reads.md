- **The nightly evolve run can no longer read your private folders:** `~/.ssh`, `~/.aws`,
  `~/.config/gh`, `~/.claude`, the Keychains and the rest. That holds for its shell and the code
  it runs (the sandbox), and for its Read tool (deny rules). `~/.claude-os` stays readable for now:
  the run's workspace and its input live there.
