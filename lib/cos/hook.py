"""cos hook permission — answer Claude Code's push prompt for the night shift (decision 0006).

Claude Code runs this as a PermissionRequest hook, just before it would ask the human. It
approves exactly one thing, and only while the human has turned on "Night shift" in
Settings: `git push [-q] -u origin night/<name>` from a checkout of this repository, to
the remote it was cloned from, after the Guardian has checked every commit and message it
would publish, and only if the branch leaves Claude OS's own safety files alone. Anything
else, any doubt, any error: it prints nothing and the human's normal prompt appears.

`cos hook check <branch>` answers the same question without pushing, so a night shift can
leave a branch for the morning instead of stalling on a prompt nobody will answer.
"""

import json
import os
import re
import sys

from . import core

ALLOW = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
COMMAND = re.compile(r"[A-Za-z0-9._/ -]+")  # no quotes, $, ;, &, |, <, >, globs, :, +, @, ~ or newlines
BRANCH = re.compile(r"night/[A-Za-z0-9._-]+")
# A night shift can't widen its own powers: changes here wait for the human. That includes
# the code this hook leans on (core, cli, evolve's guard_branch) and the server that flips
# the switch, so a branch merged one night can't loosen the next night's checks.
PROTECTED = (".claude/", ".github/", "githooks/", "bin/", "CLAUDE.md", "etc/daemons.json",
             "lib/cos/guard.py", "lib/cos/hook.py", "lib/cos/daemon.py",
             "lib/cos/core.py", "lib/cos/cli.py", "lib/cos/evolve.py", "lib/cos/server.py",
             "lib/cos/__init__.py", "lib/cos/chat.py")


def protected(path):
    """Is this path part of the gate? Also anything Python loads before Claude OS's own code:
    bin/cos puts lib/ first on sys.path, so a lib/json.py would stand in for the standard
    library's inside this very hook, and compiled .pyc files can skip their source."""
    if path in PROTECTED or path.startswith(PROTECTED):
        return True
    if path.startswith("lib/") and not path.startswith("lib/cos/"):
        return True
    return "__pycache__/" in path or path.endswith((".pyc", ".pth"))


def changed(git, base, branch):
    """Every path the branch touches, or None if git can't say. --no-renames: git lists a
    moved file under its new name only, so moving .claude/settings.json away would look
    like a new file in docs/."""
    r = git("diff", "--no-renames", "--name-only", "%s...%s" % (base, branch))
    return r.out.splitlines() if r.ok else None


def clean_main(base):
    """The hook runs from the live checkout, so that checkout must be main with nothing of
    the gate changed locally: no edits, no untracked files, no commits origin hasn't got."""
    from . import evolve
    root = str(core.ROOT)
    def git(*args):
        return core.run(["git", "-C", root] + list(args), timeout=10)
    if git("symbolic-ref", "--short", "HEAD").out != evolve.main_branch():
        return False
    status = git("status", "--porcelain", "--", "lib", "bin", ".claude", "CLAUDE.md", "etc", "githooks")
    local = git("diff", "--no-renames", "--name-only", base, "HEAD")
    return status.ok and not status.out.strip() and local.ok and not any(protected(p) for p in local.out.splitlines())


def parse_push(command):
    """The one command the night shift may push with -> its branch, or None."""
    if not isinstance(command, str) or not COMMAND.fullmatch(command):
        return None
    words = command.split()
    if words[:2] != ["git", "push"]:
        return None
    rest = words[2:]
    if rest[:1] in (["-q"], ["--quiet"]):
        rest = rest[1:]
    if len(rest) != 3 or rest[:2] != ["-u", "origin"]:
        return None
    branch = rest[2]
    if not BRANCH.fullmatch(branch) or ".." in branch or branch.endswith((".", ".lock", "main", "master")):
        return None
    return branch


def inspect(branch, cwd):
    """What the decision needs to know about the repository, read with main's own code."""
    from . import evolve, guard
    def git(*args):
        return core.run(["git", "-C", cwd] + list(args), timeout=30)
    top = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    ours = core.run(["git", "-C", str(core.ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"], timeout=30)
    base = "origin/" + evolve.main_branch()
    head = git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch).out
    return {
        "same_repo": top.ok and ours.ok and top.out == ours.out,
        "clean_main": clean_main(base),
        "head": head,
        "url": git("remote", "get-url", "origin").out,
        "push_url": git("remote", "get-url", "--push", "origin").out,
        "paths": changed(git, base, branch) if head else [],
        "problems": evolve.guard_branch(branch, base=base) if head else [],
        "guard_ok": guard is not None,
    }


def decide(request, cfg, look=inspect):
    """-> (approve, why). Pure apart from `look`, which reads the repository."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return False, "inside a background job"
    if not (cfg.get("autonomy") or {}).get("night_shift"):
        return False, "night shift is off"
    if request.get("tool_name") != "Bash":
        return False, "not a shell command"
    branch = parse_push((request.get("tool_input") or {}).get("command"))
    if not branch:
        return False, "not a plain `git push -u origin night/<name>`"
    facts = look(branch, request.get("cwd") or str(core.ROOT))
    if not facts.get("same_repo"):
        return False, "not a checkout of Claude OS"
    if not facts.get("clean_main"):
        return False, "the hook isn't running from a clean main"
    if not facts.get("head"):
        return False, "no local branch %s" % branch
    url = facts.get("url") or ""
    if not url or facts.get("push_url") != url or not re.match(r"(https://github\.com/|git@github\.com:)[\w.-]+/[\w.-]+$", url):
        return False, "origin isn't a plain GitHub remote"
    if facts.get("paths") is None:
        return False, "couldn't list what the branch changes"
    touched = [p for p in facts["paths"] if protected(p)]
    if touched:
        return False, "changes Claude OS's safety files (%s): that waits for the human" % ", ".join(touched[:3])
    if facts.get("problems"):
        return False, "the Guardian found %d problem(s)" % len(facts["problems"])
    return True, "%s at %s" % (branch, facts["head"][:8])


def permission():
    """The hook itself: read the request on stdin, print an approval or nothing. Never fails
    loudly: for a PermissionRequest hook, exit code 2 means deny."""
    try:
        request = json.loads(sys.stdin.read() or "{}")
        approve, why = decide(request, core.config())
        command = str((request.get("tool_input") or {}).get("command", ""))[:200]
        if command.startswith("git push") or approve:
            core.journal("action" if approve else "permission",
                         ("night shift: pushed " if approve else "night shift: asked the human (%s): " % why) + (why if approve else command),
                         via="hook")
        if approve:
            print(json.dumps(ALLOW))
    except BaseException:  # noqa: B036 — any doubt falls through to the human's prompt
        pass
    return 0


def main(args):
    if args.hook_cmd == "permission":
        return permission()
    branch = args.branch
    approve, why = decide({"tool_name": "Bash", "tool_input": {"command": "git push -u origin %s" % branch},
                           "cwd": os.getcwd()}, core.config())
    core.emit({"branch": branch, "approve": approve, "why": why}, args.json,
              lambda d: print(("✓ would push on its own: " if d["approve"] else "✗ would ask the human: ") + d["why"]))
    return 0 if approve else 1
