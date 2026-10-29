- Inside a sandbox (Claude Code's, or the nightly evolve run's), `cos security` and
  `cos status` no longer say the firewall is off when they can't tell. There, macOS's own
  firewall tool can't reach its service and answers "disabled" whatever the truth; now that
  reads as "couldn't tell" (?).
