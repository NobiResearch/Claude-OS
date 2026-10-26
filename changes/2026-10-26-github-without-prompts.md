- Claude no longer asks before pushing, opening or merging pull requests in the Claude OS
  repository, even with `--dangerously-skip-permissions` on. The Guardian still blocks
  private data in every commit, push and pull request, `main` still takes only green pull
  requests, and deleting the repository still asks (decision 0013).
