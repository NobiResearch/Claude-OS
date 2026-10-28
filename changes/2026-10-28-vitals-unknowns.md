- The Vitals card leaves out what macOS wouldn't tell it, the way `cos status` already does:
  where `sysctl` and `ps` are refused (inside Claude Code's sandbox, say), it no longer prints
  "swap 0 B", "of 0 B" beside a meter that divides by zero, "0 cores", or an empty model and
  chip.
