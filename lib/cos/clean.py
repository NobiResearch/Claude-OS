"""cos clean — find reclaimable disk space, and reclaim it only when asked.

Scanning is read-only and free. Applying requires naming targets explicitly
and passing --yes. Every apply is journaled with the bytes it freed.

Safety levels:
  safe     tool-managed caches and build products; regenerated automatically
  review   probably fine, but a human should glance at the details first
  careful  user data or slow to recover; list-only or explicit opt-in
"""

import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import core

HOME = Path.home()
STALE_DAYS = 90
SAFETY_ORDER = {"safe": 0, "review": 1, "careful": 2}


class Target:
    def __init__(self, id, label, why, safety, paths=(), action="contents",
                 cmd=None, requires=None, deep=False, measure=None, apply=None, busy=()):
        self.id, self.label, self.why, self.safety = id, label, why, safety
        self.paths = [Path(os.path.expanduser(p)) for p in paths]
        self.action, self.cmd, self.requires = action, cmd, requires
        self.deep, self.measure_fn, self.apply_fn = deep, measure, apply
        self.busy = busy  # processes that hold this cache while they run

    def available(self):
        if self.requires and not core.which(self.requires):
            return False
        if self.measure_fn:
            return True
        return any(p.exists() for p in self.paths)


# ---------------------------------------------------------------- measuring

def du(path):
    """Size of a path in bytes using du (handles hardlinks, skips unreadable)."""
    r = core.run(["du", "-sk", str(path)], timeout=180)
    first = (r.out.splitlines() or ["0"])[0].split("\t")[0]
    return int(first) * 1024 if first.isdigit() else 0


def measure_paths(t):
    total, details = 0, []
    for p in t.paths:
        if p.exists():
            size = du(p)
            total += size
            details.append({"path": tilde(p), "bytes": size})
    return total, details


def tilde(p):
    s = str(p)
    h = str(HOME)
    return "~" + s[len(h):] if s.startswith(h) else s


CACHE_OWNED_ELSEWHERE = {"Homebrew", "pip", "Yarn"}
# Not caches at all, whatever the folder says: Poetry keeps its virtualenvs here, and
# JetBrains IDEs keep their Local History.
NOT_REALLY_CACHES = {"pypoetry", "JetBrains"}
# Apple services that keep caches here without the com.apple. prefix. Leave them alone.
APPLE_CACHES = {"CloudKit", "GeoServices", "FamilyCircle", "PassKit", "GameKit", "SiriEntityCache",
                "askpermissiond", "familycircled", "SiriTTS", "Maps", "storeassetd", "storedownloadd",
                "ColorSync", "Metal", "AMSDataMigratorTool", "assistantd", "akd", "icloudmailagent"}
MIN_CACHE_BYTES = 50 * 1024 ** 2  # below this, not worth anyone's attention


def caches_children():
    root = HOME / "Library/Caches"
    if not root.exists():
        return []
    kids = []
    for child in root.iterdir():
        if (child.name in CACHE_OWNED_ELSEWHERE or child.name in APPLE_CACHES or child.name in NOT_REALLY_CACHES
                or child.name.startswith("com.apple.") or child.is_symlink()):
            continue
        kids.append(child)
    return kids


def user_cache_entries():
    """(path, bytes) for every cache worth deleting. Measure and apply use the same list,
    so what the human reviewed is exactly what gets deleted."""
    kids = caches_children()
    with ThreadPoolExecutor(8) as pool:
        sizes = list(pool.map(du, kids))
    entries = [(k, n) for k, n in zip(kids, sizes) if n >= MIN_CACHE_BYTES]
    entries.sort(key=lambda e: -e[1])
    return entries


def measure_user_caches(t):
    entries = user_cache_entries()
    return sum(n for _, n in entries), [{"path": tilde(k), "bytes": n} for k, n in entries]


def running_apps():
    """Bundle ids and names of the apps running now (lsappinfo, read-only), lowercased."""
    out = core.run(["lsappinfo", "list"], timeout=10).out
    return {m.lower() for m in re.findall(r'bundleID="([^"]+)"', out) + re.findall(r'^\s*\d+\) "([^"]+)"', out, re.M)}


def apply_user_caches(t):
    reviewed = _reviewed(t.id)
    if reviewed is None:
        return 0
    busy = running_apps()
    for path, _ in user_cache_entries():
        if tilde(path) not in reviewed:
            continue
        if path.name.lower() in busy:
            print("  %-22s kept %s: the app is running" % (t.id, tilde(path)))
            continue
        try:
            remove(path)
        except (OSError, ValueError) as e:
            print("  %-22s kept %s: %s" % (t.id, tilde(path), e))


def simulators():
    r = core.run(["xcrun", "simctl", "list", "devices", "-j"], timeout=60)
    if not r.ok:
        return []
    try:
        devices = json.loads(r.out)["devices"]
    except (ValueError, KeyError):
        return []
    newest = {}
    flat = []
    for runtime, devs in devices.items():
        m = re.search(r"SimRuntime\.(\w+?)-(\d+)-(\d+)", runtime)
        platform, version = (m.group(1), (int(m.group(2)), int(m.group(3)))) if m else ("?", (0, 0))
        for d in devs:
            d = dict(d, platform=platform, version=version)
            flat.append(d)
            if d.get("isAvailable", True):  # a deleted runtime's leftovers don't count as "newest"
                newest[platform] = max(newest.get(platform, (0, 0)), version)
    for d in flat:
        d["old_runtime"] = d["version"] < newest.get(d["platform"], (0, 0))
    return flat


def stale_simulators():
    # CoreSimulator touches every device folder, so mtimes say nothing about use;
    # "older runtime than the newest installed" is the honest signal.
    return [d for d in simulators()
            if d.get("isAvailable", True) and d["state"] != "Booted" and d["old_runtime"]]


def measure_stale_sims(t):
    details = [{"udid": d["udid"], "name": d["name"],
                "runtime": "%s %d.%d" % ((d["platform"],) + d["version"]),
                "bytes": d.get("dataPathSize", 0)}
               for d in stale_simulators()]
    details.sort(key=lambda d: -d["bytes"])
    return sum(d["bytes"] for d in details), details


def apply_stale_sims(t):
    """-> bytes freed: what simctl was asked to delete, if it said it did."""
    sims = stale_simulators()
    if not sims:
        return 0
    r = core.run(["xcrun", "simctl", "delete"] + [d["udid"] for d in sims], timeout=300)
    return sum(d.get("dataPathSize", 0) for d in sims) if r.ok else 0


def measure_unavailable_sims(t):
    devs = [d for d in simulators() if not d.get("isAvailable", True)]
    details = [{"udid": d["udid"], "name": d["name"], "bytes": d.get("dataPathSize", 0)} for d in devs]
    return sum(d["bytes"] for d in details), details


def _version(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:3])


def pick_old_runtimes(data):
    """Runtimes older than the newest of their platform. The newest always stays."""
    newest = {}
    for rt in data.values():
        plat = rt.get("platformIdentifier")
        newest[plat] = max(newest.get(plat, ()), _version(rt.get("version")))
    old = [dict(rt, id=rid) for rid, rt in data.items()
           if rt.get("deletable") and _version(rt.get("version")) < newest[rt.get("platformIdentifier")]]
    return sorted(old, key=lambda rt: -(rt.get("sizeBytes") or 0))


def old_runtimes():
    # Right after simulators are deleted, CoreSimulator can answer with nothing for a moment.
    for attempt in range(2):
        r = core.run(["xcrun", "simctl", "runtime", "list", "-j"], timeout=60)
        try:
            data = json.loads(r.out or "")
            if r.ok and isinstance(data, dict):
                return pick_old_runtimes(data)
        except (ValueError, AttributeError):
            pass
        time.sleep(3)
    return []


def measure_old_runtimes(t):
    plat = lambda p: {"com.apple.platform.iphonesimulator": "iOS", "com.apple.platform.appletvsimulator": "tvOS",
                      "com.apple.platform.watchsimulator": "watchOS", "com.apple.platform.xrsimulator": "visionOS"}.get(p, p)
    details = [{"name": "%s %s (%s)" % (plat(rt.get("platformIdentifier")), rt.get("version"), rt.get("build")),
                "bytes": rt.get("sizeBytes") or 0, "last_used": (rt.get("lastUsedAt") or "")[:10]}
               for rt in old_runtimes()]
    return sum(d["bytes"] for d in details), details


def apply_old_runtimes(t):
    """-> bytes freed: the size of each runtime simctl deleted."""
    freed = 0
    for rt in old_runtimes():
        r = core.run(["xcrun", "simctl", "runtime", "delete", rt["id"]], timeout=600)
        if r.ok:
            freed += rt.get("sizeBytes") or 0
        else:
            print("  couldn't delete %s %s: %s" % (rt.get("platformIdentifier"), rt.get("version"), (r.err or r.out)[:200]))
    return freed


def measure_brew(t):
    r = core.run(["brew", "cleanup", "-n", "--prune=all"], timeout=120,
                 env={"HOMEBREW_NO_AUTO_UPDATE": "1"})
    m = re.search(r"free approximately ([\d.]+)\s*([KMGT]?B)", r.out)
    if not m:
        return 0, []
    mult = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}[m.group(2)]
    return int(float(m.group(1)) * mult), []


def measure_docker(t):
    r = core.run(["docker", "system", "df", "--format", "{{json .}}"], timeout=30)
    total, details = 0, []
    units = {"B": 1, "kB": 1000, "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4}
    for line in r.out.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        m = re.match(r"([\d.]+)\s*([kKMGT]?B)", row.get("Reclaimable", ""))
        if m:
            size = int(float(m.group(1)) * units[m.group(2)])
            total += size
            details.append({"type": row.get("Type"), "bytes": size})
    return total, details


def old_downloads():
    root = HOME / "Downloads"
    if root.is_symlink() or not root.exists():
        return []  # a Downloads that links elsewhere (into Documents, say) isn't downloads
    cutoff = time.time() - STALE_DAYS * 86400
    out = []
    try:
        for child in root.iterdir():
            if child.name.startswith(".") or child.is_symlink():
                continue  # Finder would trash a symlink's target, not the link
            try:
                st = child.lstat()
            except OSError:
                continue
            if max(st.st_mtime, st.st_atime) >= cutoff:
                continue
            # A folder's own dates don't change when a file inside it is edited.
            if child.is_dir() and recently_touched(child):
                continue
            out.append(child)
    except PermissionError:
        return []
    return out


def measure_downloads(t):
    items = [{"path": tilde(p), "bytes": du(p)} for p in old_downloads()]
    items.sort(key=lambda d: -d["bytes"])
    return sum(d["bytes"] for d in items), items[:REVIEW_MAX]


def apply_downloads(t):
    reviewed = _reviewed(t.id)
    if reviewed is not None:
        trash([p for p in old_downloads() if tilde(p) in reviewed])


def measure_trash(t):
    r = core.osascript('tell application "Finder" to count items of trash', timeout=10)
    count = int(r.out) if r.out.isdigit() else None
    size = du(HOME / ".Trash")
    return size, [{"items": count, "note": "size needs Full Disk Access" if not size and count else ""}]


def apply_trash(t):
    core.osascript('tell application "Finder" to empty trash', timeout=300)


LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")
REVIEW_MAX = 500  # every item the human could review is in the scan; the desktop shows the first 40


def _reviewed(target_id, max_age=24 * 3600):
    """The paths the last scan listed for a target, which is what the human reviewed: apply
    acts only on those (and only if they still qualify). None, with a note, without a scan."""
    scan = core.cache_get("clean", max_age=max_age)
    for r in ((scan or {}).get("data") or {}).get("targets", []):
        if r["id"] == target_id:
            return {d["path"] for d in r.get("details", []) if "path" in d}
    print("  %-22s skipped: scan first (`cos clean`), so what's removed is what you reviewed" % target_id)
    return None


DEV_ROOTS = ["~/Developer", "~/Projects", "~/projects", "~/code", "~/src", "~/dev", "~/Code"]


def dev_roots():
    """Existing dev folders, deduplicated by inode (APFS is case-insensitive: ~/code is ~/Code)."""
    seen, roots = set(), []
    for r in DEV_ROOTS:
        p = Path(os.path.expanduser(r))
        try:
            st = p.stat()
        except OSError:
            continue
        if p.is_dir() and (st.st_dev, st.st_ino) not in seen:
            seen.add((st.st_dev, st.st_ino))
            roots.append(p)
    return roots


def recently_touched(project, days=STALE_DAYS):
    """Any file in the project (outside node_modules/.git) modified in the last `days`?
    If find fails, assume yes: unknown means keep."""
    r = core.run(["find", str(project), "(", "-name", "node_modules", "-o", "-name", ".git", ")", "-prune",
                  "-o", "-type", "f", "-mtime", "-%d" % days, "-print", "-quit"], timeout=120)
    return r.rc != 0 or bool(r.out)


def stale_node_modules():
    found = []
    for root in dev_roots():
        r = core.run(["find", str(root), "-maxdepth", "5", "-type", "d", "-name", "node_modules",
                      "-prune", "-print0"], timeout=120)
        for raw in r.out.split("\0"):
            nm = Path(raw)
            if not raw or nm.name != "node_modules" or nm.is_symlink() or "node_modules" in nm.parent.parts:
                continue
            # Only what `npm install` (or yarn, pnpm, bun) can put back exactly.
            if not (nm.parent / "package.json").is_file() or not any((nm.parent / l).exists() for l in LOCKFILES):
                continue
            if not recently_touched(nm.parent):
                found.append(nm)
    return found


def measure_node_modules(t):
    mods = stale_node_modules()
    with ThreadPoolExecutor(8) as pool:
        items = [{"path": tilde(nm), "bytes": size} for nm, size in zip(mods, pool.map(du, mods))]
    items.sort(key=lambda d: -d["bytes"])
    return sum(d["bytes"] for d in items), items[:REVIEW_MAX]


def apply_node_modules(t):
    reviewed = _reviewed(t.id)
    if reviewed is None:
        return 0
    for nm in stale_node_modules():
        if tilde(nm) not in reviewed:
            continue
        try:
            remove(nm)
        except (OSError, ValueError) as e:
            print("  %-22s kept %s: %s" % (t.id, tilde(nm), e))


def measure_large_files(t):
    r = core.run(["mdfind", "-onlyin", str(HOME), "kMDItemFSSize > 2000000000"], timeout=60)
    items = []
    for line in r.out.splitlines():
        if "/Library/" in line or "/." in line:
            continue
        try:
            items.append({"path": tilde(line), "bytes": os.path.getsize(line)})
        except OSError:
            continue
    items.sort(key=lambda d: -d["bytes"])
    return sum(d["bytes"] for d in items), items[:20]


def measure_hf(t):
    hub = HOME / ".cache/huggingface/hub"
    items = []
    if hub.is_dir():
        for child in hub.iterdir():
            if child.name.startswith(("models--", "datasets--")):
                items.append({"path": tilde(child), "bytes": du(child)})
    items.sort(key=lambda d: -d["bytes"])
    total = du(HOME / ".cache/huggingface")
    return total, items[:10]


TARGETS = [
    Target("xcode-derived-data", "Xcode DerivedData",
           "Build intermediates and indexes. Xcode rebuilds them on the next build.",
           "safe", ["~/Library/Developer/Xcode/DerivedData"]),
    Target("xcode-device-support", "Device support symbols",
           "Debug symbols copied per device OS version. Re-copied when a device connects.",
           "safe", ["~/Library/Developer/Xcode/iOS DeviceSupport", "~/Library/Developer/Xcode/watchOS DeviceSupport",
                    "~/Library/Developer/Xcode/tvOS DeviceSupport", "~/Library/Developer/Xcode/visionOS DeviceSupport"]),
    Target("simulators-unavailable", "Unavailable simulators",
           "Simulators whose runtime is gone. Unusable; Xcode's own cleanup removes them.",
           "safe", action="cmd", cmd=["xcrun", "simctl", "delete", "unavailable"], requires="xcrun",
           measure=measure_unavailable_sims),
    Target("simulators-stale", "Stale simulators",
           "Simulators on an older runtime than the newest installed. Deleting loses their app data; keep any you test against.",
           "review", requires="xcrun", measure=measure_stale_sims, apply=apply_stale_sims),
    Target("simulator-runtimes-old", "Old simulator runtimes",
           "Simulator OS images older than the newest one per platform. Their simulators stop working; re-download from Xcode if you still test on them.",
           "review", requires="xcrun", measure=measure_old_runtimes, apply=apply_old_runtimes),
    Target("simulator-caches", "Simulator caches", "Dyld and runtime caches; regenerated on boot.",
           "safe", ["~/Library/Developer/CoreSimulator/Caches"]),
    Target("xcode-archives", "Xcode archives",
           "Builds you archived for distribution. Needed to symbolicate crash reports of shipped versions.",
           "careful", ["~/Library/Developer/Xcode/Archives"], action="list"),
    Target("user-caches", "App caches (~/Library/Caches)",
           "Per-app caches over 50 MB (all listed in details). Apps rebuild them; quit big apps first. Apple's own caches are skipped.",
           "review", measure=measure_user_caches, apply=apply_user_caches),
    Target("homebrew", "Homebrew downloads & old versions", "Old formula versions and cached downloads.",
           "safe", action="cmd", cmd=["brew", "cleanup", "--prune=all"], requires="brew", measure=measure_brew),
    Target("npm-cache", "npm cache", "Package tarball cache. npm refetches on demand.",
           "safe", ["~/.npm/_cacache"], action="cmd", cmd=["npm", "cache", "clean", "--force"], requires="npm"),
    Target("pnpm-store", "pnpm store (unreferenced)", "Only packages no project references are pruned; size shown is the upper bound.",
           "safe", ["~/Library/pnpm/store"], action="cmd", cmd=["pnpm", "store", "prune"], requires="pnpm"),
    Target("yarn-cache", "Yarn cache", "Package cache; refetched on demand.",
           "safe", ["~/Library/Caches/Yarn"], action="cmd", cmd=["yarn", "cache", "clean"], requires="yarn"),
    Target("pip-cache", "pip cache", "Wheel and HTTP cache.", "safe", ["~/Library/Caches/pip"]),
    Target("uv-cache", "uv cache", "Python package cache; refetched on demand.",
           "safe", ["~/.cache/uv"], action="cmd", cmd=["uv", "--no-config", "cache", "clean"], requires="uv",
           busy=("uv",)),  # uvx tools (MCP servers, say) lock the cache; `uv cache clean` would wait
    Target("cargo-cache", "Cargo registry cache", "Downloaded crate archives and sources.",
           "safe", ["~/.cargo/registry/cache", "~/.cargo/registry/src"]),
    Target("gradle-cache", "Gradle caches", "Dependency and build caches.", "safe", ["~/.gradle/caches"]),
    Target("go-modcache", "Go module cache", "Downloaded modules.", "safe", ["~/go/pkg/mod"],
           action="cmd", cmd=["go", "clean", "-modcache"], requires="go"),
    Target("docker", "Docker reclaimable", "Unused images, containers and build cache.",
           "review", action="cmd", cmd=["docker", "system", "prune", "-f"], requires="docker", measure=measure_docker),
    Target("huggingface", "Hugging Face models", "Downloaded ML models and datasets. Slow to re-download.",
           "careful", ["~/.cache/huggingface"], action="list", measure=measure_hf),
    Target("logs", "User logs", "Diagnostic logs from apps.", "safe", ["~/Library/Logs"]),
    Target("downloads-old", "Old downloads",
           "Items in ~/Downloads untouched for %d+ days. Moved to Trash, not deleted." % STALE_DAYS,
           "review", measure=measure_downloads, apply=apply_downloads),
    Target("trash", "Trash", "Already-deleted files. Emptying is permanent.",
           "careful", measure=measure_trash, apply=apply_trash),
    Target("ios-backups", "iPhone/iPad backups", "Local device backups. Delete via Finder > device > Manage Backups.",
           "careful", ["~/Library/Application Support/MobileSync/Backup"], action="list"),
    Target("node-modules-stale", "Stale node_modules",
           "node_modules in projects untouched for %d+ days. `npm install` restores them." % STALE_DAYS,
           "review", deep=True, measure=measure_node_modules, apply=apply_node_modules),
    Target("large-files", "Large files (>2 GB)", "Spotlight-found big files outside ~/Library. Review by hand.",
           "careful", deep=True, action="list", measure=measure_large_files),
]

BY_ID = {t.id: t for t in TARGETS}


# ---------------------------------------------------------------- removing

PROTECTED = {
    "Library/Caches", "Library/Application Support", "Library/Developer", "Library/Preferences",
    "Library/Containers", "Library/Group Containers", "Library/Mobile Documents", "Library/Logs",
    "Library/Developer/Xcode", "Library/Developer/CoreSimulator",
}


def _guard(path):
    """Only ever remove things at least two levels inside the home folder, never a protected
    root, and never through a symlink: if any folder between the home folder and the path is
    a link (a cache folder pointing into Documents, say), deleting would follow it."""
    p = Path(os.path.abspath(os.path.expanduser(str(path))))
    for home in (Path.home(), Path(os.path.realpath(str(Path.home())))):  # a resolved path, too
        try:
            rel = p.relative_to(home)
            break
        except ValueError:
            continue
    else:
        raise ValueError("refusing to touch %s: outside the home folder" % p)
    if len(rel.parts) < 2 or rel.as_posix() in PROTECTED:
        raise ValueError("refusing to remove %s: protected folder" % p)
    cur = home
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            raise ValueError("refusing to remove %s: %s is a symlink" % (p, tilde(cur)))
    try:
        Path(os.path.realpath(str(p.parent))).relative_to(os.path.realpath(str(home)))
    except ValueError:
        raise ValueError("refusing to touch %s: it's really outside the home folder" % p)
    return p


def remove(path):
    p = _guard(path)
    if p.is_symlink() or p.is_file():
        p.unlink()
    elif p.is_dir():
        shutil.rmtree(p, ignore_errors=True)


def delete_contents(directory):
    d = Path(directory)
    if d.is_symlink():
        print("  kept %s: it's a symlink, and emptying it would empty what it points to" % tilde(d))
        return
    if not d.is_dir():
        return
    for child in d.iterdir():
        try:
            remove(child)
        except (OSError, ValueError):
            pass


def trash(paths):
    """Move to Trash via Finder: reversible, unlike rm. Never symlinks: Finder resolves
    them and would trash the target."""
    for p in paths:
        if os.path.islink(str(p)):
            continue
        try:
            _guard(p)
            _guard(os.path.realpath(str(p)))
        except ValueError as e:  # one odd item (Downloads on another disk, say) never stops the rest
            print("  kept %s: %s" % (tilde(p), e))
            continue
        core.osascript('tell application "Finder" to delete (POSIX file %s as alias)'
                       % core.applescript_str(str(p)), timeout=60)


# ---------------------------------------------------------------- scan / apply

def measure(t):
    started = time.time()
    try:
        size, details = (t.measure_fn or measure_paths)(t)
    except Exception as e:  # a broken probe must not sink the whole scan
        size, details = 0, [{"error": str(e)}]
    return {"id": t.id, "label": t.label, "why": t.why, "safety": t.safety, "bytes": size,
            "action": t.action if not t.apply_fn else "custom", "details": details,
            "seconds": round(time.time() - started, 1)}


def scan(deep=False):
    started = time.time()
    targets = [t for t in TARGETS if (deep or not t.deep) and t.available()]
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(measure, targets))
    results = [r for r in results if r["bytes"] > 0]
    results.sort(key=lambda r: (-r["bytes"]))
    totals = {}
    for r in results:
        totals[r["safety"]] = totals.get(r["safety"], 0) + r["bytes"]
    data = {"targets": results, "totals": totals, "safe_bytes": totals.get("safe", 0),
            "deep": deep, "seconds": round(time.time() - started, 1)}
    core.cache_put("clean", data)
    return data


def render_scan(data):
    print("Reclaimable space (%s scan, %.0fs)\n" % ("deep" if data["deep"] else "quick", data["seconds"]))
    print("  %-9s  %-7s  %-22s  %s" % ("SIZE", "SAFETY", "ID", "WHAT"))
    for r in data["targets"]:
        print("  %-9s  %-7s  %-22s  %s" % (core.human_bytes(r["bytes"]), r["safety"], r["id"], r["label"]))
    t = data["totals"]
    print("\n  safe %s · review %s · careful %s" % tuple(core.human_bytes(t.get(k, 0)) for k in ("safe", "review", "careful")))
    print("  details: cos clean --json · reclaim: cos clean apply <id>... --yes")


def apply(ids, yes=False):
    unknown = [i for i in ids if i not in BY_ID]
    if unknown:
        core.die("unknown target(s): %s (see `cos clean`)" % ", ".join(unknown))
    if "trash" in ids and "downloads-old" in ids:
        core.die("run `cos clean apply trash --yes` on its own, later: emptying the Trash now would delete "
                 "the downloads this just moved there, for good")
    targets = [BY_ID[i] for i in ids]
    listonly = [t.id for t in targets if t.action == "list" and not t.apply_fn]
    if listonly:
        core.die("%s: list-only, clean these by hand after reviewing `cos clean --json`" % ", ".join(listonly))
    if not yes:
        print("Would reclaim (dry run; add --yes to do it):")
        for t in targets:
            how = " ".join(t.cmd) if t.action == "cmd" else ("custom" if t.apply_fn else "delete contents of " + ", ".join(tilde(p) for p in t.paths))
            print("  %-22s %-7s %s" % (t.id, t.safety, how))
        return 2
    results = []
    for t in targets:
        running = [name for name in t.busy if core.app_running(name)]
        if running:
            print("  %-22s skipped: %s is running and holds it (an MCP server started with uvx, say). "
                  "Quit it and run this again." % (t.id, " and ".join(running)))
            core.journal("action", "clean %s skipped: %s is running" % (t.id, ", ".join(running)), target=t.id, freed=0)
            continue
        before = measure(t)["bytes"]
        reported = 0
        if t.apply_fn:
            reported = t.apply_fn(t) or 0
        elif t.action == "cmd":
            # From the home folder: a project's own config (a uv.toml pointing the cache at a
            # project folder, a Yarn project's .yarn/cache) must never decide what's deleted.
            r = core.run(t.cmd, timeout=900, cwd=str(HOME))
            if not r.ok:
                print("  %s: command failed: %s" % (t.id, (r.err or r.out)[:200]))
        else:
            for p in t.paths:
                delete_contents(p)
        after = measure(t)["bytes"]
        # Measuring can come back empty while a tool is busy; what the apply deleted still counts.
        freed = max(0, before - after, reported if isinstance(reported, int) else 0)
        results.append((t.id, freed))
        core.journal("action", "clean %s freed %s" % (t.id, core.human_bytes(freed)), target=t.id, freed=freed)
        print("  %-22s freed %s" % (t.id, core.human_bytes(freed)))
    total = sum(f for _, f in results)
    print("\n  total freed: %s" % core.human_bytes(total))
    core.run(["rm", "-f", str(core.home("cache", "clean.json"))])
    return 0


def main(args):
    if args.clean_cmd == "apply":
        return apply(args.ids, yes=args.yes)
    data = scan(deep=args.deep)
    core.emit(data, args.json, render_scan)
    return 0
