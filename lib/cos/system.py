"""cos install / uninstall / doctor — putting Claude OS on (and off) this Mac."""

import os
import sys
import time

from . import __version__, core

BIN_DIR = os.path.expanduser("~/.local/bin")
LINK = os.path.join(BIN_DIR, "cos")


def _tilde(path):
    """A path as ~/…: what install and doctor print ends up pasted into bug reports, and a
    home folder's name is the human's username."""
    s, home = str(path), os.path.expanduser("~")
    return "~" + s[len(home):] if s == home or s.startswith(home + os.sep) else s


# The Mac skills that work from any folder (decision 0009): linked into ~/.claude/skills, so
# they load live from this checkout, where the night shift can't change them unseen.
# brief, board, evolve and lab stay in the repo.
EVERYWHERE = ("music", "tidy", "update", "startup")


def _ours(path):
    return os.path.islink(path) and os.path.realpath(path) == os.path.realpath(str(core.ROOT / "bin" / "cos"))


def skills_dir():
    return os.path.expanduser("~/.claude/skills")


def _skill_target(name):
    return str(core.ROOT / ".claude" / "skills" / name)


def _our_skill(path, name):
    return os.path.islink(path) and os.path.realpath(path) == os.path.realpath(_skill_target(name))


def link_skills():
    """-> step lines. Never touches a skill of the same name that isn't ours."""
    steps, linked = [], []
    os.makedirs(skills_dir(), exist_ok=True)
    for name in EVERYWHERE:
        path = os.path.join(skills_dir(), name)
        if os.path.lexists(path) and not _our_skill(path, name):
            steps.append("✗ ~/.claude/skills/%s exists and isn't Claude OS's; left it alone" % name)
            continue
        if os.path.lexists(path):
            os.remove(path)
        os.symlink(_skill_target(name), path)
        linked.append("/" + name)
    if linked:
        steps.append("✓ %s work in Claude Code from any folder (links in ~/.claude/skills)" % ", ".join(linked))
    return steps


def unlink_skills():
    removed = 0
    for name in EVERYWHERE:
        path = os.path.join(skills_dir(), name)
        if _our_skill(path, name):
            os.remove(path)
            removed += 1
    return removed


def keep_download_settings():
    """A downloaded copy's deny rules live in its gitignored .claude/settings.local.json, which
    `git clean -X` would delete: put back what's missing whenever Claude OS starts (decision
    0015). Rules the person added stay. -> True when it wrote the file."""
    if not core.downloaded():
        return False
    path = core.ROOT / ".claude" / "settings.local.json"
    if os.path.islink(str(path)):
        return False  # someone's own arrangement: never replaced by a plain file
    d = core.load_json(path, None) if path.exists() else {}
    if not isinstance(d, dict):
        # Not JSON we can read (a hand edit with a trailing comma, say): keep it, beside.
        aside = path.with_name("settings.local.json.broken-%d" % int(time.time()))
        os.replace(str(path), str(aside))
        core.journal("action", "moved a downloaded copy's unreadable settings.local.json aside to %s" % aside.name)
        d = {}
    perms = d.get("permissions") if isinstance(d.get("permissions"), dict) else {}
    deny = perms.get("deny") if isinstance(perms.get("deny"), list) else []
    missing = [rule for rule in core.DOWNLOAD_DENY if rule not in deny]
    if not missing:
        return False
    perms["deny"] = deny + missing
    d["permissions"] = perms
    path.parent.mkdir(exist_ok=True)
    core.save_json(path, d)
    core.journal("action", "put back a downloaded copy's deny rules: %s" % ", ".join(missing))
    return True


def install(args):
    from . import daemon
    core.home()
    os.chmod(str(core.home()), 0o700)
    steps = []
    os.makedirs(BIN_DIR, exist_ok=True)
    if os.path.lexists(LINK) and not _ours(LINK):
        steps.append("✗ %s exists and isn't Claude OS; left it alone" % _tilde(LINK))
    else:
        if os.path.lexists(LINK):
            os.remove(LINK)
        os.symlink(str(core.ROOT / "bin" / "cos"), LINK)
        steps.append("✓ `cos` linked into ~/.local/bin")
    if BIN_DIR not in os.environ.get("PATH", "").split(":"):
        steps.append("! ~/.local/bin isn't on your PATH; add it to ~/.zshrc")
    if not args.no_skills:
        steps += link_skills()
    r = core.run(["git", "config", "core.hooksPath", "githooks"], cwd=str(core.ROOT))
    steps.append("✓ Guardian pre-commit hook enabled" if r.ok else "✗ couldn't set git hooks: %s" % r.err)
    if not args.no_daemons:
        r = daemon.install("pulse")
        steps.append("✓ pulse daemon running (every 2h, no LLM)" if daemon.is_loaded("pulse") and not daemon.elsewhere("pulse")
                     else "✗ pulse not installed: %s" % (r.err or "launchd didn't load it"))
    core.journal("action", "installed Claude OS %s" % __version__)
    print("\n".join(steps))
    print("\nNext: run `cos` to boot into Claude OS.")
    print("\n".join(daemon_note(daemon.status(), skipped=args.no_daemons)))
    return 0


def daemon_note(rows, skipped):
    """What install says about background jobs. --no-daemons leaves them as they are, so say
    which ones are running rather than that they're off."""
    lines = []
    if skipped:
        running = [r["name"] for r in rows if r["loaded"]]
        lines.append("Background jobs left as they are: %s running." % ", ".join(running) if running
                     else "No background jobs are running. The free one: cos daemon install pulse")
    optin = [r["name"] for r in rows if r["llm"] and not r["loaded"]]
    if optin:
        lines.append("LLM daemons are opt-in (they use your Claude plan): cos daemon install %s" % " ".join(optin))
    return lines


def uninstall(args):
    from . import daemon
    kept = [name for name in daemon.definitions() if not daemon.uninstall(name).ok]
    if kept:
        print("Left on: %s (they run from another Claude OS on this Mac)." % ", ".join(kept))
    if _ours(LINK):
        os.remove(LINK)
    skills = unlink_skills()
    core.run(["git", "config", "--unset", "core.hooksPath"], cwd=str(core.ROOT))
    print("Removed its daemons, the `cos` link%s and the git hook. Your private data is still in %s."
          % (", %d skill link%s" % (skills, "" if skills == 1 else "s") if skills else "", _tilde(core.home())))
    return 0


def doctor(args):
    from . import daemon
    checks = []

    def check(ok, label, fix=""):
        checks.append((ok, label, fix))

    check(sys.version_info >= (3, 9), "python %s" % sys.version.split()[0], "needs Python 3.9+")
    check(bool(core.which("claude")), "claude on PATH", "install Claude Code: https://claude.com/claude-code")
    check(_ours(LINK), "`cos` command installed", "run: bin/cos install")
    linked = [n for n in EVERYWHERE if _our_skill(os.path.join(skills_dir(), n), n)]
    check(len(linked) == len(EVERYWHERE), "skills that work from any folder: %s" % (", ".join("/" + n for n in linked) or "none"),
          "run: bin/cos install (or skip it: bin/cos install --no-skills)")
    hooks = core.run(["git", "config", "core.hooksPath"], cwd=str(core.ROOT)).out
    check(hooks == "githooks", "Guardian pre-commit hook", "run: git config core.hooksPath githooks")
    mode = oct(os.stat(str(core.home())).st_mode & 0o777)
    check(mode == "0o700", "private home %s is %s" % (_tilde(core.home()), mode), "chmod 700 ~/.claude-os")
    check(bool(core.which("brew")), "Homebrew", "https://brew.sh")
    check(bool(core.which("mas")), "mas (App Store updates)", "brew install mas")
    fda = core.run(["ls", os.path.expanduser("~/.Trash")], timeout=5).ok
    check(fda, "Full Disk Access for your terminal", "optional: lets `cos clean` size the Trash. System Settings › Privacy & Security › Full Disk Access")
    if core.app_running("Music"):
        r = core.osascript('tell application "Music" to get player state', timeout=5)
        check(r.ok, "Automation access to Music", "System Settings › Privacy & Security › Automation › allow your terminal to control Music")
    loaded = [d["name"] for d in daemon.status() if d["loaded"]]
    check("pulse" in loaded, "daemons running: %s" % (", ".join(loaded) or "none"), "cos daemon install pulse")
    from . import guard
    problems = guard.scan(guard.publishable(), lambda p: _read(core.ROOT / p))
    check(not problems, "repository holds no private data", "run: cos guard --all")
    for ok, label, fix in checks:
        print("%s %s%s" % ("✓" if ok else "·", label, "" if ok else "  → " + fix))
    return 0


def _read(path):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return ""
