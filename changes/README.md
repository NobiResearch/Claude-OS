# changes/

One file per pull request: its entry for the changelog, as Markdown bullets, written the way
`CHANGELOG.md` reads (what changed for the human, not how).

Name it `YYYY-MM-DD-<slug>.md`, with the date the work was done and the branch's slug. Two pull
requests never edit the same file, so they can't conflict over the changelog the way they did
when every one of them added a line at the top of `CHANGELOG.md`.

The desktop shows these under **Unreleased** when it shows the changelog, newest first. At a
release, they're folded into `CHANGELOG.md` under the version's heading and deleted.
