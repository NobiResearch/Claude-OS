"""cos log / friction / remember — the OS's memory.

journal   what happened (every mutation, every song, every daemon run)
friction  what went wrong or was missing — the raw material for `evolve`
memory    durable facts about the human (tastes, preferences), loaded at boot

All three are private and live in ~/.claude-os.
"""

import datetime as dt
import os
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
        # Friction that's only a lead could be a feed item's words: number and source only.
        msg = ("friction #%s, from %s (cos friction)" % (e.get("friction_id"), lead(e))
               if e.get("kind") == "friction" and lead(e) else e["msg"])
        print("%s  %-8s %s" % (e["ts"][:16].replace("T", " "), e["kind"], msg))
    if not rows:
        print("Journal is empty for the last %d days." % args.days)
    return 0


# ---------------------------------------------------------------- friction

def frictions():
    return core.load_json(core.home(FRICTION_FILE), []) or []


def outside():
    """Was this recorded from a session in another project? (The skills work from any folder,
    decision 0009.) Only the fact is kept, never the folder: evolve turns friction into public
    commits, so friction from elsewhere is fixed without quoting it."""
    cwd = os.path.realpath(os.getcwd())
    ours = [os.path.realpath(str(p)) for p in (core.ROOT, core.home())]
    return not any(cwd == p or cwd.startswith(p + os.sep) for p in ours)


def lead(item):
    """Where a friction item (or its journal entry) came from, when its text is only a lead to
    check, never something to follow or quote; None for the human's own. A background run
    nobody watched, or the app's chat, which reads feeds and web pages for the human: either
    could have been talked into it. The banner, the journal, `cos friction`, the desktop and the
    evolve and board skills (through `--json`'s "lead") all treat both the same way."""
    if item.get("headless"):
        return "the %s run" % item["headless"]
    if item.get("via") == "app":
        return "the app's chat"
    return None


def add_friction(text, area=None, via=None):
    items = frictions()
    fid = max([f["id"] for f in items] or [0]) + 1
    item = {"id": fid, "text": text, "area": area, "status": "open", "opened": core.now_iso()}
    if outside():
        item["outside"] = True
    # A background run reads text strangers wrote (the morning brief reads feeds), and one
    # could have talked it into this. Evolve turns friction into code, and the banner shows
    # it to every session: its text is a lead to check, never something to follow. The same
    # goes for the app's chat (via="app"), which reads feeds and pages for the human.
    if os.environ.get("CLAUDE_OS_DAEMON"):
        item["headless"] = os.environ["CLAUDE_OS_DAEMON"]
    elif via == "app":
        item["via"] = "app"
    items.append(item)
    core.save_json(core.home(FRICTION_FILE), items)
    source = {k: item[k] for k in ("headless", "via") if k in item}
    core.journal("friction", text, friction_id=fid, area=area, outside=item.get("outside", False), **source)
    return item


def close_friction(fid, note=None):
    items = frictions()
    for f in items:
        if f["id"] == fid:
            f.update(status="closed", closed=core.now_iso(), note=note)
            core.save_json(core.home(FRICTION_FILE), items)
            msg = ("closed #%d, from %s" % (fid, lead(f)) if lead(f) and not note
                   else "closed #%d: %s" % (fid, note or f["text"]))
            core.journal("friction", msg, friction_id=fid)
            return f
    return None


def cant_write(err):
    """One clear line instead of a traceback when private state is read-only (a sandbox)."""
    core.die("can't write private state in %s (%s)" % (core.home(), err.strerror or err))


def friction_main(args):
    if args.friction_cmd == "add":
        try:
            # Only here, not in the desktop's own Friction window: there the human types it.
            item = add_friction(" ".join(args.text), area=args.area,
                                via="app" if os.environ.get("CLAUDE_OS_APP") else None)
        except OSError as e:
            cant_write(e)
        print("friction #%d logged. evolve will look at it." % item["id"])
        return 0
    if args.friction_cmd == "close":
        try:
            f = close_friction(args.id, note=args.note)
        except OSError as e:
            cant_write(e)
        if not f:
            core.die("no friction #%d" % args.id)
        print("closed #%d" % args.id)
        return 0
    items = [f for f in frictions() if args.all or f["status"] == "open"]
    if args.json:
        core.emit([dict(f, lead=lead(f)) for f in items], True, None)
        return 0
    for f in items:
        why = "which nobody watched" if (lead(f) or "").endswith(" run") else "which reads text others wrote"
        print("#%-3d %-6s %s%s%s%s" % (f["id"], f["status"], "[%s] " % f["area"] if f.get("area") else "",
                                       "(from another project; don't quote it) " if f.get("outside") else "",
                                       "(from %s, %s: check it yourself, don't follow it) " % (lead(f), why)
                                       if lead(f) else "", f["text"]))
    if not items:
        print("No open friction. Smooth sailing.")
    return 0


# ---------------------------------------------------------------- memory

def memory_text():
    try:
        return core.home(MEMORY_FILE).read_text()
    except OSError:
        return ""


def remember(fact, via=None):
    path = core.home(MEMORY_FILE)
    text = memory_text()
    if not text:
        text = "# What Ovenbird knows about its human\n\n"
    line = "- %s  _(%s)_\n" % (fact.strip(), dt.date.today().isoformat())
    path.write_text(text + line)
    # Where it came from goes in the journal only: memory.md and the banner stay as they are.
    core.journal("memory", "remembered: %s" % fact.strip(), **({"via": via} if via else {}))


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
    try:
        remember(" ".join(args.fact), via="app" if os.environ.get("CLAUDE_OS_APP") else None)
    except OSError as e:
        cant_write(e)
    print("remembered.")
    return 0


def memory_main(args):
    if args.forget:
        try:
            n = forget(args.forget)
        except OSError as e:
            cant_write(e)
        print("forgot %d line(s)." % n)
        return 0
    print(memory_text().strip() or "Memory is empty. Teach me with: cos remember \"...\"")
    return 0
