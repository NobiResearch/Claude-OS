"""Shared plumbing for every syscall: paths, processes, journal, config, cache.

Everything private lives under CLAUDE_OS_HOME (default ~/.claude-os), never in
the repository. The repository is public; this module is the boundary.
"""

import datetime as _dt
import json
import os
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def home(*parts):
    """Private state directory (created on demand)."""
    base = Path(os.environ.get("CLAUDE_OS_HOME", "~/.claude-os")).expanduser()
    path = base.joinpath(*parts)
    target = path if not path.suffix else path.parent
    if not target.is_dir():
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # read-only contexts (sandboxed evolve runs) still get a path back
    return path


# ---------------------------------------------------------------- processes

class Result:
    __slots__ = ("rc", "out", "err")

    def __init__(self, rc, out, err):
        self.rc, self.out, self.err = rc, out, err

    @property
    def ok(self):
        return self.rc == 0

    def __repr__(self):
        return "Result(rc=%r, out=%r, err=%r)" % (self.rc, self.out[:80], self.err[:80])


def run(cmd, timeout=30, input=None, env=None, cwd=None):
    """Run a command and capture its output. Never raises for missing or unrunnable
    binaries, undecodable output, or timeouts; on timeout or Ctrl-C the whole process
    group is killed so no grandchildren are left behind."""
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update(env)
    try:
        p = subprocess.Popen(
            cmd, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", env=full_env, cwd=cwd, start_new_session=True,
        )
    except FileNotFoundError:
        return Result(127, "", "command not found: %s" % cmd[0])
    except OSError as e:
        return Result(126, "", "cannot run %s: %s" % (cmd[0], e))
    try:
        out, err = p.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired:
        _killpg(p)
        out, err = _drain(p)
        return Result(124, out.strip(), ("timed out after %ss: %s\n%s" % (timeout, " ".join(cmd), err)).strip())
    except KeyboardInterrupt:
        _killpg(p)
        raise
    return Result(p.returncode, out.strip(), err.strip())


def stream(cmd, on_line, timeout=30, input=None, env=None, cwd=None):
    """Like run(), but each stdout line goes to on_line as it arrives (and isn't kept). Same
    promises: never raises for a missing binary or a timeout, and the whole process group
    dies on timeout, on Ctrl-C, on any error here and when the command ends. The deadline
    doesn't wait for output, stderr drains on its own thread (the last lines are kept), and
    an on_line that fails loses that line, not the run."""
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update(env)
    try:
        p = subprocess.Popen(
            cmd, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", env=full_env, cwd=cwd, start_new_session=True,
        )
    except FileNotFoundError:
        return Result(127, "", "command not found: %s" % cmd[0])
    except OSError as e:
        return Result(126, "", "cannot run %s: %s" % (cmd[0], e))
    tail = deque(maxlen=40)
    expired = threading.Event()

    def read_stderr():
        for line in p.stderr:
            tail.append(line.rstrip())

    def expire():
        expired.set()
        _killpg(p)

    reader = threading.Thread(target=read_stderr, daemon=True)
    reader.start()
    timer = threading.Timer(timeout, expire)
    timer.daemon = True
    timer.start()
    finished = False
    try:
        if input is not None:
            try:
                p.stdin.write(input)
                p.stdin.close()
            except OSError:
                pass  # it exited (or was killed) before reading its input
        for line in p.stdout:
            try:
                on_line(line)
            except Exception:
                pass
        finished = True
    finally:
        timer.cancel()
        if finished:  # give it a moment to exit by itself after closing its output
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        _killpg(p)  # also takes any grandchildren still holding on
        p.wait()
        reader.join(timeout=2)
    err = "\n".join(tail).strip()
    if expired.is_set():
        return Result(124, "", ("timed out after %ss\n%s" % (timeout, err)).strip())
    return Result(p.returncode, "", err)


def _killpg(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass


def _drain(p):
    try:
        out, err = p.communicate(timeout=5)
        return out or "", err or ""
    except subprocess.TimeoutExpired:
        return "", ""


SANDBOX_PROFILE = """(version 1)
(allow default)
(deny network-outbound (remote ip))
(allow network-outbound (remote ip "localhost:*"))
(deny file-write*)
(allow file-write* (subpath %(cwd)s) (subpath "/private/tmp") (subpath "/private/var/folders") (subpath "/dev"))
(deny file-read* %(private)s)
(allow file-read* (subpath %(cwd)s))
"""

# Never readable by model-written code: credentials and the human's private state.
PRIVATE_DIRS = (".ssh", ".claude-os", ".claude", ".aws", ".gnupg", ".config/gh", ".netrc", ".npmrc",
                "Library/Keychains", "Library/Application Support/com.apple.TCC")


def run_sandboxed(cmd, cwd, timeout=600):
    """Run untrusted code (e.g. tests an evolve run wrote): no network, writes only inside
    cwd and temp dirs, and a throwaway HOME so nothing can touch the real one."""
    import tempfile
    real = os.path.realpath(cwd)
    home_dir = os.path.realpath(os.path.expanduser("~"))
    private = " ".join("(subpath %s)" % json.dumps(os.path.join(home_dir, p)) for p in PRIVATE_DIRS)
    profile = SANDBOX_PROFILE % {"cwd": json.dumps(real), "private": private}
    with tempfile.TemporaryDirectory(prefix="cos-sandbox-") as tmp:
        # CLAUDE_OS_DAEMON makes `cos` refuse every mutating command inside, too.
        env = {"HOME": tmp, "CLAUDE_OS_HOME": os.path.join(tmp, "state"), "COS_SANDBOXED": "1",
               "CLAUDE_OS_DAEMON": "sandboxed-tests"}
        return run(["sandbox-exec", "-p", profile] + list(cmd), timeout=timeout, cwd=real, env=env)


def osascript(script, timeout=10):
    """Run AppleScript with a hard timeout.

    Apple Events block forever behind modal dialogs and permission prompts,
    so a timeout is mandatory, not optional.
    """
    return run(["osascript", "-e", script], timeout=timeout)


def which(name):
    return shutil.which(name)


def app_running(name):
    return run(["pgrep", "-xq", name], timeout=3).rc == 0


def applescript_str(s):
    """Quote a Python string as an AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ---------------------------------------------------------------- formatting

def human_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return ("%d %s" if unit == "B" else "%.1f %s") % (n, unit)
        n /= 1024.0


def ago(ts):
    """'5m ago' style age for an epoch timestamp."""
    if not ts:
        return "never"
    s = max(0, int(time.time() - ts))
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if s >= size:
            return "%d%s ago" % (s // size, unit)
    return "just now"


def now_iso():
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def emit(data, as_json, render):
    """Print data as JSON (for machines) or via render() (for humans)."""
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        render(data)


def die(msg, rc=1):
    print("cos: %s" % msg, file=sys.stderr)
    sys.exit(rc)


# ---------------------------------------------------------------- journal

def journal(kind, msg, **data):
    """Append one event to the private journal (monthly JSONL files)."""
    entry = {"ts": now_iso(), "kind": kind, "msg": msg}
    entry.update(data)
    path = home("journal", _dt.date.today().strftime("%Y-%m") + ".jsonl")
    try:
        with open(path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass
    return entry


def read_journal(days=7, kind=None):
    cutoff = _dt.datetime.now().astimezone() - _dt.timedelta(days=days)
    entries = []
    jdir = home("journal")
    for path in sorted(jdir.glob("*.jsonl")):
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if _dt.datetime.fromisoformat(e["ts"]) < cutoff:
                        continue
                except (ValueError, KeyError):
                    continue
                if kind and e.get("kind") != kind:
                    continue
                entries.append(e)
    return entries


# ---------------------------------------------------------------- json state

def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def cache_get(name, max_age=None):
    """Return cached payload, or None if missing/stale."""
    blob = load_json(home("cache", name + ".json"))
    if not blob:
        return None
    if max_age is not None and time.time() - blob.get("ts", 0) > max_age:
        return None
    return blob


def cache_put(name, payload):
    blob = {"ts": time.time(), "data": payload}
    try:
        save_json(home("cache", name + ".json"), blob)
    except OSError:
        pass
    return blob


# ---------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "music": {"storefront": None, "apple_music": False},
    "weather": {},
    "notify": {"enabled": True, "native": False},
    "pulse": {"low_disk_gb": 20, "backup_check": True},
    "autonomy": {"night_shift": False},  # decision 0006: only the human turns this on
}


def config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = load_json(home("config.json"), {}) or {}
    for section, values in user.items():
        if isinstance(values, dict) and isinstance(cfg.get(section), dict):
            cfg[section].update(values)
        else:
            cfg[section] = values
    return cfg


def config_set(dotted, value):
    user = load_json(home("config.json"), {}) or {}
    node = user
    keys = dotted.split(".")
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    save_json(home("config.json"), user)
    return user


# ---------------------------------------------------------------- network

USER_AGENT = "ClaudeOS/0.1 (+https://github.com/markusskov/Claude-OS)"
_SSL = None


def ssl_context():
    """python.org builds ship without CA certs; macOS keeps a bundle at /etc/ssl/cert.pem."""
    global _SSL
    if _SSL is None:
        _SSL = ssl.create_default_context()
        if os.path.exists("/etc/ssl/cert.pem"):
            try:
                _SSL.load_verify_locations("/etc/ssl/cert.pem")
            except (OSError, ssl.SSLError):
                pass
    return _SSL


def http_get(url, headers=None, timeout=12):
    """GET a URL; returns the open response (use as a context manager). Raises urllib errors."""
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())


def curl_get(url, timeout=12):
    """Fallback for sites that reject Python's TLS fingerprint. Returns bytes or None."""
    try:
        p = subprocess.run(["curl", "-sfL", "--max-time", str(timeout), "-A", USER_AGENT, url],
                           capture_output=True, timeout=timeout + 5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


# ---------------------------------------------------------------- mac i/o

def app_url(path, **params):
    """A claude-os:// link for a command that changes something. It carries the per-launch
    nonce Claude OS.app keeps in ~/.claude-os/state/app.nonce (0600), so a web page or any
    process that can't read that file can't make the app act."""
    import urllib.parse
    try:
        params["nonce"] = home("state", "app.nonce").read_text().strip()
    except OSError:
        params["nonce"] = ""
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return "claude-os://%s?%s" % (path, query)


def ensure_app(wait=12):
    """Start Claude OS.app (in the background) if it isn't running; True once it's up."""
    if app_running("ClaudeOS"):
        return True
    bundle = os.path.expanduser("~/Applications/Claude OS.app")
    if not os.path.isdir(bundle):
        return False
    nonce = home("state", "app.nonce")
    before = nonce.stat().st_mtime if nonce.exists() else 0
    run(["open", "-g", bundle], timeout=15)
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.5)
        if app_running("ClaudeOS") and nonce.exists() and nonce.stat().st_mtime > before:
            return True
    return app_running("ClaudeOS")


def native_notifications():
    """Claude OS.app posts them itself when the human turned it on, macOS allowed it and the
    app is running. Background jobs never launch the app just to show a notification."""
    if not config()["notify"].get("native"):
        return False
    status = load_json(home("state", "notify.json"), {}) or {}
    return status.get("authorization") == "authorized" and app_running("ClaudeOS")


# The only places a click on a notification may open. The app checks the same list and maps
# each to a fixed view; a click only ever navigates.
NOTIFY_TARGETS = ("board", "brief", "evolve", "daemons")


def notify(message, title="Claude OS", subtitle=None, sound=None, target=None):
    if not config()["notify"]["enabled"]:
        return Result(0, "", "notifications disabled")
    if native_notifications():
        # The text goes in a private file; the link that wakes the app carries nothing.
        import uuid
        note = {"title": title, "subtitle": subtitle or "", "body": message, "sound": bool(sound)}
        if target in NOTIFY_TARGETS:
            note["target"] = target
        path = home("state", "outbox", "%d-%s.json" % (int(time.time() * 1000), uuid.uuid4().hex[:8]))
        try:
            with open(path, "w") as f:
                json.dump(note, f, ensure_ascii=False)
            os.chmod(str(path), 0o600)
            r = run(["open", "-g", "claude-os://notify/flush"], timeout=10)
            if r.ok:
                return r
            os.unlink(str(path))  # couldn't wake the app: say it the old way instead
        except OSError:
            pass  # fall through to AppleScript
    script = "display notification %s with title %s" % (
        applescript_str(message), applescript_str(title))
    if subtitle:
        script += " subtitle " + applescript_str(subtitle)
    if sound:
        script += " sound name " + applescript_str(sound)
    return osascript(script, timeout=5)


def locale_country():
    """Two-letter storefront from the system locale, e.g. en_GB -> gb."""
    r = run(["defaults", "read", "NSGlobalDomain", "AppleLocale"], timeout=3)
    loc = r.out if r.ok else ""
    if "_" in loc:
        return loc.split("_")[1][:2].lower()
    return "us"
