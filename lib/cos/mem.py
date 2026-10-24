"""cos log / friction / remember — the OS's memory.

journal   what happened (every mutation, every song, every daemon run)
friction  what went wrong or was missing — the raw material for `evolve`
memory    durable facts about the human (tastes, preferences), loaded at boot

All three are private and live in ~/.claude-os.
"""

import datetime as dt
import re

from . import core

MEMORY_FILE = "memory.md"
FRICTION_FILE = "friction.json"


# ---------------------------------------------------------------- journal

def log_main(args):
    if args.log_cmd == "add":
        core.journal(args.kind, " ".join(args.text))
        return 0
    rows = core.read_journal(days=args.days, kind=args.kind)
    if args.json:
        core.emit(rows, True, None)
        return 0
    for e in rows[-args.limit:]:
        print("%s  %-8s %s" % (e["ts"][:16].replace("T", " "), e["kind"], e["msg"]))
    if not rows:
        print("Journal is empty for the last %d days." % args.days)
    return 0


# ---------------------------------------------------------------- friction

def frictions():
    return core.load_json(core.home(FRICTION_FILE), []) or []


def add_friction(text, area=None):
    items = frictions()
    fid = max([f["id"] for f in items] or [0]) + 1
    item = {"id": fid, "text": text, "area": area, "status": "open", "opened": core.now_iso()}
    items.append(item)
    core.save_json(core.home(FRICTION_FILE), items)
    core.journal("friction", text, friction_id=fid, area=area)
    return item


def close_friction(fid, note=None):
    items = frictions()
    for f in items:
        if f["id"] == fid:
            f.update(status="closed", closed=core.now_iso(), note=note)
            core.save_json(core.home(FRICTION_FILE), items)
            core.journal("friction", "closed #%d: %s" % (fid, note or f["text"]), friction_id=fid)
            return f
    return None


def friction_main(args):
    if args.friction_cmd == "add":
        item = add_friction(" ".join(args.text), area=args.area)
        print("friction #%d logged. evolve will look at it." % item["id"])
        return 0
    if args.friction_cmd == "close":
        f = close_friction(args.id, note=args.note)
        if not f:
            core.die("no friction #%d" % args.id)
        print("closed #%d" % args.id)
        return 0
    items = [f for f in frictions() if args.all or f["status"] == "open"]
    if args.json:
        core.emit(items, True, None)
        return 0
    for f in items:
        print("#%-3d %-6s %s%s" % (f["id"], f["status"], "[%s] " % f["area"] if f.get("area") else "", f["text"]))
    if not items:
        print("No open friction. Smooth sailing.")
    return 0


# ---------------------------------------------------------------- memory

def memory_text():
    try:
        return core.home(MEMORY_FILE).read_text()
    except OSError:
        return ""


def remember(fact):
    path = core.home(MEMORY_FILE)
    text = memory_text()
    if not text:
        text = "# What Claude OS knows about its human\n\n"
    line = "- %s  _(%s)_\n" % (fact.strip(), dt.date.today().isoformat())
    path.write_text(text + line)
    core.journal("memory", "remembered: %s" % fact.strip())


def forget(pattern):
    lines = memory_text().splitlines(True)
    rx = re.compile(re.escape(pattern), re.I)
    kept = [l for l in lines if not (l.startswith("- ") and rx.search(l))]
    removed = len(lines) - len(kept)
    core.home(MEMORY_FILE).write_text("".join(kept))
    if removed:
        core.journal("memory", "forgot %d line(s) matching %r" % (removed, pattern))
    return removed


def remember_main(args):
    remember(" ".join(args.fact))
    print("remembered.")
    return 0


def memory_main(args):
    if args.forget:
        n = forget(args.forget)
        print("forgot %d line(s)." % n)
        return 0
    print(memory_text().strip() or "Memory is empty. Teach me with: cos remember \"...\"")
    return 0
