- `cos evolve merge` and the Evolve window's Merge button wait for CI to start before watching
  it. They used to report "CI didn't pass" when a pull request's checks hadn't shown up yet.
  The merge is pinned to the commit the Guardian and the tests checked.
