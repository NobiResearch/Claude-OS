"""cos install / uninstall / doctor — putting Claude OS on (and off) this Mac."""

import os
import sys

from . import __version__, core

BIN_DIR = os.path.expanduser("~/.local/bin")
LINK = os.path.join(BIN_DIR, "cos")


def _ours(path):
    return os.path.islink(path) and os.path.realpath(path) == os.path.realpath(str(core.ROOT / "bin" / "cos"))


def install(args):
    from . import daemon
    core.home()
    os.chmod(str(core.home()), 0o700)
    steps = []
    os.makedirs(BIN_DIR, exist_ok=True)
    if os.path.lexists(LINK) and not _ours(LINK):
        steps.append("✗ %s exists and isn't Claude OS; left it alone" % LINK)
    else:
        if os.path.lexists(LINK):
            os.remove(LINK)
        os.symlink(str(core.ROOT / "bin" / "cos"), LINK)
        steps.append("✓ `cos` linked into ~/.local/bin")
    if BIN_DIR not in os.environ.get("PATH", "").split(":"):
        steps.append("! ~/.local/bin isn't on your PATH; add it to ~/.zshrc")
    r = core.run(["git", "config", "core.hooksPath", "githooks"], cwd=str(core.ROOT))
    steps.append("✓ Guardian pre-commit hook enabled" if r.ok else "✗ couldn't set git hooks: %s" % r.err)
    if not args.no_daemons:
        daemon.install("pulse")
        steps.append("✓ pulse daemon running (every 2h, no LLM)")
    core.journal("action", "installed Claude OS %s" % __version__)
    print("\n".join(steps))
    print("\nNext: run `cos` to boot into Claude OS.")
    if args.no_daemons:
        print("Background jobs are off. The free one: cos daemon install pulse")
    print("LLM daemons are opt-in (they use your Claude plan): cos daemon install morning evolve board")
    return 0


def uninstall(args):
    from . import daemon
    for name in daemon.definitions():
        daemon.uninstall(name)
    if _ours(LINK):
        os.remove(LINK)
    core.run(["git", "config", "--unset", "core.hooksPath"], cwd=str(core.ROOT))
    print("Removed daemons, the `cos` link and the git hook. Your private data is still in %s." % core.home())
    return 0


def doctor(args):
    from . import daemon
    checks = []

    def check(ok, label, fix=""):
        checks.append((ok, label, fix))

    check(sys.version_info >= (3, 9), "python %s" % sys.version.split()[0], "needs Python 3.9+")
    check(bool(core.which("claude")), "claude on PATH", "install Claude Code: https://claude.com/claude-code")
    check(_ours(LINK), "`cos` command installed", "run: bin/cos install")
    hooks = core.run(["git", "config", "core.hooksPath"], cwd=str(core.ROOT)).out
    check(hooks == "githooks", "Guardian pre-commit hook", "run: git config core.hooksPath githooks")
    mode = oct(os.stat(str(core.home())).st_mode & 0o777)
    check(mode == "0o700", "private home %s is %s" % (core.home(), mode), "chmod 700 ~/.claude-os")
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
