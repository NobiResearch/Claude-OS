- `cos status` and the session's boot banner leave out what macOS wouldn't tell them, instead
  of making it up. Where `sysctl` and `ps` are refused (inside Claude Code's sandbox, say),
  they used to print "0 cores", "used of 0 B", "swap 0 B", an empty load and empty top-process
  lines. Swap that couldn't be read is now unknown in `--json` too (`null`, not 0).
