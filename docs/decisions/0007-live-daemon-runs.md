# 0007 — Live daemon runs: watch the board meet

- **Status:** accepted
- **Date:** 2026-10-25
- **Decided by:** the board, on the human's request

## Context

Ten minutes into the first weekly meeting, the human asked: "Is that something I can see
in Claude OS, or is it more behind the scenes with a recap shown when it's done?" They could
see nothing. Daemons ran `claude -p --output-format text`, which writes only when a run
ends. The only notification read "Board seats are deliberating." That was the first line of
the run's chatter, and it arrived 14 minutes after the meeting had finished: the chair had
scheduled a 20-minute wakeup "in case the seats never report back", and the pending wakeup
kept the run alive until its timeout killed it. The minutes were complete, but the app
showed them with the chatter and a stderr section holding the whole command line.

## Votes

| Seat | Vote | Top reason |
|---|---|---|
| Architect | amend | Parsing belongs in the runner, not in a skill. Live means the runner is alive, not that it spoke lately. Keep the partial output on a timeout. |
| Guardian | amend | The timeout is the only bound on a Pro or Max plan, so the new runner must kill on time whatever the output does. The live file holds labels only, and a click target comes from a fixed list. |
| Steward | amend | They asked for it. One notification at the end that says what happened, the minutes without the chatter, and a click that opens them. |
| Skeptic | amend | Most of the itch is a bug: fix the hang and the summary first. Doubted that stream-json shows the seats. |

**Approved, with conditions.** The chair settled the Skeptic's doubt with a test run on
Claude Code 2.1.310. Stream-json reports every background agent with `task_started` and
`task_notification` events, and the agent's answer is in the event's summary. Per-seat
progress therefore needs no undocumented formats. If those events ever stop coming, the
tab still shows "In session · N min".

## Decision

1. **Fix the hang.** Daemons deny `ScheduleWakeup`, `CronCreate`, `CronDelete`, `Monitor`
   and `RemoteTrigger`, and the board skill says not to wait on timers.
2. **A streaming runner.** `core.stream` sits next to `core.run` with the same promises. It
   never raises. The deadline is a timer that doesn't wait for output. stderr drains on its
   own thread, keeping a short tail. The process group is killed on timeout, on errors and
   when the run ends. `claude_command` changes only to `--output-format stream-json
   --verbose`, and every other flag stays as it was (a test checks this).
3. **The output.** The same as text mode: each turn's final text. On a timeout, the
   unfinished turn's latest text is kept too. stderr goes to a private `.err` file next to
   the run, never into the minutes.
4. **The live file.** `~/.claude-os/state/live/<name>.json` (mode 0600, written atomically,
   removed when the run ends) holds labels only:
   - the runner's pid and start time;
   - each agent's type, state and vote, the vote matched by `VOTE: approve|amend|reject`;
   - the current tool's name, or `cos <verb>` for Bash.

   Never tool inputs, results or free text. A run is live while its runner's pid is alive
   and it's younger than its timeout allows.
5. **The app.**
   - Evolution › Board shows "In session · N min", with each seat waiting, deliberating or
     voted. It checks every 5 seconds, only while a meeting runs and the tab is open, then
     shows the minutes. The chatter before the minutes' first heading is folded away under
     "How the meeting went".
   - Settings › Background jobs says "running now · N min", and `cos daemon list` does too.
   - No other daemon gets its own live view.
6. **One notification, at the end, saying what happened.** It gives the run's first heading
   (for example "Board minutes — weekly review"), or says that it ran out of time or stopped
   with an error. It names a click target from a fixed list (`board`, `brief`, `evolve`,
   `daemons`). The app's routing for the target is a separate change; until then the
   desktop ignores it.

The board's timeout stays at 20 minutes. The meeting needed 6.

## Not chosen

- **`cos board progress` from the skill.** It depends on the model remembering, needs a new
  write path into state the page renders, and can't write from evolve's sandbox.
- **Only a timer from the lock file.** It's the fallback, not the feature: it doesn't answer
  "can I see it".
- **Raising the board's timeout.** The meeting didn't need more time; it was stuck on a
  wakeup.
