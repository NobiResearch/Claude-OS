"""cos startup — what starts with this Mac, read-only (decision 0004).

Reads macOS's Background Task Management records (`sfltool dumpbtm`, the list behind
System Settings › General › Login Items & Extensions), checks each executable's code
signature, and puts the odd ones first: missing executables, unsigned or ad-hoc code,
things that are on but haven't run in months. It never changes anything; the human (or
Claude, with an Allow) does that in System Settings.
"""

import datetime as dt
import os
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


def signer(path):
    """Who signed the executable: Apple, a named developer, ad hoc, or nobody."""
    if not path or not os.path.exists(path):
        return {"signed": None, "authority": None}
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
    if item.get("authority") in ("unsigned", "ad hoc") and item["enabled"]:
        out.append("runs %s code" % ("unsigned" if item["authority"] == "unsigned" else "ad-hoc signed"))
    if item["enabled"] and item["last_use"] and now - item["last_use"] > STALE_DAYS * 86400:
        out.append("on, but hasn't run in %d days" % ((now - item["last_use"]) // 86400))
    if not item["allowed"]:
        out.append("blocked in System Settings")
    return out


def audit():
    r = core.run(["sfltool", "dumpbtm"], timeout=30)
    if not r.ok and not r.out:
        return {"error": "couldn't read the login items list: %s" % (r.err or "sfltool failed")[:200], "items": []}
    me = os.getuid()
    items = [i for i in parse_btm(r.out) if i["uid"] in (me, 0, -2) and i["type"] != "developer group"]
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
            "flagged": sum(1 for i in unique if i["findings"])}


def render(data):
    if data.get("error"):
        print(data["error"])
        return
    print("%d things start with this Mac (%d on), %d worth a look\n" % (len(data["items"]), data["enabled"], data["flagged"]))
    for i in data["items"]:
        mark = "⚠" if i["findings"] else ("●" if i["enabled"] else "○")
        who = i.get("authority") or i["developer"] or "?"
        print("%s %-34s %-14s %s" % (mark, (i["name"] or "?")[:34], i["type"], who))
        for f in i["findings"]:
            print("    %s" % f)
    print("\n● on  ○ off  ⚠ worth a look · change these in System Settings › General › Login Items & Extensions")


def main(args):
    core.emit(audit(), args.json, render)
    return 0
