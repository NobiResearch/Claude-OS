"""cos daemon — scheduled background work via launchd.

Daemons are defined in etc/daemons.json. `builtin` daemons are plain Python
(free); `prompt` daemons run headless Claude Code with a tool allowlist and a
timeout, plus a budget cap when Claude is billed per token (an API key; a Pro or Max plan
has no per-run cost, so its runs aren't cut short). Output of every run lands in
~/.claude-os/runs/. While a run is going, ~/.claude-os/state/live/<name>.json says so
(decision 0007): which agents it started, their votes, and the tool it's on, as labels only.
"""

import datetime as dt
import json
import os
import plistlib
import re
import time
from pathlib import Path

from . import core

LABEL_PREFIX = "com.claude-os."
AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")

# Defense in depth: no daemon may mutate the machine or publish, whatever its allowlist
# says. (The real enforcement is in cli.check_mutation, which refuses these commands
# whenever CLAUDE_OS_DAEMON is set; these patterns just stop the attempt earlier.)
_MUTATING = ["clean apply", "update apply", "daemon install", "daemon uninstall", "daemon run",
             "evolve merge", "evolve discard", "install", "uninstall", "cal connect", "weather set",
             "weather clear", "feeds add", "feeds mute", "config", "music play", "music like", "music unlike", "music radio", "remember",
             "memory --forget", "ask", "serve", "app", "startup --full", "security on",
             "net --speed"]
ALWAYS_DENIED = ["Bash(%s %s*)" % (pre, m) for m in _MUTATING for pre in ("bin/cos", "./bin/cos", "cos")] + [
    "Bash(git push*)", "Bash(sudo *)", "Bash(curl *)", "Bash(osascript *)",
    # A pending wakeup keeps a headless run alive until its timeout (the first weekly board
    # meeting finished in 6 minutes and then sat for 14), and a daemon has no business
    # scheduling more work or cloud routines anyway.
    "ScheduleWakeup", "CronCreate", "CronDelete", "Monitor", "RemoteTrigger",
]

# Evolve edits code and runs tests, so its shell runs in Claude Code's sandbox: writes
# confined to its workspace clone, no network, no unsandboxed escape hatch.
SANDBOX_SETTINGS = {"sandbox": {"enabled": True, "failIfUnavailable": True,
                                "allowUnsandboxedCommands": False, "autoAllowBashIfSandboxed": False,
                                # the test suite starts servers on 127.0.0.1; still no outside network
                                "network": {"allowLocalBinding": True}}}


def definitions():
    with open(core.ROOT / "etc" / "daemons.json") as f:
        return json.load(f)


def label(name):
    return LABEL_PREFIX + name


def plist_path(name):
    return os.path.join(AGENTS_DIR, label(name) + ".plist")


def build_plist(name, spec, root=None, path_env=None):
    root = str(root or core.ROOT)
    log = str(core.home("logs", name + ".log"))
    p = {
        "Label": label(name),
        "ProgramArguments": ["/usr/bin/env", "python3", os.path.join(root, "bin", "cos"), "daemon", "run", name],
        "WorkingDirectory": root,
        "EnvironmentVariables": {"PATH": path_env or os.environ.get("PATH", "/usr/bin:/bin"),
                                 "CLAUDE_OS_HOME": str(core.home())},
        "StandardOutPath": log,
        "StandardErrorPath": log,
        "ProcessType": "Background",
        "RunAtLoad": False,
    }
    sched = spec["schedule"]
    if "every_minutes" in sched:
        p["StartInterval"] = int(sched["every_minutes"]) * 60
    else:
        cal = {"Hour": int(sched["hour"]), "Minute": int(sched.get("minute", 0))}
        if "weekday" in sched:
            cal["Weekday"] = int(sched["weekday"])
        p["StartCalendarInterval"] = cal
    return p


def is_loaded(name):
    return core.run(["launchctl", "print", "gui/%d/%s" % (os.getuid(), label(name))], timeout=5).ok


def install(name):
    spec = definitions()[name]
    os.makedirs(AGENTS_DIR, exist_ok=True)
    path = plist_path(name)
    if is_loaded(name):
        core.run(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), label(name))], timeout=10)
    with open(path, "wb") as f:
        plistlib.dump(build_plist(name, spec), f)
    r = core.run(["launchctl", "bootstrap", "gui/%d" % os.getuid(), path], timeout=10)
    if not r.ok:
        r = core.run(["launchctl", "load", "-w", path], timeout=10)
    core.journal("action", "daemon %s installed" % name, daemon=name, rc=r.rc)
    return r


def uninstall(name):
    core.run(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), label(name))], timeout=10)
    if os.path.exists(plist_path(name)):
        os.remove(plist_path(name))
    core.journal("action", "daemon %s uninstalled" % name, daemon=name)


def describe_schedule(sched):
    if "every_minutes" in sched:
        m = sched["every_minutes"]
        return "every %dh" % (m // 60) if m % 60 == 0 else "every %dm" % m
    t = "%02d:%02d" % (sched["hour"], sched.get("minute", 0))
    if "weekday" in sched:
        return "%s %s" % (["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][sched["weekday"] % 7], t)
    return "daily %s" % t


def last_run(name):
    runs = [e for e in core.read_journal(days=30, kind="daemon") if e.get("daemon") == name]
    return runs[-1] if runs else None


def status():
    out = []
    for name, spec in definitions().items():
        last = last_run(name)
        now = live(name)
        out.append({"name": name, "installed": os.path.exists(plist_path(name)), "loaded": is_loaded(name),
                    "schedule": describe_schedule(spec["schedule"]), "llm": "prompt" in spec,
                    "description": spec["description"],
                    "last_run": last["ts"] if last else None, "last_ok": last.get("ok") if last else None,
                    "running_minutes": now["minutes"] if now else None})
    return out


def render_status(rows):
    for r in rows:
        mark = "●" if r["loaded"] else ("○" if r["installed"] else "–")
        last = r["last_run"][:16].replace("T", " ") if r["last_run"] else "never"
        if r.get("running_minutes") is not None:
            last = "running %d min" % r["running_minutes"]
            print("%s %-8s %-12s %-5s now:  %-16s %s" % (mark, r["name"], r["schedule"], "llm" if r["llm"] else "", last, r["description"]))
            continue
        print("%s %-8s %-12s %-5s last: %-16s %s" % (mark, r["name"], r["schedule"], "llm" if r["llm"] else "", last, r["description"]))
    print("\n● running  ○ installed, not loaded  – off · cos daemon install <name>|--all")


# ---------------------------------------------------------------- running

def _lock(name):
    path = core.home("state", "daemon-%s.lock" % name)
    if path.exists() and time.time() - path.stat().st_mtime < 3 * 3600 and _alive(_pid(path)):
        return None
    path.write_text(str(os.getpid()))
    return path


def _pid(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ---------------------------------------------------------------- live runs

# Where a click on a daemon's notification lands in the app (core.NOTIFY_TARGETS).
NOTIFY_TARGET = {"board": "board", "morning": "brief", "evolve": "evolve"}

# Only labels reach the live file. Tool inputs, tool results and free text can hold anything
# private (memory, journal, calendar), so they never leave the stream.
LABEL = re.compile(r"[A-Za-z][\w:.-]{0,60}")
COS_VERB = re.compile(r"(?:\./)?(?:bin/)?cos\s+([a-z]+)")
VOTE = re.compile(r"VOTE:\W*(approve|amend|reject)", re.I)
HEADING = re.compile(r"^#{1,3}\s+(.+)$", re.M)


def tool_label(block):
    name = str(block.get("name") or "")
    if name == "Bash":
        m = COS_VERB.match(str((block.get("input") or {}).get("command", "")).strip())
        return "cos " + m.group(1) if m else "Bash"
    return name if LABEL.fullmatch(name) else "a tool"


class Transcript:
    """One headless run, read from Claude Code's stream-json: its output (each turn's final
    text, as text mode printed it), the background agents it started (for the board, its
    seats and their votes) and the tool it's on."""

    def __init__(self):
        self.turns, self.pending = [], None
        self.agents = {}  # tool_use_id -> {"type", "state", "vote"}
        self.now, self.error = None, False

    def feed(self, line):
        """Take one line of the stream -> True when something worth showing changed."""
        msg = json.loads(line)
        kind, sub = msg.get("type"), msg.get("subtype")
        if kind == "assistant":
            blocks = (msg.get("message") or {}).get("content") or []
            parent = msg.get("parent_tool_use_id")
            if parent:  # an agent's own messages: only its vote matters here
                agent = self.agents.get(parent)
                for b in blocks:
                    m = VOTE.search(b.get("text") or "") if agent and b.get("type") == "text" else None
                    if m:
                        agent["vote"] = m.group(1).lower()
                return False
            for b in blocks:
                if b.get("type") == "text" and (b.get("text") or "").strip():
                    self.pending = b["text"].strip()
                elif b.get("type") == "tool_use":
                    self.now = tool_label(b)
            return True
        if kind == "result":
            text = (msg.get("result") or "").strip() or self.pending
            if text:
                self.turns.append(text)
            self.pending, self.now, self.error = None, None, bool(msg.get("is_error"))
            return True
        if kind == "system" and sub == "task_started":
            agent_type = str(msg.get("subagent_type") or "")
            self.agents[msg.get("tool_use_id") or msg.get("task_id")] = {
                "type": agent_type if LABEL.fullmatch(agent_type) else "agent", "state": "working", "vote": None}
            return True
        if kind == "system" and sub == "task_notification":
            agent = self.agents.get(msg.get("tool_use_id") or msg.get("task_id"))
            if not agent:
                return False
            agent["state"] = "done" if msg.get("status") == "completed" else "stopped"
            m = VOTE.search(str(msg.get("summary") or ""))
            if m:
                agent["vote"] = m.group(1).lower()
            return True
        return False

    def output(self):
        return "\n\n".join(self.turns + ([self.pending] if self.pending else []))


def summarize(name, text, timed_out, minutes, ok):
    """The line the notification and the journal show: what the run produced, never the
    chatter it started with."""
    title = name.capitalize()
    if timed_out:
        return "%s ran out of time after %d min%s" % (title, minutes, "; partial output saved" if text else "")
    if not ok:
        return "%s stopped with an error (cos daemon logs %s)" % (title, name)
    m = HEADING.search(text)
    last = text.split("\n\n")[-1] if text else ""
    line = m.group(1) if m else next((l for l in last.splitlines() if l.strip()), "(no output)")
    return line.strip().strip("*#").strip()[:180]


def live_path(name):
    return core.home("state", "live", name + ".json")


def write_live(name, started, transcript=None):
    t = transcript or Transcript()
    data = {"name": name, "pid": os.getpid(), "started": started, "updated": core.now_iso(),
            "agents": list(t.agents.values()), "now": t.now, "turns": len(t.turns)}
    path = live_path(name)
    tmp = Path(str(path) + ".tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        pass  # the run matters more than its progress report


def live(name):
    """The run in progress, or None. Live means its runner is still alive (an agent can
    think for minutes without a word), and not older than its timeout allows."""
    data = core.load_json(live_path(name))
    if not isinstance(data, dict) or not _alive(data.get("pid")):
        return None
    try:
        started = dt.datetime.fromisoformat(data["started"])
    except (KeyError, TypeError, ValueError):
        return None
    minutes = int((dt.datetime.now().astimezone() - started).total_seconds() // 60)
    limit = int((definitions().get(name) or {}).get("timeout_minutes", 10)) + 5
    if minutes > max(limit, 15):
        return None
    data["minutes"] = minutes
    return data


def pulse():
    """Keep the caches behind boot/statusline fresh; nag only when it matters."""
    from . import status as st, feeds, updates, clean
    st.refresh_backup()
    s = st.collect(include_slow=False)
    core.cache_put("status", s)
    st.record_trend(s)
    warn = [x["msg"] for x in s["signals"] if x["level"] == "warn"]
    state_path = core.home("state", "pulse.json")
    state = core.load_json(state_path, {}) or {}
    if warn and time.time() - state.get("last_alert", 0) > 12 * 3600:
        core.notify("; ".join(warn), subtitle="Pulse")
        state["last_alert"] = time.time()
    try:
        feeds.refresh(force=True)
    except Exception as e:
        core.journal("daemon", "pulse: feeds failed: %s" % e, daemon="pulse")
    try:
        from . import weather
        if weather.location():
            weather.forecast()  # keeps the weather alert signal fresh
    except Exception as e:
        core.journal("daemon", "pulse: weather failed: %s" % e, daemon="pulse")
    if not core.cache_get("updates", max_age=20 * 3600):
        updates.check(fetch=False)
    if not core.cache_get("clean", max_age=24 * 3600):
        clean.scan(deep=False)
    core.save_json(state_path, state)
    return "pulse ok: %s free%s" % (core.human_bytes(s["disk"]["free"]), ("; " + "; ".join(warn)) if warn else "")


def parse_auth(text):
    """`claude auth status` JSON -> True for a Pro or Max plan, False for anything else."""
    try:
        data = json.loads(text)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("loggedIn") is True and data.get("authMethod") == "claude.ai" \
        and data.get("subscriptionType") in ("pro", "max")


def on_subscription():
    """Is headless Claude covered by a flat plan? An API key always wins, and it bills per token."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return False
    r = core.run(["claude", "auth", "status"], timeout=20)
    return r.ok and parse_auth(r.out)


def claude_command(spec, capped=True):
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose",
           "--permission-mode", spec.get("permission_mode", "dontAsk")]
    if capped and spec.get("budget_usd"):
        cmd += ["--max-budget-usd", str(spec["budget_usd"])]
    if spec.get("allowed_tools"):
        cmd += ["--allowedTools"] + spec["allowed_tools"]
    if spec.get("sandbox"):
        cmd += ["--settings", json.dumps(SANDBOX_SETTINGS)]
    cmd += ["--disallowedTools"] + spec.get("disallowed_tools", []) + ALWAYS_DENIED
    return cmd


def run_llm(name, spec, started=None):
    from . import evolve
    cwd = str(core.ROOT)
    workspace = None
    if spec.get("workspace"):
        workspace = evolve.new_workspace()
        cwd = workspace["path"]
    env = {"CLAUDE_OS_DAEMON": name, "CLAUDE_OS_HOME": str(core.home())}
    transcript = Transcript()

    def on_line(line):
        if transcript.feed(line):
            write_live(name, started or core.now_iso(), transcript)

    minutes = int(spec.get("timeout_minutes", 10))
    # The cap is Claude Code's estimate at API prices: real money with an API key, but on a
    # Pro or Max plan it only cut runs short (the timeout still bounds them).
    r = core.stream(claude_command(spec, capped=not on_subscription()), on_line, input=spec["prompt"],
                    cwd=cwd, env=env, timeout=minutes * 60)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = core.home("runs", name, stamp + ".md")
    text = transcript.output()
    out_path.write_text(text + "\n" if text else "")
    if r.err:  # kept next to the output, not in it: the app shows the .md as it is
        try:
            fd = os.open(str(out_path.with_suffix(".err")), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(r.err + "\n")
        except OSError:
            pass
    ok = r.ok and not transcript.error
    summary = summarize(name, text, r.rc == 124, minutes, ok)
    if workspace:
        summary = evolve.after_run(workspace, summary)
    return r.ok, summary, str(out_path)


def run(name):
    spec = definitions().get(name)
    if not spec:
        core.die("no daemon %r" % name)
    lock = _lock(name)
    if not lock:
        print("%s is already running" % name)
        return 0
    started = time.time()
    since = core.now_iso()
    write_live(name, since)
    try:
        if spec.get("builtin") == "pulse":
            ok, summary, out = True, pulse(), None
        else:
            ok, summary, out = run_llm(name, spec, started=since)
            core.notify(summary, subtitle=name.capitalize(), target=NOTIFY_TARGET.get(name, "daemons"))
    except Exception as e:
        ok, summary, out = False, "%s crashed: %s" % (name, e), None
    finally:
        for path in (lock, live_path(name)):
            try:
                path.unlink()
            except OSError:
                pass
    core.journal("daemon", summary, daemon=name, ok=ok, output=out, seconds=round(time.time() - started))
    print(summary)
    return 0 if ok else 1


def main(args):
    names = list(definitions())
    c = args.daemon_cmd or "list"
    if c == "list":
        core.emit(status(), args.json, render_status)
        return 0
    if c in ("install", "uninstall"):
        targets = names if args.all else args.names
        if not targets:
            core.die("name a daemon (%s) or pass --all" % ", ".join(names))
        for n in targets:
            if n not in names:
                core.die("no daemon %r" % n)
            if c == "install":
                r = install(n)
                print("%s %s" % (n, "installed and loaded" if is_loaded(n) else "installed (load failed: %s)" % r.err))
            else:
                uninstall(n)
                print("%s removed" % n)
        return 0
    if c == "run":
        return run(args.name)
    if c == "logs":
        path = core.home("runs", args.name)
        runs = sorted(path.glob("*.md")) if path.is_dir() else []
        if runs:
            print(runs[-1].read_text())
        else:
            log = core.home("logs", args.name + ".log")
            print(log.read_text()[-4000:] if log.exists() else "no runs yet")
        return 0
    core.die("unknown daemon command %r" % c)
