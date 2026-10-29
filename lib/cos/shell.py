"""cos boot / statusline — what Claude (and you) see when Ovenbird starts.

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

DIM, RESET, ACCENT = "\033[2m", "\033[0m", "\033[38;5;172m"  # 172: the 256-color nearest Crown


def _music_now(max_age=20):
    """What's playing, for the banner and the status line. Music.app is asked only once a
    person's `cos music` has talked to it here (music.asked): before that, or with Music closed,
    only Ovenbird's own player, read from its state file, since the first AppleScript to Music
    shows macOS's dialog. Anything odd there means no music line, never a broken banner."""
    from . import music
    try:
        if not music.asked() or not core.app_running("Music"):
            own = music.own_player_active()
            return music._own_now(own) if own else None
        cached = core.cache_get("music-now", max_age=max_age)
        if cached:
            return cached["data"]
        n = music.now()
        core.cache_put("music-now", n)
        return n
    except Exception:
        return None


def _caught_up_line():
    """Once, after Ovenbird moved itself forward (0011): what came in."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return None  # it's for the human, so a background job's banner doesn't use it up
    done = core.cache_get("caught-up")
    if not done:
        return None
    core.home("cache", "caught-up.json").unlink(missing_ok=True)  # two sessions may boot at once
    d = done["data"]
    n = len(d["subjects"])
    line = "  ↑ Ovenbird caught up with main (%s, %s): %s%s — this session read the old CLAUDE.md; " \
           "read it again for new commands" % (d["source"], core.ago(done["ts"]), " · ".join(d["subjects"][:3]),
                                               " (+%d more)" % (n - 3) if n > 3 else "")
    if d["protected"]:
        line += "\n    the gate changed: %s" % ", ".join(d["protected"][:4])
    return line


def _catch_up_line():
    """What's merged on GitHub and not on this Mac, so a session never works from stale
    Ovenbird without knowing (friction #16). A terminal session catches up first when Keep
    Ovenbird up to date is on and the app isn't running (its server would mix versions)."""
    if os.environ.get("CLAUDE_OS_DAEMON") or core.downloaded():
        return None  # a downloaded copy follows its app, not main (0015)
    from . import evolve
    try:
        terminal = not os.environ.get("CLAUDE_OS_APP") and not evolve.code_in_use()
        c = (terminal and evolve.auto_catch_up("boot")) or evolve.catch_up(fetch=True, source="boot")
    except Exception:
        return None
    if c["updated"]:
        return _caught_up_line()
    if not c["behind"]:
        return None
    n, shown = len(c["subjects"]), c["subjects"][:3]
    line = "  ↓ Ovenbird: %d change%s merged on GitHub, not on this Mac: %s%s" % (
        n, "" if n == 1 else "s", " · ".join(shown), " (+%d more)" % (n - 3) if n > 3 else "")
    if c["why"]:
        line += " — not updated: %s" % c["why"]
    elif core.config()["autonomy"].get("catch_up"):
        line += " — it comes in when Ovenbird.app restarts (menu bar: Update)"
    else:
        line += " — update: cos update apply claude-os --yes"
    if c["protected"]:
        line += "\n    the gate changes too: %s" % ", ".join(c["protected"][:4])
    return line


def _evolve_line():
    """Evolve branches waiting, with the ones whose tests failed in the sandbox marked: the
    verdict used to be only in the journal, so a failing branch read as a good one (friction #18)."""
    from . import evolve
    waiting = evolve.branches()
    if not waiting:
        return None
    ok = evolve.verdicts(waiting[:3])
    named = ", ".join(b + (" (its tests FAIL)" if ok[b] is False else "") for b in waiting[:3])
    return "  evolve: %d branch(es) awaiting review: %s (cos evolve)" % (len(waiting), named)


def _friction_line():
    """Open friction, and the latest one's text, unless it's only a lead (a background run or
    the app's chat logged it, mem.lead): that text could come from a feed item, and the banner
    puts it in front of every session."""
    from . import mem
    open_f = [f for f in mem.frictions() if f["status"] == "open"]
    if not open_f:
        return None
    last = open_f[-1]
    latest = ("#%d, from %s (cos friction)" % (last["id"], mem.lead(last)) if mem.lead(last)
              else last["text"][:90])
    return "  friction: %d open (cos friction) — latest: %s" % (len(open_f), latest)


def _vitals(s):
    """The banner's machine and vitals lines, without what couldn't be read (status.known)."""
    from . import status
    sy, d, m, b = s["system"], s["disk"], s["memory"], s["battery"]
    up = "up " + status.fmt_uptime(s["uptime"]) if s["uptime"] is not None else ""
    machine = status.known(sy["model"], "macOS %s" % sy["macos"] if sy["macos"] else "", sy["chip"], up)
    used = core.human_bytes(m["used"]) + ("/" + core.human_bytes(m["total"]) if m["total"] else " used")
    vit = "  disk %s free (%s%%) · memory %s" % (core.human_bytes(d["free"]), d["free_pct"], used)
    if b:
        vit += " · battery %d%% %s" % (b["percent"], b["state"])
    return (["  " + machine] if machine else []) + [vit]


def boot():
    from . import status, mem, daemon, system
    try:
        system.keep_download_settings()  # before this session's Claude does anything (0015)
    except Exception:
        pass
    s = status.collect(include_slow=False)
    now = dt.datetime.now()
    lines = ["◆ Ovenbird %s · %s" % (__version__, now.strftime("%A %d %b %Y, %H:%M"))]
    lines += _vitals(s)
    if s["signals"]:
        lines.append("  signals: " + " · ".join(("⚠ " if x["level"] == "warn" else "") + x["msg"] for x in s["signals"]))
    n = _music_now()
    if n and n.get("track"):
        lines.append("  music: %s %s — %s" % ("▶" if n.get("state") == "playing" else "❚❚", n["track"], n.get("artist") or ""))
    for line in (_friction_line(), _caught_up_line(), _catch_up_line()):
        if line:
            lines.append(line)
    line = _evolve_line()
    if line:
        lines.append(line)
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
        lines.append("  mode: Ovenbird app — your replies render as Markdown in a chat window; tool calls show"
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
    # NO_COLOR set to anything (no-color.org) means plain text.
    dim, reset, accent = ("", "", "") if os.environ.get("NO_COLOR") else (DIM, RESET, ACCENT)
    parts = [accent + "◆ Ovenbird" + reset]
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
    print((dim + " │ " + reset).join(parts))
    return 0
