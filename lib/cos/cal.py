"""cos cal — today's events and due reminders.

Claude OS.app reads them with EventKit (it holds the Calendars/Reminders grant; `cos`
never asks for it) and writes ~/.claude-os/state/agenda.json. Nothing is read until the
human connects it once, from Settings or `cos cal connect` (decision 0002).
"""

import datetime as dt
import time

from . import core

STALE_SECONDS = 15 * 60


def state():
    return core.load_json(core.home("state", "agenda.json"), None)


def connected(s=None):
    s = s if s is not None else state()
    return bool(s) and s.get("calendar") == "connected"


def _ask_app(command, wait):
    before = (state() or {}).get("ts", 0)
    url = core.app_url("calendar/%s" % command) if command == "connect" else "claude-os://calendar/%s" % command
    r = core.run(["open", "-g", url], timeout=15)
    if not r.ok:
        return None
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.5)
        s = state()
        if s and s.get("ts", 0) > before:
            return s
    return None


def connect(wait=90):
    """Ask Claude OS.app to request access (macOS shows its prompts) and read the agenda."""
    if not core.ensure_app():
        return state()
    return _ask_app("connect", wait) or state()


def agenda(refresh=False):
    s = state()
    # Only ask a running app; launching Claude OS from a background job would pop its window up.
    if connected(s) and core.app_running("ClaudeOS") and (refresh or time.time() - s.get("ts", 0) > STALE_SECONDS):
        s = _ask_app("refresh", 6) or s
    return s or {"calendar": "not connected", "reminders": "not connected"}


def day_view(s, now=None):
    """Split the agenda into today / tomorrow / reminders due (today or overdue)."""
    now = now or time.time()
    today = dt.datetime.fromtimestamp(now).date()
    tomorrow = today + dt.timedelta(days=1)
    out = {"connected": connected(s), "today": [], "tomorrow": [], "reminders": [],
           "calendars": (s or {}).get("calendars"), "reminder_lists": (s or {}).get("reminder_lists")}
    for e in (s or {}).get("events") or []:
        start = dt.datetime.fromtimestamp(e["start"])
        end = dt.datetime.fromtimestamp(e["end"])
        item = {"title": e.get("title"), "calendar": e.get("calendar"), "all_day": bool(e.get("all_day")),
                "start": e["start"], "end": e["end"], "location": e.get("location") or "",
                "when": "all day" if e.get("all_day") else "%s–%s" % (start.strftime("%H:%M"), end.strftime("%H:%M")),
                "past": not e.get("all_day") and e["end"] < now}
        if start.date() <= today <= end.date() and (e.get("all_day") or start.date() == today or end > dt.datetime.fromtimestamp(now)):
            out["today"].append(item)
        elif start.date() == tomorrow:
            out["tomorrow"].append(item)
    for r in (s or {}).get("reminders_due") or []:
        due = dt.datetime.fromtimestamp(r["due"])
        if due.date() <= today:
            out["reminders"].append({"title": r.get("title"), "list": r.get("list"), "due": r["due"],
                                     "overdue": due.date() < today})
    return out


def render(v):
    if not v["connected"]:
        print("Calendar isn't connected. Connect it in Claude OS › Settings, or: cos cal connect")
        return
    print("Today")
    for e in v["today"] or []:
        print("  %-12s %s%s" % (e["when"], e["title"], "  (done)" if e["past"] else ""))
    if not v["today"]:
        print("  nothing on the calendar")
    if v["tomorrow"]:
        print("Tomorrow")
        for e in v["tomorrow"][:5]:
            print("  %-12s %s" % (e["when"], e["title"]))
    if v["reminders"]:
        print("Reminders due")
        for r in v["reminders"]:
            print("  · %s%s" % (r["title"], "  (overdue)" if r["overdue"] else ""))


def main(args):
    if args.cal_cmd == "connect":
        s = connect()
        v = day_view(s or {})
        print("Calendar: %s · Reminders: %s" % ((s or {}).get("calendar", "?"), (s or {}).get("reminders", "?")))
        if v["connected"]:
            render(v)
        return 0 if v["connected"] else 1
    v = day_view(agenda(refresh=args.refresh))
    core.emit(v, args.json, render)
    return 0
