"""cos startup — what starts with this Mac, read-only (decision 0004).

By default it reads the launchd plists in ~/Library/LaunchAgents, /Library/LaunchAgents and
/Library/LaunchDaemons (plus launchctl's on/off overrides), which needs no permission.
`--full` reads macOS's Background Task Management records instead (`sfltool dumpbtm`, the
list behind System Settings › General › Login Items & Extensions, apps included); on recent
macOS that shows an admin password dialog, so it only runs when the human asked for it, and
never in a background job. Either way it checks each executable's code signature and puts
the odd ones first: missing executables, unsigned or ad-hoc code, things that are on but
haven't run in months. It never changes anything; the human (or Claude, with an Allow) does
that in System Settings.
"""

import datetime as dt
import os
import plistlib
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from . import core

STALE_DAYS = 90
TYPES = {"app": "app", "login item": "login item", "legacy agent": "launch agent",
         "legacy daemon": "launch daemon", "agent": "launch agent", "daemon": "launch daemon",
         "developer": "developer group", "curated": "system"}


def parse_btm(text):
    """Items from `sfltool dumpbtm`, tagged with the section's owner (uid)."""
    items, item, uid = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"Records for UID (-?\d+)", line)
        if m:
            uid = int(m.group(1))
            continue
        if re.match(r"#\d+:$", line) and raw.startswith(" #"):
            item = {"uid": uid}
            items.append(item)
            continue
        if item is None or ":" not in line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        item[key.strip().lower().replace(" ", "_")] = value.strip()
    return [normalize(i) for i in items if i.get("name") or i.get("identifier")]


def home_path(path):
    """BTM writes home folders as /Users/<uid>/…; map that back to the real home."""
    prefix = "/Users/%d/" % os.getuid()
    return os.path.expanduser("~") + "/" + path[len(prefix):] if path.startswith(prefix) else path


def normalize(i):
    kind = (i.get("type") or "").split("(")[0].strip()
    disposition = i.get("disposition") or ""
    url = i.get("url") or ""
    bundle = urllib.parse.unquote(url[len("file://"):]).rstrip("/") if url.startswith("file://") else ""
    path = home_path(i.get("executable_path") or "") or home_path(bundle)
    if path and not path.startswith("/"):
        # Relative executables live inside the item's bundle.
        path = os.path.join(home_path(bundle), path) if bundle.startswith("/") else ""
    last = None
    if i.get("last_use"):
        try:
            last = dt.datetime.fromisoformat(i["last_use"].replace(" ", "T", 1)).timestamp()
        except ValueError:
            pass
    return {"name": i.get("name") or i.get("identifier"), "developer": i.get("developer_name") or "",
            "type": TYPES.get(kind, kind or "item"), "enabled": "enabled" in disposition and "disabled" not in disposition,
            "allowed": "disallowed" not in disposition, "identifier": i.get("identifier") or "",
            "path": path, "last_use": last, "uid": i.get("uid"), "parent": i.get("parent_identifier") or ""}


LAUNCH_DIRS = [("~/Library/LaunchAgents", "launch agent", "me"),
               ("/Library/LaunchAgents", "launch agent", 0),
               ("/Library/LaunchDaemons", "launch daemon", 0)]
FULL_NOTE = ("Apps that open at login aren't listed: `cos startup --full` reads macOS's full list, "
             "and macOS asks for an admin password to show it.")


def parse_plist(path, kind, uid):
    try:
        with open(path, "rb") as f:
            d = plistlib.load(f)
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    label = str(d.get("Label") or os.path.basename(path)[:-len(".plist")])
    args = d.get("ProgramArguments") or [None]
    prog = d.get("Program") or (args[0] if isinstance(args, list) and args else None) or ""
    return {"name": label, "developer": "", "type": kind, "enabled": not d.get("Disabled", False),
            "allowed": True, "identifier": label, "path": prog if str(prog).startswith("/") else "",
            "last_use": None, "uid": uid, "parent": ""}


def parse_overrides(text):
    """`launchctl print-disabled` lines: "label" => enabled|disabled (or true/false)."""
    out = {}
    for m in re.finditer(r'"([^"]+)"\s*=>\s*(\w+)', text):
        out[m.group(1)] = m.group(2) in ("enabled", "false")
    return out


def launchd_items(dirs=None):
    me = os.getuid()
    overrides = {}
    for domain in ("gui/%d" % me, "system"):
        overrides.update(parse_overrides(core.run(["launchctl", "print-disabled", domain], timeout=10).out))
    items = []
    for folder, kind, uid in dirs or LAUNCH_DIRS:
        folder = os.path.expanduser(folder)
        try:
            names = sorted(n for n in os.listdir(folder) if n.endswith(".plist"))
        except OSError:
            continue
        for n in names:
            item = parse_plist(os.path.join(folder, n), kind, me if uid == "me" else uid)
            if item:
                if item["identifier"] in overrides:
                    item["enabled"] = overrides[item["identifier"]]
                items.append(item)
    return items


def signer(path):
    """Who signed the executable: Apple, a named developer, ad hoc, or nobody."""
    if not path or not os.path.exists(path):
        return {"signed": None, "authority": None}
    try:
        with open(path, "rb") as f:
            if f.read(2) == b"#!":
                return {"signed": False, "authority": "script"}  # scripts are never signed
    except OSError:
        pass
    r = core.run(["codesign", "-dvv", path], timeout=10)
    text = r.err + r.out
    if "not signed" in text:
        return {"signed": False, "authority": "unsigned"}
    if "Signature=adhoc" in text:
        return {"signed": True, "authority": "ad hoc"}
    auth = re.search(r"Authority=(.+)", text)
    a = auth.group(1).strip() if auth else "unknown"
    if a == "Software Signing" or a.startswith("Apple Mac OS Application Signing"):
        a = "Apple"
    return {"signed": True, "authority": re.sub(r"\s*\([A-Z0-9]{10}\)$", "", a)}


def findings(item, now=None):
    now = now or dt.datetime.now().timestamp()
    out = []
    if item["path"] and not os.path.exists(item["path"]):
        out.append("its program is missing (left behind by something you removed?)")
    if item.get("authority") in ("unsigned", "ad hoc", "script") and item["enabled"]:
        out.append({"unsigned": "runs unsigned code", "ad hoc": "runs ad-hoc signed code",
                    "script": "runs a script (scripts aren't signed; fine if you know it)"}[item["authority"]])
    if item["enabled"] and item["last_use"] and now - item["last_use"] > STALE_DAYS * 86400:
        out.append("on, but hasn't run in %d days" % ((now - item["last_use"]) // 86400))
    if not item["allowed"]:
        out.append("blocked in System Settings")
    return out


def audit(full=False):
    note = None
    if full:
        r = core.run(["sfltool", "dumpbtm"], timeout=60)
        if not r.ok and not r.out:
            return {"error": "couldn't read the login items list (did macOS's password dialog get "
                             "cancelled?): %s" % (r.err or "sfltool timed out")[:200], "items": []}
        me = os.getuid()
        items = [i for i in parse_btm(r.out) if i["uid"] in (me, 0, -2) and i["type"] != "developer group"]
    else:
        items = launchd_items()
        note = FULL_NOTE
    seen, unique = set(), []
    for i in items:
        key = (i["identifier"], i["path"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    with ThreadPoolExecutor(8) as pool:
        for i, sig in zip(unique, pool.map(lambda i: signer(i["path"]), unique)):
            i.update(sig)
            i["findings"] = findings(i)
    unique.sort(key=lambda i: (not i["findings"], not i["enabled"], i["type"], (i["name"] or "").lower()))
    return {"items": unique, "enabled": sum(1 for i in unique if i["enabled"]),
            "flagged": sum(1 for i in unique if i["findings"]), "full": full, "note": note}


NAME_WIDTH = 46


def fit(name, width):
    """A name that fits the column, cut with an ellipsis rather than silently."""
    return name if len(name) <= width else name[:width - 1] + "…"


def render(data):
    if data.get("error"):
        print(data["error"])
        return
    print("%d things start with this Mac (%d on), %d worth a look\n" % (len(data["items"]), data["enabled"], data["flagged"]))
    width = min(max([len(i["name"] or "?") for i in data["items"]] + [10]), NAME_WIDTH)
    for i in data["items"]:
        mark = "⚠" if i["findings"] else ("●" if i["enabled"] else "○")
        who = i.get("authority") or i["developer"] or "?"
        print("%s %-*s %-14s %s" % (mark, width, fit(i["name"] or "?", width), i["type"], who))
        for f in i["findings"]:
            print("    %s" % f)
    print("\n● on  ○ off  ⚠ worth a look · change these in System Settings › General › Login Items & Extensions")
    if data.get("note"):
        print(data["note"])


def main(args):
    core.emit(audit(full=args.full), args.json, render)
    return 0
