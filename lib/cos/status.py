"""cos status — vitals of the Mac, plus signals worth acting on."""

import os
import plistlib
import re
import time

from . import core

DATA_VOLUME = "/System/Volumes/Data"


def _sysctl(name):
    r = core.run(["sysctl", "-n", name], timeout=3)
    return r.out if r.ok else ""


def disk():
    path = DATA_VOLUME if os.path.exists(DATA_VOLUME) else "/"
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    return {"total": total, "free": free, "free_pct": round(100.0 * free / total, 1) if total else 0}


def memory():
    total = int(_sysctl("hw.memsize") or 0)
    r = core.run(["vm_stat"], timeout=3)
    page = 16384
    m = re.search(r"page size of (\d+)", r.out)
    if m:
        page = int(m.group(1))
    pages = {}
    for line in r.out.splitlines()[1:]:
        k, _, v = line.partition(":")
        v = v.strip().rstrip(".")
        if v.isdigit():
            pages[k.strip()] = int(v)
    used = (pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
            + pages.get("Pages occupied by compressor", 0)) * page
    swap = 0
    sm = re.search(r"used = ([\d.]+)M", _sysctl("vm.swapusage"))
    if sm:
        swap = int(float(sm.group(1)) * 1024 * 1024)
    return {"total": total, "used": used, "swap_used": swap}


def battery():
    r = core.run(["pmset", "-g", "batt"], timeout=3)
    m = re.search(r"(\d+)%;\s*([^;]+);", r.out)
    if not m:
        return None
    info = {"percent": int(m.group(1)), "state": m.group(2).strip(),
            "source": "AC" if "AC Power" in r.out else "battery"}
    io = core.run(["ioreg", "-rn", "AppleSmartBattery"], timeout=3).out
    cyc = re.search(r'"CycleCount" = (\d+)', io)
    raw = re.search(r'"AppleRawMaxCapacity" = (\d+)', io)
    design = re.search(r'"DesignCapacity" = (\d+)', io)
    pct = re.search(r'"MaxCapacity" = (\d+)', io)
    if cyc:
        info["cycles"] = int(cyc.group(1))
    if raw and design and int(design.group(1)):
        info["health_pct"] = min(100, round(100.0 * int(raw.group(1)) / int(design.group(1))))
    elif pct and int(pct.group(1)) <= 100:
        info["health_pct"] = int(pct.group(1))  # Apple Silicon reports health directly
    return info


def uptime_seconds():
    m = re.search(r"sec = (\d+)", _sysctl("kern.boottime"))
    return int(time.time()) - int(m.group(1)) if m else None


def load():
    nums = re.findall(r"[\d.]+", _sysctl("vm.loadavg"))
    return [float(x) for x in nums[:3]]


def top_processes(n=5):
    r = core.run(["ps", "-Ao", "pid=,pcpu=,rss=,comm="], timeout=5)
    procs = []
    for line in r.out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            pid, cpu, rss, comm = parts
            procs.append({"pid": int(pid), "cpu": float(cpu), "rss": int(rss) * 1024,
                          "name": os.path.basename(comm)})
    by_cpu = sorted(procs, key=lambda p: -p["cpu"])[:n]
    by_mem = sorted(procs, key=lambda p: -p["rss"])[:n]
    return {"cpu": by_cpu, "memory": by_mem}


def security():
    fv = core.run(["fdesetup", "status"], timeout=5).out
    sip = core.run(["csrutil", "status"], timeout=5).out
    fw = core.run(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"], timeout=5).out
    gk = core.run(["spctl", "--status"], timeout=5)
    return {
        "filevault": "On" in fv if fv else None,
        "sip": "enabled" in sip if sip else None,
        "firewall": ("enabled" in fw or "State = 1" in fw) if fw else None,
        "gatekeeper": "enabled" in (gk.out + gk.err) if (gk.out or gk.err) else None,
    }


def parse_backup(text):
    """`tmutil destinationinfo -X` is a plist, an empty dict when Time Machine has no
    destination. Anything we can't read is unknown (None), and unknown is never a signal."""
    try:
        data = plistlib.loads(text.encode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not data:
        return {"configured": False}
    dests = data.get("Destinations")
    return {"configured": bool(dests)} if isinstance(dests, list) else None


def backup():
    """Is Time Machine set up? Never mounts or names the destination (decision 0005)."""
    r = core.run(["tmutil", "destinationinfo", "-X"], timeout=10)
    return parse_backup(r.out) if r.ok and r.out else None


def refresh_backup(max_age=24 * 3600):
    """Keep the `backup` cache that signals() reads; off with `cos config pulse.backup_check false`."""
    if core.config()["pulse"].get("backup_check", True) and not core.cache_get("backup", max_age=max_age):
        core.cache_put("backup", backup())


def system():
    v = core.run(["sw_vers"], timeout=3).out
    fields = dict(re.findall(r"(\w+):\s+(.+)", v))
    return {
        "macos": fields.get("ProductVersion"),
        "build": fields.get("BuildVersion"),
        "model": _sysctl("hw.model"),
        "chip": _sysctl("machdep.cpu.brand_string"),
        "cores": int(_sysctl("hw.ncpu") or 0),
    }


def signals(s):
    """Turn raw vitals into a short list of things worth a human's attention."""
    out = []
    d = s["disk"]
    pulse = core.config()["pulse"]
    low_gb = pulse["low_disk_gb"]
    if d["free"] < low_gb * 1024 ** 3 or d["free_pct"] < 10:
        out.append(("warn", "disk low: %s free" % core.human_bytes(d["free"])))
    elif d["free_pct"] < 20:
        out.append(("note", "disk getting full: %s%% free" % d["free_pct"]))
    m = s["memory"]
    if m["swap_used"] > 4 * 1024 ** 3:
        out.append(("note", "heavy swap: %s" % core.human_bytes(m["swap_used"])))
    b = s.get("battery")
    if b and b.get("health_pct") and b["health_pct"] < 80:
        out.append(("note", "battery health %d%%" % b["health_pct"]))
    sec = s["security"]
    if sec.get("filevault") is False:
        out.append(("warn", "FileVault is off"))
    if sec.get("firewall") is False:
        out.append(("note", "firewall is off"))
    up = s.get("uptime") or 0
    if up > 14 * 86400:
        out.append(("note", "up %d days; a restart helps updates land" % (up // 86400)))
    wx = core.cache_get("weather", max_age=3 * 3600)
    if wx and (wx["data"].get("alert") or {}).get("msg"):
        a = wx["data"]["alert"]
        out.append((a["level"], a["msg"][0].upper() + a["msg"][1:]))
    upd = core.cache_get("updates")
    if upd:
        n = upd["data"].get("total", 0)
        if n:
            out.append(("note", "%d updates available (checked %s)" % (n, core.ago(upd["ts"]))))
    scan = core.cache_get("clean")
    if scan:
        safe = scan["data"].get("safe_bytes", 0)
        if safe > 5 * 1024 ** 3:
            out.append(("note", "%s safely reclaimable (scanned %s)" % (
                core.human_bytes(safe), core.ago(scan["ts"]))))
    tm = core.cache_get("backup")
    if tm and pulse.get("backup_check", True) and (tm["data"] or {}).get("configured") is False:
        out.append(("note", "Time Machine isn't set up"))
    return out


def collect(include_slow=True):
    s = {
        "system": system(),
        "disk": disk(),
        "memory": memory(),
        "battery": battery(),
        "uptime": uptime_seconds(),
        "load": load(),
    }
    if include_slow:
        s["security"] = security()
        s["top"] = top_processes()
    else:
        s["security"] = {}
    s["signals"] = [{"level": lvl, "msg": msg} for lvl, msg in signals(s)]
    return s


TRENDS_FILE = "trends.jsonl"
TRENDS_KEEP = 730  # two years of daily lines


def record_trend(s, today=None):
    """Append one snapshot per day (idempotent), for trend lines once enough days exist."""
    import datetime as dt
    import json
    today = today or dt.date.today().isoformat()
    path = core.home(TRENDS_FILE)
    try:
        lines = path.read_text().splitlines()
    except OSError:
        lines = []
    if lines and json.loads(lines[-1]).get("date") == today:
        return False
    b = s.get("battery") or {}
    upd = core.cache_get("updates")
    scan = core.cache_get("clean")
    row = {"date": today, "disk_free": s["disk"]["free"], "battery_health": b.get("health_pct"),
           "battery_cycles": b.get("cycles"), "updates": upd["data"].get("total") if upd else None,
           "reclaimable": scan["data"].get("safe_bytes") if scan else None}
    lines = (lines + [json.dumps(row)])[-TRENDS_KEEP:]
    path.write_text("\n".join(lines) + "\n")
    return True


def trends():
    import json
    try:
        return [json.loads(l) for l in core.home(TRENDS_FILE).read_text().splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def disk_trend(rows, min_days=7):
    """Average change in free disk per week, once there's at least a week of data."""
    rows = [r for r in rows if r.get("disk_free") is not None]
    if len(rows) < min_days:
        return None
    import datetime as dt
    first, last = rows[0], rows[-1]
    days = (dt.date.fromisoformat(last["date"]) - dt.date.fromisoformat(first["date"])).days or 1
    return (last["disk_free"] - first["disk_free"]) / days * 7


def fmt_uptime(sec):
    if sec is None:
        return "?"
    d, rem = divmod(sec, 86400)
    h = rem // 3600
    return "%dd %dh" % (d, h) if d else "%dh %dm" % (h, (rem % 3600) // 60)


def render(s):
    sy, d, m, b = s["system"], s["disk"], s["memory"], s["battery"]
    print("◆ %s · macOS %s (%s) · %s, %d cores" % (sy["model"], sy["macos"], sy["build"], sy["chip"], sy["cores"]))
    print("  disk     %s free of %s (%s%%)" % (core.human_bytes(d["free"]), core.human_bytes(d["total"]), d["free_pct"]))
    print("  memory   %s used of %s · swap %s" % (core.human_bytes(m["used"]), core.human_bytes(m["total"]), core.human_bytes(m["swap_used"])))
    if b:
        extra = ""
        if "health_pct" in b:
            extra = " · health %d%%, %d cycles" % (b["health_pct"], b.get("cycles", 0))
        print("  battery  %d%% %s on %s%s" % (b["percent"], b["state"], b["source"], extra))
    print("  uptime   %s · load %s" % (fmt_uptime(s["uptime"]), " ".join("%.2f" % x for x in s["load"])))
    sec = s.get("security") or {}
    if sec:
        flag = lambda v: "on" if v else ("off" if v is False else "?")
        print("  security FileVault %s · SIP %s · firewall %s · Gatekeeper %s" % (
            flag(sec.get("filevault")), flag(sec.get("sip")), flag(sec.get("firewall")), flag(sec.get("gatekeeper"))))
    top = s.get("top")
    if top:
        print("  top cpu  " + ", ".join("%s %.0f%%" % (p["name"], p["cpu"]) for p in top["cpu"][:4]))
        print("  top mem  " + ", ".join("%s %s" % (p["name"], core.human_bytes(p["rss"])) for p in top["memory"][:4]))
    week = disk_trend(trends())
    if week is not None:
        print("  trend    free disk %s%s per week" % ("+" if week >= 0 else "−", core.human_bytes(abs(week))))
    if s["signals"]:
        print()
        for sig in s["signals"]:
            print("  %s %s" % ("⚠" if sig["level"] == "warn" else "·", sig["msg"]))
    else:
        print("\n  all quiet.")


def main(args):
    refresh_backup(max_age=0)  # asked for by the human, so fresh (tmutil answers in milliseconds)
    s = collect()
    core.cache_put("status", s)
    core.emit(s, args.json, render)
    return 0
