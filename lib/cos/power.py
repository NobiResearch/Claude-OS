"""cos power — what keeps the Mac or display awake? (read-only)

`pmset -g assertions` lists the processes holding sleep assertions.
This module reports only the three assertions that actually keep the
Mac or its display awake, with how long each has held them.

Privacy: the `named:` string in pmset output can name a document, so
it is never captured, stored, printed, or emitted as JSON. Only the
pid, the process name from the `pid 123(name):` prefix, the assertion,
and the duration leave this module. Nothing is journalled or cached.
"""

import re

from . import core

TARGET_ASSERTIONS = (
    "PreventUserIdleSystemSleep",
    "PreventUserIdleDisplaySleep",
    "PreventSystemSleep",
)

# pmset holder lines vary: the (process) name and the duration
# are both optional, e.g.
#   pid 1234(caffeinate): [0x...] 00:42:10 PreventUserIdleSystemSleep named: "..."
#   pid 194: [0x...] PreventUserIdleSystemSleep named: "..."
# The duration is %02d:%02d:%02d, a minimum width: hours keep counting
# past 99, so the hour field is \d+, not \d\d, or a holder at 100+ hours
# would silently disappear from the output.
# Only pid lines are matched, so the system-wide summary (no pid) can
# never double-count. The named: string is matched but not captured.
_HOLDER = re.compile(
    r"^\s*pid\s+(\d+)(?:\(([^)]*)\))?:\s*\[0x[0-9a-fA-F]+\]\s+"
    r"(?:(\d+:\d\d:\d\d)\s+)?(Prevent\w+)\s+named:\s*\"[^\"]*\"",
    re.M)


def _duration_seconds(hms):
    if not hms:
        return None
    try:
        h, m, s = (int(part) for part in hms.split(":"))
    except ValueError:
        return None
    return h * 3600 + m * 60 + s


def _format_duration(seconds):
    if seconds is None:
        return "unknown duration"
    if seconds < 60:
        return "%d s" % seconds
    minutes = seconds // 60
    if minutes < 60:
        return "%d min" % minutes
    hours, minutes = divmod(minutes, 60)
    return "%d h %d min" % (hours, minutes)


def parse_assertions(out):
    """Holders from `pmset -g assertions` output, filtered to
    TARGET_ASSERTIONS only. Each dict: pid, process, assertion,
    duration (HH:MM:SS or None), duration_seconds (int or None).
    Empty or garbage input -> []. Never raises on malformed lines."""
    holders = []
    if not out:
        return holders
    for match in _HOLDER.finditer(out):
        pid, process, duration, assertion = match.groups()
        if assertion not in TARGET_ASSERTIONS:
            continue
        try:
            pid_int = int(pid)
        except ValueError:
            continue
        holders.append({
            "pid": pid_int,
            "process": process or None,
            "assertion": assertion,
            "duration": duration,
            "duration_seconds": _duration_seconds(duration),
        })
    return holders


def check():
    """{"holders": [...], "preventing": bool, "available": bool}.
    rc != 0 (e.g. pmset missing) -> available False, holders []."""
    r = core.run(["pmset", "-g", "assertions"], timeout=3)
    if not r.ok:
        return {"holders": [], "preventing": False, "available": False}
    holders = parse_assertions(r.out)
    return {"holders": holders, "preventing": bool(holders), "available": True}


def render(r):
    """Human output; never prints None for a missing duration/process."""
    if not r.get("available", True):
        print("? pmset is not available, so sleep assertions could not be read.")
        return
    holders = r.get("holders") or []
    if not holders:
        print("✓ Nothing is keeping the Mac awake.")
        return
    # Count assertions, not processes: one app can hold two assertions.
    if len(holders) == 1:
        print("• 1 sleep assertion keeping the Mac awake:")
    else:
        print("• %d sleep assertions keeping the Mac awake:" % len(holders))
    for h in holders:
        process = h.get("process") or "unknown process"
        print("  %s (pid %s) — %s, %s" % (
            process, h.get("pid"), h.get("assertion"),
            _format_duration(h.get("duration_seconds"))))


def main(args):
    r = check()
    core.emit(r, args.json, render)
    return 0
