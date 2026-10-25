"""cos daemon — scheduled background work via launchd.

Daemons are defined in etc/daemons.json. `builtin` daemons are plain Python
(free); `prompt` daemons run headless Claude Code with a tool allowlist and a
timeout, plus a budget cap when Claude is billed per token (an API key; a Pro or Max plan
has no per-run cost, so its runs aren't cut short). Output of every run lands in
~/.claude-os/runs/.
"""

import datetime as dt
import json
import os
import plistlib
import time

from . import core

LABEL_PREFIX = "com.claude-os."
AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")

# Defense in depth: no daemon may mutate the machine or publish, whatever its allowlist
# says. (The real enforcement is in cli.check_mutation, which refuses these commands
# whenever CLAUDE_OS_DAEMON is set; these patterns just stop the attempt earlier.)
_MUTATING = ["clean apply", "update apply", "daemon install", "daemon uninstall", "daemon run",
             "evolve merge", "evolve discard", "install", "uninstall", "cal connect", "weather set",
             "weather clear", "feeds add", "feeds mute", "config", "music play", "music like", "music unlike", "music radio", "remember",
             "memory --forget", "ask", "serve", "app", "startup --full"]
ALWAYS_DENIED = ["Bash(%s %s*)" % (pre, m) for m in _MUTATING for pre in ("bin/cos", "./bin/cos", "cos")] + [
    "Bash(git push*)", "Bash(sudo *)", "Bash(curl *)", "Bash(osascript *)",
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
        out.append({"name": name, "installed": os.path.exists(plist_path(name)), "loaded": is_loaded(name),
                    "schedule": describe_schedule(spec["schedule"]), "llm": "prompt" in spec,
                    "description": spec["description"],
                    "last_run": last["ts"] if last else None, "last_ok": last.get("ok") if last else None})
    return out


def render_status(rows):
    for r in rows:
        mark = "●" if r["loaded"] else ("○" if r["installed"] else "–")
        last = r["last_run"][:16].replace("T", " ") if r["last_run"] else "never"
        print("%s %-8s %-12s %-5s last: %-16s %s" % (mark, r["name"], r["schedule"], "llm" if r["llm"] else "", last, r["description"]))
    print("\n● running  ○ installed, not loaded  – off · cos daemon install <name>|--all")


# ---------------------------------------------------------------- running

def _lock(name):
    path = core.home("state", "daemon-%s.lock" % name)
    if path.exists() and time.time() - path.stat().st_mtime < 3 * 3600:
        return None
    path.write_text(str(os.getpid()))
    return path


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
    cmd = ["claude", "-p", "--output-format", "text",
           "--permission-mode", spec.get("permission_mode", "dontAsk")]
    if capped and spec.get("budget_usd"):
        cmd += ["--max-budget-usd", str(spec["budget_usd"])]
    if spec.get("allowed_tools"):
        cmd += ["--allowedTools"] + spec["allowed_tools"]
    if spec.get("sandbox"):
        cmd += ["--settings", json.dumps(SANDBOX_SETTINGS)]
    cmd += ["--disallowedTools"] + spec.get("disallowed_tools", []) + ALWAYS_DENIED
    return cmd


def run_llm(name, spec):
    from . import evolve
    cwd = str(core.ROOT)
    workspace = None
    if spec.get("workspace"):
        workspace = evolve.new_workspace()
        cwd = workspace["path"]
    env = {"CLAUDE_OS_DAEMON": name, "CLAUDE_OS_HOME": str(core.home())}
    # The cap is Claude Code's estimate at API prices: real money with an API key, but on a
    # Pro or Max plan it only cut runs short (the timeout still bounds them).
    r = core.run(claude_command(spec, capped=not on_subscription()), input=spec["prompt"], cwd=cwd, env=env,
                 timeout=int(spec.get("timeout_minutes", 10)) * 60)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = core.home("runs", name, stamp + ".md")
    out_path.write_text(r.out + ("\n\n---\nstderr:\n" + r.err if r.err else ""))
    summary = next((l.strip("# ").strip() for l in r.out.splitlines() if l.strip()), "(no output)")[:180]
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
    try:
        if spec.get("builtin") == "pulse":
            ok, summary, out = True, pulse(), None
        else:
            ok, summary, out = run_llm(name, spec)
            core.notify(summary, subtitle=name.capitalize())
    except Exception as e:
        ok, summary, out = False, "%s crashed: %s" % (name, e), None
    finally:
        lock.unlink()
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
