"""cos boot / statusline — what Claude (and you) see when Claude OS starts.

`boot` runs as Claude Code's SessionStart hook: its output becomes part of
Claude's context, so it must be fast and dense. Its one network call is a git fetch of
main, at most every 10 minutes and never longer than 4 seconds (decision 0011).
`statusline` feeds Claude Code's status bar and must be faster still.
"""

import datetime as dt
import json
import os
import sys

from . import __version__, core

DIM, RESET, ACCENT = "\033[2m", "\033[0m", "\033[38;5;173m"


def _music_now(max_age=20):
    if not core.app_running("Music"):
        return None
    cached = core.cache_get("music-now", max_age=max_age)
    if cached:
        return cached["data"]
    from . import music
    n = music.now()
    core.cache_put("music-now", n)
    return n


def _catch_up_line():
    """What's merged on GitHub and not on this Mac, so a session never works from stale
    Claude OS without knowing (friction #16). It never moves the code itself."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return None
    from . import evolve
    try:
        c = evolve.catch_up(fetch=True, source="boot")
    except Exception:
        return None
    if not c["behind"]:
        return None
    n, shown = len(c["subjects"]), c["subjects"][:3]
    line = "  ↓ Claude OS: %d change%s merged on GitHub, not on this Mac: %s%s" % (
        n, "" if n == 1 else "s", " · ".join(shown), " (+%d more)" % (n - 3) if n > 3 else "")
    line += (" — not updated: %s" % c["why"]) if c["why"] else " — update: cos update apply claude-os --yes"
    if c["protected"]:
        line += "\n    the gate changes too: %s" % ", ".join(c["protected"][:4])
    return line


def boot():
    from . import status, mem, daemon, evolve
    s = status.collect(include_slow=False)
    sy, d, m, b = s["system"], s["disk"], s["memory"], s["battery"]
    now = dt.datetime.now()
    lines = ["◆ Claude OS %s · %s" % (__version__, now.strftime("%A %d %b %Y, %H:%M"))]
    lines.append("  %s · macOS %s · %s · up %s" % (sy["model"], sy["macos"], sy["chip"], status.fmt_uptime(s["uptime"])))
    vit = "  disk %s free (%s%%) · memory %s/%s" % (core.human_bytes(d["free"]), d["free_pct"],
                                                    core.human_bytes(m["used"]), core.human_bytes(m["total"]))
    if b:
        vit += " · battery %d%% %s" % (b["percent"], b["state"])
    lines.append(vit)
    if s["signals"]:
        lines.append("  signals: " + " · ".join(("⚠ " if x["level"] == "warn" else "") + x["msg"] for x in s["signals"]))
    n = _music_now()
    if n and n.get("track"):
        lines.append("  music: %s %s — %s" % ("▶" if n.get("state") == "playing" else "❚❚", n["track"], n.get("artist") or ""))
    open_f = [f for f in mem.frictions() if f["status"] == "open"]
    if open_f:
        lines.append("  friction: %d open (cos friction) — latest: %s" % (len(open_f), open_f[-1]["text"][:90]))
    behind = _catch_up_line()
    if behind:
        lines.append(behind)
    waiting = evolve.branches()
    if waiting:
        lines.append("  evolve: %d branch(es) awaiting review: %s (cos evolve)" % (len(waiting), ", ".join(waiting[:3])))
    try:
        ds = daemon.status()
        lines.append("  daemons: " + "  ".join("%s %s" % (r["name"], "●" if r["loaded"] else "–") for r in ds))
    except Exception:
        pass
    memory = mem.memory_text().strip().splitlines()
    facts = [l for l in memory if l.startswith("- ")]
    if facts:
        lines.append("  memory (what you've learned about your human):")
        lines += ["    " + f for f in facts[-40:]]
    else:
        lines.append("  memory: empty — learn preferences as you go (cos remember \"...\")")
    if os.environ.get("CLAUDE_OS_APP"):
        lines.append("  mode: Claude OS app — your replies render as Markdown in a chat window; tool calls show"
                     " as chips, and the human approves anything that needs permission in a dialog. Keep it"
                     " conversational and brief; the app has visual Storage, Updates, Music and Feeds windows.")
    if os.environ.get("CLAUDE_OS_DAEMON"):
        lines.append("  mode: headless daemon run (%s) — no human is watching; never wait for input." % os.environ["CLAUDE_OS_DAEMON"])
    print("\n".join(lines))
    return 0


def statusline():
    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except ValueError:
        payload = {}
    parts = [ACCENT + "◆ Claude OS" + RESET]
    model = (payload.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    try:
        from .status import disk
        parts.append("%s free" % core.human_bytes(disk()["free"]).replace(".0 ", " "))
    except OSError:
        pass
    n = _music_now()
    if n and n.get("track") and n.get("state") == "playing":
        parts.append("♫ %s — %s" % (n["track"][:28], (n.get("artist") or "")[:20]))
    upd = core.cache_get("updates")
    if upd and upd["data"].get("total"):
        parts.append("%d updates" % upd["data"]["total"])
    try:
        from .mem import frictions
        open_f = sum(1 for f in frictions() if f["status"] == "open")
        if open_f:
            parts.append("%d friction" % open_f)
    except Exception:
        pass
    print((DIM + " │ " + RESET).join(parts))
    return 0
