# 0012 — `cos backup`, and what waits

- **Status:** accepted
- **Date:** 2026-10-26
- **Decided by:** the board, overnight (night shift)

## Context

"Time Machine isn't set up" has been in every boot banner since 0005, and nothing helps
the human act on it. The board ranked four candidates for the night: `cos backup`, `cos
power` (what keeps the Mac awake), a daily music mix, and a `pre-push` Guardian hook.

## Votes

| Seat | Ranking | Top reason |
|---|---|---|
| Architect | backup, power, mix, pre-push | The backup reader already exists in `status.py`; extend it. The mix needs a queue the player lacks; the pre-push hook has no range mode yet. |
| Guardian | power, pre-push, backup, mix | Volume names are personal, and "recommend a disk" could steer toward one Time Machine erases. A daily mix written in the same run that reads feeds could be steered. |
| Steward | mix, backup, pre-push, power | Music is daily; a backup helper mostly repeats a signal while no disk is plugged in. |
| Skeptic | pre-push, backup, mix, power | The backup's age can't be read honestly without Full Disk Access; `cos power` would mostly report our own `caffeinate`. |

**Decided:** `cos backup` (most points), at the scope below; the `pre-push` hook next.
`cos power` and the mix wait (Ideas), until the human asks.

## Decision

- **`cos backup`** (read-only, `lib/cos/backup.py`, which now owns the Time Machine reader
  `status` uses):
  - whether Time Machine has a destination (`tmutil destinationinfo`, which mounts nothing);
  - about how much there is to back up (the data volume's `CapacityInUse`);
  - each physical external volume from `diskutil`'s plists: format, size, use, and a plain
    verdict (too small, tight, big enough), saying when Time Machine would erase it (a disk
    that isn't APFS and isn't empty). Disk images, such as simulator runtimes, don't count.
  - It suggests the biggest disk that fits and wouldn't be erased, empty ones first; with
    none connected, it says what size to plug in.
- **Never:** the last backup's age (no honest source without Full Disk Access or mounting),
  listing or opening anything on a disk, `tmutil enable|setdestination|startbackup`. Volume
  names go to the screen and `--json` only: never the journal, caches, signals or tests.
- **`cos backup setup`** opens Time Machine's settings, where the human chooses the disk.
  It's refused in background jobs.
- The banner's note now reads "Time Machine isn't set up: cos backup".
