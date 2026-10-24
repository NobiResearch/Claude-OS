"""cos serve --demo — a fictional Mac for screenshots and trying the desktop safely.

Every API read is answered from the fixtures below; nothing touches the real machine,
Music, the network or ~/.claude-os. Writes do nothing. Chat is a scripted stub that
shows a tool call and an Allow/Deny card. All names here are invented.
"""

import threading
import time

from . import chat

GB = 1024 ** 3
NOW = time.time()

STATUS = {
    "system": {"macos": "27.0.1", "build": "26A500", "model": "Mac16,8", "chip": "Apple M4 Pro", "cores": 14},
    "disk": {"total": 994 * GB, "free": 412 * GB, "free_pct": 41.4},
    "memory": {"total": 48 * GB, "used": int(21.4 * GB), "swap_used": 0},
    "battery": {"percent": 81, "state": "charging", "source": "AC", "cycles": 212, "health_pct": 96},
    "uptime": 3 * 86400 + 7200,
    "load": [2.41, 2.18, 1.97],
    "security": {"filevault": True, "sip": True, "firewall": True, "gatekeeper": True},
    "top": {
        "cpu": [{"name": "Xcode", "cpu": 38.0, "rss": 3 * GB}, {"name": "Safari", "cpu": 12.0, "rss": GB},
                {"name": "claude", "cpu": 9.0, "rss": GB // 2}, {"name": "WindowServer", "cpu": 7.0, "rss": GB // 3}],
        "memory": [{"name": "Xcode", "cpu": 38.0, "rss": 3 * GB}, {"name": "Simulator", "cpu": 3.0, "rss": int(2.2 * GB)},
                   {"name": "Safari", "cpu": 12.0, "rss": GB}, {"name": "claude", "cpu": 9.0, "rss": GB // 2}],
    },
    "signals": [{"level": "note", "msg": "23 updates available (checked 2h ago)"},
                {"level": "note", "msg": "41.2 GB safely reclaimable (scanned 1h ago)"}],
}


def _t(id_, label, safety, size, why, details=(), action="contents"):
    return {"id": id_, "label": label, "safety": safety, "bytes": int(size * GB), "why": why,
            "action": action, "details": list(details), "seconds": 0.4}


CLEAN = {"deep": False, "seconds": 6.8, "safe_bytes": int(41.2 * GB),
         "totals": {"safe": int(41.2 * GB), "review": int(27.9 * GB), "careful": int(6.1 * GB)},
         "targets": [
             _t("xcode-derived-data", "Xcode DerivedData", "safe", 17.3, "Build intermediates and indexes. Xcode rebuilds them on the next build.",
                [{"path": "~/Library/Developer/Xcode/DerivedData", "bytes": int(17.3 * GB)}]),
             _t("simulator-runtimes-old", "Old simulator runtimes", "review", 16.9,
                "Simulator OS images older than the newest one per platform. Their simulators stop working; re-download from Xcode if you still test on them.",
                [{"name": "iOS 26.4 (23E254)", "bytes": int(8.5 * GB), "last_used": "2026-08-30"},
                 {"name": "iOS 26.2 (23C55)", "bytes": int(8.4 * GB), "last_used": "2026-06-11"}]),
             _t("xcode-device-support", "Device support symbols", "safe", 12.6, "Debug symbols copied per device OS version. Re-copied when a device connects."),
             _t("user-caches", "App caches (~/Library/Caches)", "review", 11.0, "Per-app caches over 50 MB (all listed in details). Apps rebuild them; quit big apps first.",
                [{"path": "~/Library/Caches/org.swift.swiftpm", "bytes": int(3.1 * GB)},
                 {"path": "~/Library/Caches/ms-playwright", "bytes": int(1.8 * GB)}]),
             _t("npm-cache", "npm cache", "safe", 6.4, "Package tarball cache. npm refetches on demand.", action="cmd"),
             _t("huggingface", "Hugging Face models", "careful", 6.1, "Downloaded ML models and datasets. Slow to re-download.", action="list"),
             _t("uv-cache", "uv cache", "safe", 3.2, "Python package cache; refetched on demand.", action="cmd"),
             _t("homebrew", "Homebrew downloads & old versions", "safe", 1.7, "Old formula versions and cached downloads.", action="cmd"),
         ]}

UPDATES = {"total": 23, "fetched": True, "missing_tools": [], "sources": {
    "macos": {"items": [], "error": None},
    "brew": {"error": None, "items": [
        {"name": "node", "kind": "formula", "installed": "24.9.0", "latest": "25.1.0", "major": True, "pinned": False},
        {"name": "python@3.14", "kind": "formula", "installed": "3.14.0", "latest": "3.14.1", "major": False, "pinned": False},
        {"name": "ffmpeg", "kind": "formula", "installed": "8.0", "latest": "8.0.1", "major": False, "pinned": False},
        {"name": "git", "kind": "formula", "installed": "2.51.0", "latest": "2.51.2", "major": False, "pinned": False},
        {"name": "ripgrep", "kind": "formula", "installed": "15.0.0", "latest": "15.1.0", "major": False, "pinned": False},
        {"name": "sqlite", "kind": "formula", "installed": "3.50.4", "latest": "3.51.0", "major": False, "pinned": False},
    ]},
    "npm": {"error": None, "items": [
        {"name": "typescript", "kind": "npm", "installed": "5.9.2", "latest": "6.0.1", "major": True},
        {"name": "prettier", "kind": "npm", "installed": "3.6.1", "latest": "3.6.2", "major": False}]},
}}

ARTWORK = "https://is1-ssl.mzstatic.com/image/thumb/Music125/v4/f7/63/80/f76380c0-49fc-7849-a2e4-2833657bdb1b/cover.jpg/600x600bb.jpg"
MUSIC_NOW = {"running": True, "state": "playing", "track": "Weightless", "artist": "Marconi Union", "album": "Weightless",
             "duration": 488.0, "position": 131.0, "volume": 60, "shuffle": False, "repeat": "off", "artwork": ARTWORK}
PLAYLISTS = [{"name": n, "tracks": c} for n, c in (("Morning Coffee", 42), ("Deep Work", 118), ("Late Nights", 37),
                                                    ("Road Trip", 64), ("Rainy Sundays", 29), ("Favourites", 210))]


def _feed(feed, cat, title, summary, hours):
    return {"feed": feed, "category": cat, "title": title, "summary": summary, "link": "https://example.com/",
            "ts": NOW - hours * 3600, "key": ("%s-%s" % (feed, hours)).replace(" ", "")[:16]}


FEEDS = {"categories": ["ideas", "mac", "science", "tech"], "fetched": NOW, "items": [
    _feed("Small Machines", "tech", "What a 1980s word processor teaches about software today",
          "Constraints made the old tools fast. A tour of the ideas worth stealing back.", 1),
    _feed("Orbital", "science", "The quiet comeback of the airship",
          "Cargo, not passengers: why helium is having a moment again.", 3),
    _feed("Field Notes", "ideas", "On keeping a notebook for twenty years",
          "Not a productivity system, a conversation with your future self.", 5),
    _feed("The Quiet Engineer", "mac", "A tour of the macOS launch system, one plist at a time",
          "LaunchAgents, LaunchDaemons and the job that wakes up at 3 a.m.", 8),
    _feed("Orbital", "science", "Mapping the ocean floor with sound",
          "Most of the seabed is still blank on our maps. That is changing.", 26),
]}

MEMORY_FACTS = ["likes ambient and downtempo while working", "keeps Xcode DerivedData; clears it monthly",
                "wants the brief to lead with science, skip celebrity news"]

FRICTION = [{"id": 3, "text": "brief: link straight to the article, not the comments page", "area": "brief",
             "status": "open", "opened": "2026-10-22T09:12:00+02:00"},
            {"id": 2, "text": "music: catalog playback needs a setup step", "area": "music", "status": "closed",
             "opened": "2026-10-20T21:40:00+02:00", "note": "merged evolve/2026-10-21"}]

JOURNAL = [{"ts": "2026-10-24T08:00:41+02:00", "kind": "daemon", "msg": "Good morning — Saturday 24 October"},
           {"ts": "2026-10-24T09:14:02+02:00", "kind": "music", "msg": "played Weightless — Marconi Union"},
           {"ts": "2026-10-24T10:02:17+02:00", "kind": "approval", "msg": "allowed: Bash bin/cos clean apply xcode-derived-data --yes"},
           {"ts": "2026-10-24T10:02:31+02:00", "kind": "action", "msg": "clean xcode-derived-data freed 17.3 GB"}]

EVOLVE = [{"branch": "evolve/2026-10-24", "commits": ["a1b2c3d brief: link to articles instead of comment threads"]}]

DAEMONS = [
    {"name": "pulse", "installed": True, "loaded": True, "schedule": "every 2h", "llm": False, "last_run": "2026-10-24T10:00:00",
     "last_ok": True, "description": "Every 2 hours: refresh vitals, feeds, update and cleanup caches; alert on low disk. No LLM, no cost."},
    {"name": "morning", "installed": True, "loaded": True, "schedule": "daily 08:00", "llm": True, "last_run": "2026-10-24T08:00:41",
     "last_ok": True, "description": "08:00 daily: Claude writes your morning brief and sends a notification."},
    {"name": "evolve", "installed": True, "loaded": True, "schedule": "daily 03:30", "llm": True, "last_run": "2026-10-24T03:30:12",
     "last_ok": True, "description": "03:30 daily: one small, tested improvement to Claude OS on a local evolve/* branch."},
    {"name": "board", "installed": False, "loaded": False, "schedule": "Sun 10:00", "llm": True, "last_run": None,
     "last_ok": None, "description": "Sundays 10:00: the board reviews the week and sets next week's priorities."},
]

BRIEF = {"file": "demo.md", "ts": NOW - 3 * 3600, "text": """# Good morning — Saturday 24 October

**Mac:** 412 GB free, all quiet. **Updates:** 23 waiting; Node 25 is a major bump, so look first.

## Worth your time
- **The quiet comeback of the airship** — cargo routes where runways don't reach. https://example.com/
- **On keeping a notebook for twenty years** — exactly your kind of slow read. https://example.com/

## Claude OS
One evolve branch waiting: *brief: link to articles instead of comment threads*.
"""}

BOOT = ["◆ Claude OS (demo) · a fictional Mac, for screenshots",
        "  Mac16,8 · macOS 27.0.1 · Apple M4 Pro · up 3d 2h",
        "  disk 412 GB free (41.4%) · memory 21.4 GB/48.0 GB · battery 81% charging",
        "  signals: 23 updates available · 41.2 GB safely reclaimable",
        "  music: ▶ Weightless — Marconi Union",
        "  daemons: pulse ●  morning ●  evolve ●  board –",
        "  memory: 3 things you've taught me"]

WEATHER = {"configured": True, "place": "Lisbon, Portugal", "source": "city", "units": "°C, km/h", "fetched": NOW,
           "now": {"temp": 19.4, "feels": 18.9, "wind": 11.0, "summary": "Mostly clear", "symbol": "🌤"},
           "today": {"max": 22.0, "min": 14.0, "precip_pct": 10, "summary": "Mostly clear", "symbol": "🌤"},
           "tomorrow": {"max": 21.0, "min": 13.0, "precip_pct": 40, "summary": "Showers", "symbol": "🌦"}}

SETTINGS = {"music": {"apple_music": True, "authorization": "authorized", "error": None, "shortcut": False},
            "weather": {"name": "Lisbon, Portugal", "source": "city"}}

GETS = {
    "/api/boot": {"version": "demo", "lines": BOOT},
    "/api/status": STATUS,
    "/api/clean": {"ts": NOW - 3600, "data": CLEAN},
    "/api/updates": {"ts": NOW - 7200, "data": UPDATES},
    "/api/music/now": MUSIC_NOW,
    "/api/music/playlists": PLAYLISTS,
    "/api/music/search": {"library": [], "catalog": []},
    "/api/feeds": FEEDS,
    "/api/friction": FRICTION,
    "/api/memory": {"text": "\n".join("- " + f for f in MEMORY_FACTS), "facts": MEMORY_FACTS},
    "/api/log": JOURNAL,
    "/api/evolve": EVOLVE,
    "/api/evolve/diff": {"log": "a1b2c3d brief: link to articles instead of comment threads\n .claude/skills/brief/SKILL.md | 2 +-",
                         "diff": "@@ -38 +38 @@\n-Mark what you showed as read.\n+Prefer the article URL over the comments page.\n"},
    "/api/daemons": DAEMONS,
    "/api/brief": BRIEF,
    "/api/trends": {"rows": [], "disk_per_week": None},
    "/api/chats": [],
    "/api/weather": WEATHER,
    "/api/settings": SETTINGS,
}


def handle_get(path):
    """Fixture for a read endpoint, or None to let the real handler answer (docs only)."""
    return GETS.get(path)


def fake_job(label):
    return {"id": "0000000000", "label": label, "argv": [], "done": True, "rc": 0, "seconds": 0.1,
            "output": "(demo mode: nothing was changed)"}


# ---------------------------------------------------------------- scripted chat

REPLY_1 = """**No, not urgently.** You have 412 GB free (41%), which is comfortable.

That said, **41 GB is safe to clear** whenever you like:

| Size | What | Cost of clearing |
|---|---|---|
| 17.3 GB | Xcode DerivedData | next build is slower |
| 12.6 GB | Device support symbols | re-copied when a device connects |
| 6.4 GB | npm cache | packages re-download on demand |

Want me to clear the safe ones?"""


class DemoSession(chat.Session):
    def __init__(self):
        super().__init__(spawn=False)
        self.model = "demo"
        self.turn = 0
        self._emit("ready", model="demo")

    def _script(self, steps):
        def run():
            for delay, kind, data in steps:
                time.sleep(delay)
                if kind == "permission":
                    self.pending[data["request_id"]] = {"tool_name": "Bash", "input": data["input"]}
                self._emit(kind, **data)
            if not self.pending:
                self.state = "idle"
        threading.Thread(target=run, daemon=True).start()

    def send(self, text):
        self.touched = time.time()
        self.title = self.title or text[:60]
        self.state = "busy"
        self._emit("user", text=text)
        self.turn += 1
        if self.turn == 1:
            words = REPLY_1.split(" ")
            steps = [(0.6, "tool_use", {"id": "d1", "name": "Bash", "input": {"command": "bin/cos clean --json"}}),
                     (0.9, "tool_result", {"tool_use_id": "d1", "content": "(demo scan)", "is_error": False})]
            steps += [(0.03, "text_delta", {"text": w + " "}) for w in words]
            steps += [(0.1, "text", {"text": REPLY_1}),
                      (0.1, "result", {"is_error": False, "cost": 0.0, "total_cost": 0.0, "duration_ms": 4200, "text": None})]
        else:
            cmd = "bin/cos clean apply xcode-derived-data xcode-device-support npm-cache --yes"
            steps = [(0.5, "text", {"text": "Clearing the three safe targets now."}),
                     (0.4, "tool_use", {"id": "d2", "name": "Bash", "input": {"command": cmd}}),
                     (0.4, "permission", {"request_id": "demo-perm", "tool_name": "Bash", "input": {"command": cmd},
                                          "description": "Reclaim the three safe cleanup targets", "tool_use_id": "d2"})]
        self._script(steps)
        return True

    def answer(self, request_id, allow, message=None):
        if self.pending.pop(request_id, None) is None:
            return False
        self._emit("permission_resolved", request_id=request_id, allow=allow)
        if allow:
            steps = [(0.8, "tool_result", {"tool_use_id": "d2", "content": "freed 36.3 GB", "is_error": False}),
                     (0.3, "text", {"text": "Done: **36.3 GB freed**. You now have 448 GB free."})]
        else:
            steps = [(0.3, "tool_result", {"tool_use_id": "d2", "content": "denied", "is_error": True}),
                     (0.3, "text", {"text": "No problem, I left everything as it was."})]
        steps.append((0.1, "result", {"is_error": False, "cost": 0.0, "total_cost": 0.0, "duration_ms": 1500, "text": None}))
        self._script(steps)
        return True

    def interrupt(self):
        return True

    def close(self):
        self.state = "closed"
