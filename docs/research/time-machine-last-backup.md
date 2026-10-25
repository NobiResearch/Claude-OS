# When did Time Machine last back up, without Full Disk Access or mounting?

- **Asked:** 2026-10-26, by the board (0012 left the backup's age out of `cos backup`)
- **Status:** a likely answer, verified only partly (this Mac has no Time Machine destination)

## Answer

`defaults export /Library/Preferences/com.apple.TimeMachine -` returns Time Machine's system
preferences through `cfprefsd`, even though reading the same file directly is denied without
Full Disk Access. With a destination set up, each entry in `Destinations` carries
`SnapshotDates`, the dates of the backups on that disk; the newest is the last backup. It
mounts nothing and reads the same in every language.

## Evidence

- On macOS 27.0.1, `plutil -p /Library/Preferences/com.apple.TimeMachine.plist` says
  permission denied; `defaults export … -` prints the plist (exit 0, no prompt). (verified)
- A [Jamf thread](https://community.jamf.com/t5/jamf-pro/set-terminal-disc-access-in-jamf/m-p/312287)
  (March 2024) reads `Destinations` › `SnapshotDates` this way where PlistBuddy needs FDA.
  (verified for Sonoma by its authors; unverified on macOS 27 with a real destination)
- The keys `SnapshotDates`, `AttemptDates` and `LastDestinationID` still appear in macOS 27's
  system code; [Plaso](https://plaso.readthedocs.io/en/latest/_modules/plaso/parsers/plist_plugins/time_machine.html)
  documents `SnapshotDates` as the backup dates. (key presence verified; meaning per Plaso)
- `tmutil status -X` has no last-completed date (only `ClientID`, `Percent`, `Running`), and
  `tmutil destinationinfo` gives only name, kind, URL, mount point and ID. (verified)
- The unified log (`/usr/bin/log show --predicate 'subsystem == "com.apple.TimeMachine"'`;
  in zsh `log` is a builtin) is readable by an admin user and logs "Backup succeeded"
  ([Eclectic Light](https://eclecticlight.co/2023/11/08/time-machine-in-sonoma-how-to-check-backing-up/)),
  but its history here was about 16 hours, so it can't show that a backup is old. (verified)

## Recommendation

Read the age with `defaults export` and `plistlib` in pulse, with a timeout; anything
missing is unknown, and unknown is never a signal (0005). A signal only when the newest
`SnapshotDates` is over a week old. Verify on a Mac with a real destination before relying
on it, and keep the log out of it. Note the date is when the backup's snapshot was taken, a
few minutes before it finished.

## Open questions (unverified)

- Does `cfprefsd` return `Destinations` without FDA on macOS 27 once a destination exists?
- Is `SnapshotDates` kept for network destinations, and are failed backups left out?
- What does `AttemptDates` hold?
