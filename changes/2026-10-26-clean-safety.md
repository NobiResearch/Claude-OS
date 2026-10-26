- **`cos clean` is stricter about what it deletes:** never through a symlinked folder (a
  cache that links into Documents stays untouched), command cleanups run from the home folder
  so a project's own config can't redirect them, only items from your last scan (within a
  day) are removed, a downloaded folder with something recent inside isn't "old", running
  apps keep their caches, Poetry's and JetBrains' folders aren't treated as caches,
  `node_modules` needs a package.json and a lockfile, and `downloads-old trash` together is
  refused (it would empty the Trash the downloads just went to).
