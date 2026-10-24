"""The `cos` command: syscalls for humans and for Claude."""

import argparse
import os
import subprocess
import sys

from . import __version__, core

COMMANDS = {
    "ask", "status", "clean", "update", "music", "feeds", "log", "friction", "remember", "memory",
    "notify", "say", "brief", "daemon", "evolve", "guard", "boot", "statusline", "install",
    "uninstall", "doctor", "version", "config",
}

INTRO = """\
◆ Claude OS %s — a Claude-native layer for your Mac

  cos                       boot into Claude OS (Claude Code, in this repo)
  cos <anything else>       boot and ask, e.g.  cos find me a chill song
  cos ask "question"        one-shot answer, no session

syscalls (what Claude uses; you can too):
  status                    vitals and signals
  clean [--deep]            reclaimable space · clean apply <id>... --yes
  update [--fetch]          what's outdated · update apply <source> --yes
  music ...                 now | play <q> | pause | next | find | catalog | playlists | playlist <name> | like
  feeds                     unread headlines · feeds list | add <url> | mute <url> | mark-read
  log · friction · remember · memory        the OS's memory
  notify "msg" · say "text" · brief         talk back
  daemon list|install|run   background jobs (pulse, morning, evolve, board)
  evolve                    review what Claude OS changed about itself
  guard · doctor · install · uninstall · config
""" % __version__


def build_parser():
    p = argparse.ArgumentParser(prog="cos", description="Claude OS syscalls", add_help=True)
    p.add_argument("--version", action="version", version="Claude OS " + __version__)
    sub = p.add_subparsers(dest="cmd")

    def cmd(name, help_text, json_flag=True):
        # --json is accepted anywhere on the line; main() strips it before parsing.
        return sub.add_parser(name, help=help_text)

    a = cmd("ask", "one-shot question to Claude", json_flag=False)
    a.add_argument("question", nargs="+")

    cmd("status", "vitals and signals")

    c = cmd("clean", "reclaimable disk space")
    c.add_argument("--deep", action="store_true", help="also find stale node_modules and huge files")
    csub = c.add_subparsers(dest="clean_cmd")
    ca = csub.add_parser("apply", help="reclaim the named targets")
    ca.add_argument("ids", nargs="+")
    ca.add_argument("--yes", action="store_true")
    csub.add_parser("scan")

    u = cmd("update", "outdated software")
    u.add_argument("--fetch", action="store_true", help="refresh Homebrew metadata first")
    usub = u.add_subparsers(dest="update_cmd")
    ua = usub.add_parser("apply")
    ua.add_argument("source", choices=["brew", "npm", "mas", "rustup", "macos"])
    ua.add_argument("names", nargs="*")
    ua.add_argument("--yes", action="store_true")
    usub.add_parser("check")

    m = cmd("music", "Apple Music")
    msub = m.add_subparsers(dest="music_cmd")
    msub.add_parser("now")
    mp = msub.add_parser("play")
    mp.add_argument("query", nargs="*")
    mp.add_argument("--source", choices=["auto", "library", "catalog"], default="auto")
    mp.add_argument("--pick", type=int, default=0, help="play the Nth result instead of the best")
    for t in ("pause", "resume", "toggle", "next", "prev", "stop", "like"):
        msub.add_parser(t)
    mv = msub.add_parser("vol")
    mv.add_argument("level", type=int, nargs="?")
    mf = msub.add_parser("find")
    mf.add_argument("query", nargs="+")
    mc = msub.add_parser("catalog")
    mc.add_argument("query", nargs="+")
    mc.add_argument("--limit", type=int, default=10)
    msub.add_parser("playlists")
    ml = msub.add_parser("playlist")
    ml.add_argument("name", nargs="+")
    ml.add_argument("--shuffle", action="store_true")
    ms = msub.add_parser("shuffle")
    ms.add_argument("state", choices=["on", "off"])
    mh = msub.add_parser("history")
    mh.add_argument("--days", type=int, default=30)

    f = cmd("feeds", "RSS/Atom headlines")
    f.add_argument("--all", action="store_true", help="include already-read items")
    f.add_argument("--refresh", action="store_true")
    f.add_argument("--since", type=float, help="only items from the last N hours")
    f.add_argument("--category")
    f.add_argument("--limit", type=int, default=30)
    f.add_argument("--mark-read", action="store_true", help="mark what's shown as read")
    fsub = f.add_subparsers(dest="feeds_cmd")
    fsub.add_parser("list")
    fa = fsub.add_parser("add")
    fa.add_argument("url")
    fa.add_argument("--name")
    fm = fsub.add_parser("mute")
    fm.add_argument("url")
    fsub.add_parser("mark-read")

    lg = cmd("log", "the journal")
    lg.add_argument("--days", type=int, default=7)
    lg.add_argument("--kind")
    lg.add_argument("--limit", type=int, default=50)
    lsub = lg.add_subparsers(dest="log_cmd")
    la = lsub.add_parser("add")
    la.add_argument("text", nargs="+")
    la.add_argument("--kind", default="note")

    fr = cmd("friction", "things that went wrong (fuel for evolve)")
    fr.add_argument("--all", action="store_true")
    frsub = fr.add_subparsers(dest="friction_cmd")
    fra = frsub.add_parser("add")
    fra.add_argument("text", nargs="+")
    fra.add_argument("--area")
    frc = frsub.add_parser("close")
    frc.add_argument("id", type=int)
    frc.add_argument("--note")

    r = cmd("remember", "store a fact about your human", json_flag=False)
    r.add_argument("fact", nargs="+")
    mm = cmd("memory", "what Claude OS knows about you", json_flag=False)
    mm.add_argument("--forget", metavar="TEXT")

    n = cmd("notify", "macOS notification", json_flag=False)
    n.add_argument("message", nargs="+")
    n.add_argument("--title", default="Claude OS")
    n.add_argument("--sound")
    s = cmd("say", "speak out loud", json_flag=False)
    s.add_argument("text", nargs="+")
    cmd("brief", "show the latest morning brief", json_flag=False)

    d = cmd("daemon", "background jobs")
    dsub = d.add_subparsers(dest="daemon_cmd")
    dsub.add_parser("list")
    for verb in ("install", "uninstall"):
        dv = dsub.add_parser(verb)
        dv.add_argument("names", nargs="*")
        dv.add_argument("--all", action="store_true")
    dr = dsub.add_parser("run")
    dr.add_argument("name")
    dl = dsub.add_parser("logs")
    dl.add_argument("name")

    e = cmd("evolve", "self-improvement branches")
    esub = e.add_subparsers(dest="evolve_cmd")
    esub.add_parser("status")
    for verb in ("review", "merge", "discard"):
        ev = esub.add_parser(verb)
        ev.add_argument("branch")
        if verb != "review":
            ev.add_argument("--yes", action="store_true")

    g = cmd("guard", "block private data from the public repo", json_flag=False)
    g.add_argument("--all", action="store_true", help="scan every tracked file, not just staged ones")
    g.add_argument("--quiet", action="store_true")

    cmd("boot", "session banner (SessionStart hook)", json_flag=False)
    cmd("statusline", "one-line status for Claude Code", json_flag=False)
    i = cmd("install", "set up Claude OS on this Mac", json_flag=False)
    i.add_argument("--no-daemons", action="store_true")
    cmd("uninstall", "remove daemons, link and hook", json_flag=False)
    cmd("doctor", "check that everything is wired up", json_flag=False)
    cmd("version", "print version", json_flag=False)
    cf = cmd("config", "get or set preferences", json_flag=False)
    cf.add_argument("key", nargs="?")
    cf.add_argument("value", nargs="?")
    return p


def launch_claude(prompt=None):
    if not core.which("claude"):
        core.die("Claude Code isn't installed: https://claude.com/claude-code")
    os.chdir(str(core.ROOT))
    argv = ["claude"] + ([prompt] if prompt else [])
    os.execvp("claude", argv)


def ask(question):
    if not core.which("claude"):
        core.die("Claude Code isn't installed")
    core.journal("ask", question)
    return subprocess.call(["claude", "-p", question], cwd=str(core.ROOT))


def say(text):
    return core.run(["say", text], timeout=120).rc


def brief():
    runs = sorted(core.home("runs", "morning").glob("*.md"))
    if not runs:
        print("No brief yet. Ask for one with `cos ask /brief`, or schedule it: cos daemon install morning")
        return 0
    print(runs[-1].read_text())
    return 0


def config_cmd(args):
    import json
    if args.key is None:
        print(json.dumps(core.config(), indent=2))
        return 0
    if args.value is None:
        node = core.config()
        for k in args.key.split("."):
            node = node.get(k) if isinstance(node, dict) else None
        print(json.dumps(node))
        return 0
    try:
        value = json.loads(args.value)
    except ValueError:
        value = args.value
    core.config_set(args.key, value)
    print("%s = %s" % (args.key, json.dumps(value)))
    return 0


# Commands that change the machine or the repository. Two rules, enforced here rather
# than in permission patterns (which a reordered flag could slip past):
#  * they must be written canonically (`cos clean apply …`, flags after) so Claude Code's
#    `ask` rules always match them;
#  * they never run inside a headless daemon session.
MUTATING = {("clean", "apply"), ("update", "apply"), ("daemon", "install"), ("daemon", "uninstall"),
            ("daemon", "run"), ("evolve", "merge"), ("evolve", "discard"), ("install",), ("uninstall",)}


def mutation(args):
    sub = {"clean": "clean_cmd", "update": "update_cmd", "daemon": "daemon_cmd", "evolve": "evolve_cmd"}
    key = (args.cmd, getattr(args, sub[args.cmd], None)) if args.cmd in sub else (args.cmd,)
    return key if key in MUTATING else None


def check_mutation(key, argv):
    if os.environ.get("CLAUDE_OS_DAEMON") and key != ("daemon", "run"):
        core.die("`cos %s` is not allowed in a headless daemon run; a human must do this." % " ".join(key), 3)
    if key == ("daemon", "run") and os.environ.get("CLAUDE_OS_DAEMON"):
        core.die("daemons can't start other daemons", 3)
    if tuple(argv[:len(key)]) != key:
        core.die("write it as `cos %s …` with options after, so permission rules can see it." % " ".join(key), 2)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        if sys.stdin.isatty() and sys.stdout.isatty():
            launch_claude()
        print(INTRO)
        return 0
    if argv[0] in ("-h", "--help", "help"):
        print(INTRO)
        return 0
    if argv[0] not in COMMANDS and not argv[0].startswith("-"):
        # Free text means "boot and ask", but only for a person at a terminal: a script or
        # a model typo must never spin up a Claude session.
        if sys.stdin.isatty() and sys.stdout.isatty():
            launch_claude(" ".join(argv))
        core.die("unknown command %r (see `cos help`; free-text questions need a terminal, or use `cos ask`)" % argv[0], 2)
    as_json = "--json" in argv
    args = build_parser().parse_args([a for a in argv if a != "--json"])
    args.json = as_json
    key = mutation(args)
    if key:
        check_mutation(key, argv)
    c = args.cmd
    if c == "ask":
        return ask(" ".join(args.question))
    if c == "status":
        from . import status
        return status.main(args)
    if c == "clean":
        from . import clean
        return clean.main(args)
    if c == "update":
        from . import updates
        return updates.main(args)
    if c == "music":
        from . import music
        return music.main(args)
    if c == "feeds":
        from . import feeds
        return feeds.main(args)
    if c in ("log", "friction", "remember", "memory"):
        from . import mem
        return getattr(mem, c + "_main" if c != "log" else "log_main")(args)
    if c == "notify":
        r = core.notify(" ".join(args.message), title=args.title, sound=args.sound)
        return 0 if r.ok else 1
    if c == "say":
        return say(" ".join(args.text))
    if c == "brief":
        return brief()
    if c == "daemon":
        from . import daemon
        return daemon.main(args)
    if c == "evolve":
        from . import evolve
        return evolve.main(args)
    if c == "guard":
        from . import guard
        return guard.main(args)
    if c in ("boot", "statusline"):
        from . import shell
        return getattr(shell, c)()
    if c in ("install", "uninstall", "doctor"):
        from . import system
        return getattr(system, c)(args)
    if c == "version":
        print("Claude OS %s" % __version__)
        return 0
    if c == "config":
        return config_cmd(args)
    print(INTRO)
    return 0
