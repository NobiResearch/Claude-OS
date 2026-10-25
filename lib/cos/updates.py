"""cos update — what's out of date on this Mac, and upgrading it when asked."""

import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import core

BREW_ENV = {"HOMEBREW_NO_AUTO_UPDATE": "1", "HOMEBREW_NO_ENV_HINTS": "1"}


def parse_softwareupdate(text):
    """Parse `softwareupdate -l` into [{label, title, version, size, restart, recommended}]."""
    items, current = [], None
    for line in text.splitlines():
        m = re.match(r"\s*\*\s+Label:\s+(.+)", line)
        if m:
            current = {"label": m.group(1).strip()}
            items.append(current)
            continue
        if current is not None and "Title:" in line:
            fields = dict((k.strip().lower(), v.strip()) for k, v in
                          (kv.split(":", 1) for kv in line.strip().rstrip(",").split(", ") if ":" in kv))
            current["title"] = fields.get("title")
            current["version"] = fields.get("version")
            current["size"] = fields.get("size")
            current["recommended"] = fields.get("recommended", "").upper() == "YES"
            current["restart"] = "restart" in fields.get("action", "").lower()
    return items


def check_macos():
    r = core.run(["softwareupdate", "-l"], timeout=120)
    text = r.out + "\n" + r.err
    return {"items": parse_softwareupdate(text), "error": None if ("Finding" in text or r.ok) else text[:200]}


def parse_brew_outdated(text):
    data = json.loads(text or "{}")
    items = []
    for f in data.get("formulae", []):
        items.append({"name": f["name"], "kind": "formula", "installed": (f.get("installed_versions") or ["?"])[-1],
                      "latest": f.get("current_version"), "pinned": f.get("pinned", False)})
    for c in data.get("casks", []):
        items.append({"name": c["name"], "kind": "cask", "installed": (c.get("installed_versions") or ["?"])[-1],
                      "latest": c.get("current_version"), "pinned": False})
    for it in items:
        _classify(it)
    return items


def _major(v):
    m = re.match(r"(\d+)", str(v or ""))
    return m.group(1) if m else v


def _version(v):
    """'3.6.5_1' -> ((3, 6, 5), 1): leading numbers (trailing zeros dropped, so 1.0 == 1.0.0)
    plus brew's revision; a cask's ',build' is dropped."""
    m = re.match(r"(\d+(?:\.\d+)*)(?:_(\d+))?", str(v or "").split(",")[0])
    if not m:
        return None
    parts = [int(p) for p in m.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts), int(m.group(2) or 0)


def _look(installed, latest):
    """Why an upgrade deserves a look first: 'scheme', 'downgrade', 'major', or None."""
    a, b = _version(installed), _version(latest)
    if a and b:
        if (a[0][0] >= 1000) != (b[0][0] >= 1000):
            return "scheme"  # a build number or year became a version (or back): not comparable
        if b < a:
            return "downgrade"
    return "major" if _major(installed) != _major(latest) else None


def _classify(it):
    it["look"] = _look(it["installed"], it["latest"])
    it["major"] = it["look"] == "major"
    return it


def check_brew(fetch=False):
    if not core.which("brew"):
        return None
    if fetch:
        core.run(["brew", "update", "--quiet"], timeout=300, env=BREW_ENV)
    r = core.run(["brew", "outdated", "--json=v2"], timeout=120, env=BREW_ENV)
    try:
        return {"items": parse_brew_outdated(r.out), "error": None}
    except ValueError:
        return {"items": [], "error": (r.err or r.out)[:200]}


# A fixed phrase, never the tool's own words: npm's errors name log files under the home folder.
UNCHECKED = "couldn't check"


def parse_npm_outdated(rc, out):
    """`npm outdated -g --json` -> items, or None if npm couldn't check. Exit 1 with packages
    is normal (something is outdated); an "error" object, or a failure with nothing listed, is
    npm not reaching its registry (offline, sandboxed), which isn't "up to date"."""
    try:
        data = json.loads(out or "{}")
    except ValueError:
        return None
    if not isinstance(data, dict) or "error" in data or (rc != 0 and not data):
        return None
    return [_classify({"name": name, "kind": "npm", "installed": v.get("current"), "latest": v.get("latest")})
            for name, v in data.items() if isinstance(v, dict)]


def check_npm():
    if not core.which("npm"):
        return None
    r = core.run(["npm", "outdated", "-g", "--json"], timeout=90)
    items = parse_npm_outdated(r.rc, r.out)
    return {"items": items or [], "error": None if items is not None else UNCHECKED}


def check_mas():
    if not core.which("mas"):
        return None
    r = core.run(["mas", "outdated"], timeout=60)
    items = []
    for line in r.out.splitlines():
        m = re.match(r"(\d+)\s+(.+?)\s+\((.+?)\s*->\s*(.+?)\)", line)
        if m:
            items.append({"name": m.group(2), "id": m.group(1), "kind": "app-store",
                          "installed": m.group(3), "latest": m.group(4)})
    return {"items": items, "error": UNCHECKED if not r.ok and not items else None}


def check_rustup():
    if not core.which("rustup"):
        return None
    r = core.run(["rustup", "check"], timeout=60)
    items = []
    for line in r.out.splitlines():
        if "Update available" in line:
            name = line.split(" - ")[0].strip()
            vers = re.findall(r"(\d+\.\d+\.\d+)", line)
            items.append({"name": name, "kind": "rustup", "installed": vers[0] if vers else "?",
                          "latest": vers[-1] if vers else "?"})
    # rustup check exits 100 when updates are available; only a failure with nothing parsed is unchecked
    return {"items": items, "error": UNCHECKED if r.rc not in (0, 100) and not items else None}


def check(fetch=False):
    jobs = {"macos": check_macos, "brew": lambda: check_brew(fetch), "npm": check_npm,
            "mas": check_mas, "rustup": check_rustup}
    with ThreadPoolExecutor(len(jobs)) as pool:
        futures = {k: pool.submit(fn) for k, fn in jobs.items()}
        sources = {k: f.result() for k, f in futures.items()}
    sources = {k: v for k, v in sources.items() if v is not None}
    total = sum(len(v["items"]) for v in sources.values())
    data = {"sources": sources, "total": total, "fetched": fetch,
            "missing_tools": [t for t in ("mas",) if not core.which(t)]}
    core.cache_put("updates", data)
    return data


MARKS = {"major": "▲", "downgrade": "▼", "scheme": "≠"}
NOTES = {"downgrade": " (downgrade)", "scheme": " (new version scheme)"}


def _look_of(it):
    return it.get("look") or ("major" if it.get("major") else None)  # caches from before `look` existed


def render(data):
    src = data["sources"]
    mac = src.get("macos", {}).get("items", [])
    if mac:
        print("macOS")
        for it in mac:
            print("  ⚠ %s %s%s" % (it.get("title") or it["label"], it.get("version") or "",
                                   " (restart)" if it.get("restart") else ""))
    else:
        print("macOS: up to date")
    for name, label in (("brew", "Homebrew"), ("npm", "npm (global)"), ("mas", "App Store"), ("rustup", "Rust")):
        s = src.get(name)
        if not s:
            continue
        items = s["items"]
        if not items:
            print("%s: %s" % (label, UNCHECKED if s.get("error") == UNCHECKED else "up to date"))
            continue
        looks = [i for i in items if _look_of(i)]
        print("%s: %d outdated%s" % (label, len(items), (", %d to look at first" % len(looks)) if looks else ""))
        for it in sorted(items, key=lambda i: (not _look_of(i), i["name"]))[:12]:
            look = _look_of(it)
            print("  %s %-24s %s → %s%s%s" % (MARKS.get(look, "·"), it["name"], it["installed"], it["latest"],
                                             NOTES.get(look, ""), " (pinned)" if it.get("pinned") else ""))
        if len(items) > 12:
            print("  … and %d more" % (len(items) - 12))
    if not data["fetched"] and src.get("brew"):
        print("\n(brew metadata not refreshed; `cos update --fetch` asks Homebrew for the latest)")
    if data["missing_tools"]:
        print("tip: `brew install mas` lets Claude OS see App Store updates too")
    print("\nupgrade with: cos update apply brew|npm|mas|rustup [names...] --yes · macOS: cos update apply macos")


def apply(source, names, yes=False):
    plans = {
        "brew": ["brew", "upgrade"] + names,
        "npm": (["npm", "install", "-g"] + ["%s@latest" % n for n in names]) if names else ["npm", "update", "-g"],
        "mas": ["mas", "upgrade"] + names,
        "rustup": ["rustup", "update"],
        "macos": ["open", "x-apple.systempreferences:com.apple.Software-Update-Settings.extension"],
    }
    if source not in plans:
        core.die("unknown source %r (choose: %s)" % (source, ", ".join(plans)))
    cmd = plans[source]
    if source == "macos":
        core.run(cmd)
        print("Opened Software Update in System Settings. macOS installs need your password and a restart,"
              " so the human presses the button.")
        return 0
    if not yes:
        print("Would run: %s\n(add --yes to do it)" % " ".join(cmd))
        return 2
    print("$ %s" % " ".join(cmd))
    r = core.run(cmd, timeout=3600, env=BREW_ENV if source == "brew" else None)
    tail = "\n".join((r.out + "\n" + r.err).strip().splitlines()[-15:])
    print(tail)
    core.journal("action", "update %s %s (rc=%d)" % (source, " ".join(names) or "all", r.rc),
                 source=source, names=names, rc=r.rc)
    core.run(["rm", "-f", str(core.home("cache", "updates.json"))])
    return 0 if r.ok else 1


def main(args):
    if args.update_cmd == "apply":
        return apply(args.source, args.names, yes=args.yes)
    data = check(fetch=args.fetch)
    core.emit(data, args.json, render)
    return 0
