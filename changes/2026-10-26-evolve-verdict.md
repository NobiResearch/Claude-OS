- An evolve branch whose tests failed in the sandbox now says so in the boot banner
  ("evolve/2026-10-26 (its tests FAIL)"), in `cos evolve` and on its card in the desktop's
  Evolve window. The verdict used to be only in the journal, so a failing branch looked like a
  good one. A branch that moved since its last run shows no verdict.
- The Evolve window's Merge dialog now says what Merge does: it pushes the branch, opens a pull
  request and squash-merges it once CI passes. It used to say "Nothing is pushed."
