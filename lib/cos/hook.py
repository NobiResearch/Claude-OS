"""cos hook permission — answer Claude Code's push and merge prompts for the night shift (0006).

Claude Code runs this as a PermissionRequest hook, just before it would ask the human. While
the human has "Night shift" on in Settings, it approves two things and nothing else:

- **Pushing** `git push [-q] -u origin night/<name>` from a checkout of this repository, to
  the remote it was cloned from, after the Guardian has checked every commit and message it
  would publish. A pushed branch runs nothing that matters, so it may change anything except
  `.github/` (CI runs a branch's workflow the moment it's pushed).
- **Merging** `gh pr merge <N> --squash --delete-branch --match-head-commit <sha>`: a green,
  open `night/*` pull request of this repository, pinned to the commit checked here, that
  leaves Claude OS's safety files alone. A merge is where code starts to run, so a pull
  request that touches the gate waits for the human's merge.

It also lets read-only `gh api <path>` calls through, which the merge rules otherwise ask
about. Anything else, any doubt, any error: it prints nothing and the human's normal prompt
appears. This is a tripwire against drift and mistakes, not a wall: Claude works with the
human's own GitHub login, and decision 0006 lists the spellings these rules don't catch.

`cos hook check <branch|PR>` answers the same question without acting, so a night shift
leaves work for the morning instead of stalling on a prompt nobody will answer. With no
argument it lists the night's pull requests that wait for the human.
"""

import json
import os
import re
import sys

from . import core

ALLOW = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
COMMAND = re.compile(r"[A-Za-z0-9._/ -]+")  # no quotes, $, ;, &, |, <, >, globs, :, +, @, ~ or newlines
BRANCH = re.compile(r"night/[A-Za-z0-9._-]+")
SHA = re.compile(r"[0-9a-f]{40}")
GITHUB = re.compile(r"(?:https://github\.com/|git@github\.com:)([\w.-]+)/([\w.-]+?)(?:\.git)?$")
# A night shift can't widen its own powers: merging changes here waits for the human. That
# includes the code this hook leans on (core, cli, evolve's guard_branch), the server that
# flips the switch and the app's Allow/Deny path, so one night's merge can't loosen the next.
PROTECTED = (".claude/", ".github/", "githooks/", "bin/", "CLAUDE.md", "etc/daemons.json",
             "lib/cos/guard.py", "lib/cos/hook.py", "lib/cos/daemon.py",
             "lib/cos/core.py", "lib/cos/cli.py", "lib/cos/evolve.py", "lib/cos/server.py",
             "lib/cos/__init__.py", "lib/cos/chat.py")
NEVER_PUSHED = (".github/",)  # CI runs it on push: a workflow could merge pull requests itself
GREEN = ("SUCCESS", "SKIPPED", "NEUTRAL")


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


# ---------------------------------------------------------------- the commands

def _words(command):
    if not isinstance(command, str) or not COMMAND.fullmatch(command):
        return None
    return command.split()


def parse_push(command):
    """The one command the night shift may push with -> its branch, or None."""
    words = _words(command)
    if not words or words[:2] != ["git", "push"]:
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


def parse_merge(command):
    """The one command the night shift may merge with -> (PR number, the commit it checked),
    or None. Pinning the commit means GitHub merges exactly what was checked here."""
    words = _words(command)
    if not words or len(words) != 8 or words[:3] != ["gh", "pr", "merge"]:
        return None
    if words[4:7] != ["--squash", "--delete-branch", "--match-head-commit"]:
        return None
    if not words[3].isdigit() or not SHA.fullmatch(words[7]):
        return None
    return int(words[3]), words[7]


def parse_api_read(command):
    """A read-only `gh api [--paginate] <path>`: no method, no fields, no input, no GraphQL."""
    words = _words(command)
    if not words or words[:2] != ["gh", "api"]:
        return False
    rest = [w for w in words[2:] if w != "--paginate"]
    return len(rest) == 1 and not rest[0].startswith("-") and "graphql" not in rest[0] and ".." not in rest[0]


# ---------------------------------------------------------------- what's true

def _repo(git):
    from . import evolve
    top = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    ours = core.run(["git", "-C", str(core.ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"], timeout=30)
    base = "origin/" + evolve.main_branch()
    return base, {
        "same_repo": top.ok and ours.ok and top.out == ours.out,
        "clean_main": clean_main(base),
        "main": evolve.main_branch(),
        "url": git("remote", "get-url", "origin").out,
        "push_url": git("remote", "get-url", "--push", "origin").out,
    }


def inspect(branch, cwd):
    """What a push decision needs to know, read with main's own code."""
    from . import evolve
    def git(*args):
        return core.run(["git", "-C", cwd] + list(args), timeout=30)
    base, facts = _repo(git)
    head = git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch).out
    facts.update(head=head, paths=changed(git, base, branch) if head else [],
                 problems=evolve.guard_branch(branch, base=base) if head else [])
    return facts


def inspect_pr(number, sha, cwd):
    """What a merge decision needs to know: one `gh pr view` for the pull request's state and
    checks, and everything about its code from local git (GitHub's file list stops at 100)."""
    from . import evolve, guard
    def git(*args):
        return core.run(["git", "-C", cwd] + list(args), timeout=20)
    base, facts = _repo(git)
    view = core.run(["gh", "pr", "view", str(number), "--json",
                     "number,state,isDraft,isCrossRepository,headRefName,headRefOid,baseRefName,url,title,statusCheckRollup"],
                    cwd=cwd, timeout=15)
    try:
        pr = json.loads(view.out) if view.ok else None
    except ValueError:
        pr = None
    facts["pr"] = pr if isinstance(pr, dict) else None
    if facts["pr"] and BRANCH.fullmatch(str(pr.get("headRefName"))) and git("cat-file", "-e", sha + "^{commit}").ok:
        facts["local"] = git("rev-parse", "--verify", "--quiet", "refs/heads/" + pr["headRefName"]).out
        facts["paths"] = changed(git, base, sha)
        facts["problems"] = evolve.guard_branch(sha, base=base)
        patterns = guard.SECRET_PATTERNS + guard.personal_patterns()
        facts["problems"] += [("title", why) for _, why in guard.check_text("title", str(pr.get("title") or ""), patterns)]
    return facts


# ---------------------------------------------------------------- deciding

def _common(facts):
    if not facts.get("same_repo"):
        return "not a checkout of Claude OS"
    if not facts.get("clean_main"):
        return "the hook isn't running from a clean main"
    url = facts.get("url") or ""
    if not url or facts.get("push_url") != url or not GITHUB.match(url):
        return "origin isn't a plain GitHub remote"
    return None


def checks_green(rollup):
    """Every check finished and passed, and `test` (what the ruleset requires) is among them."""
    runs = rollup if isinstance(rollup, list) else []
    def outcome(c):
        return c.get("conclusion") if c.get("__typename", "CheckRun") == "CheckRun" else c.get("state")
    def name(c):
        return c.get("name") or c.get("context")
    if not runs or any(outcome(c) not in GREEN for c in runs):
        return False
    return any(name(c) == "test" and outcome(c) == "SUCCESS" for c in runs)


def decide_push(branch, facts):
    why = _common(facts)
    if why:
        return False, why
    if not facts.get("head"):
        return False, "no local branch %s" % branch
    if facts.get("paths") is None:
        return False, "couldn't list what the branch changes"
    ci = [p for p in facts["paths"] if p.startswith(NEVER_PUSHED)]
    if ci:
        return False, "changes CI (%s): that stays local for the human" % ", ".join(ci[:3])
    if facts.get("problems"):
        return False, "the Guardian found %d problem(s)" % len(facts["problems"])
    return True, "%s at %s" % (branch, facts["head"][:8])


def decide_merge(number, sha, facts):
    why = _common(facts)
    if why:
        return False, why
    pr = facts.get("pr")
    if not pr:
        return False, "couldn't read pull request #%d" % number
    owner_repo = GITHUB.match(facts["url"]).groups()
    if str(pr.get("url", "")).lower() != ("https://github.com/%s/%s/pull/%d" % (owner_repo + (number,))).lower():
        return False, "#%d isn't a pull request of this repository" % number
    if pr.get("state") != "OPEN" or pr.get("isDraft") or pr.get("isCrossRepository"):
        return False, "#%d isn't an open, ready pull request from this repository" % number
    head = str(pr.get("headRefName"))
    if not BRANCH.fullmatch(head) or pr.get("baseRefName") != facts.get("main"):
        return False, "#%d isn't a night/* branch into %s" % (number, facts.get("main"))
    if not (pr.get("headRefOid") == sha == facts.get("local")):
        return False, "#%d's head isn't the commit that was checked" % number
    if not checks_green(pr.get("statusCheckRollup")):
        return False, "#%d's checks aren't all green yet" % number
    if facts.get("paths") is None:
        return False, "couldn't list what #%d changes" % number
    touched = [p for p in facts["paths"] if protected(p)]
    if touched:
        return False, "changes Claude OS's safety files (%s): that waits for the human's merge" % ", ".join(touched[:3])
    if facts.get("problems"):
        return False, "the Guardian found %d problem(s)" % len(facts["problems"])
    return True, "merged #%d (%s at %s)" % (number, head, sha[:8])


def decide(request, cfg, look=inspect, look_pr=inspect_pr):
    """-> (approve, why). Pure apart from `look` and `look_pr`, which read the repository."""
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return False, "inside a background job"
    if request.get("tool_name") != "Bash":
        return False, "not a shell command"
    command = (request.get("tool_input") or {}).get("command")
    if parse_api_read(command):
        return True, "a read-only gh api call"
    if not (cfg.get("autonomy") or {}).get("night_shift"):
        return False, "night shift is off"
    cwd = request.get("cwd") or str(core.ROOT)
    branch = parse_push(command)
    if branch:
        return decide_push(branch, look(branch, cwd))
    merge = parse_merge(command)
    if merge:
        return decide_merge(merge[0], merge[1], look_pr(merge[0], merge[1], cwd))
    return False, "not the exact push or merge the night shift may use"


def permission():
    """The hook itself: read the request on stdin, print an approval or nothing. Never fails
    loudly: for a PermissionRequest hook, exit code 2 means deny."""
    try:
        request = json.loads(sys.stdin.read() or "{}")
        approve, why = decide(request, core.config())
        command = str((request.get("tool_input") or {}).get("command", ""))[:200]
        if approve and not why.startswith("a read-only"):
            core.journal("action", "night shift: " + (why if why.startswith("merged") else "pushed " + why), via="hook")
        elif not approve and command.startswith(("git push", "gh pr merge", "gh-axi pr merge")):
            core.journal("permission", "night shift: asked the human (%s): %s" % (why, command), via="hook")
        if approve:
            print(json.dumps(ALLOW))
    except BaseException:  # noqa: B036 — any doubt falls through to the human's prompt
        pass
    return 0


# ---------------------------------------------------------------- cos hook check

def merge_command(number, sha):
    return "gh pr merge %d --squash --delete-branch --match-head-commit %s" % (number, sha)


def check_pr(number, cwd=None):
    """Would the night shift merge #number on its own? -> (approve, why, the exact command)."""
    view = core.run(["gh", "pr", "view", str(number), "--json", "headRefOid"], cwd=cwd or os.getcwd(), timeout=15)
    try:
        sha = json.loads(view.out).get("headRefOid") if view.ok else None
    except (ValueError, AttributeError):
        sha = None
    if not sha or not SHA.fullmatch(sha):
        return False, "couldn't read pull request #%d" % number, None
    command = merge_command(number, sha)
    approve, why = decide({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or os.getcwd()}, core.config())
    return approve, why, command


def waiting(cwd=None):
    """The night shift's open pull requests and what each waits for, or None if GitHub
    couldn't be asked. Ones that touch the gate list exactly which safety files."""
    r = core.run(["gh", "pr", "list", "--state", "open", "--limit", "50", "--json", "number,title,headRefName,url"],
                 cwd=cwd or str(core.ROOT), timeout=20)
    try:
        prs = json.loads(r.out) if r.ok else None
    except ValueError:
        prs = None
    if not isinstance(prs, list):
        return None
    rows = []
    for pr in prs:
        if not BRANCH.fullmatch(str(pr.get("headRefName"))):
            continue
        approve, why, command = check_pr(pr["number"], cwd)
        rows.append({"number": pr["number"], "title": pr.get("title"), "branch": pr["headRefName"], "url": pr.get("url"),
                     "merges_on_its_own": approve, "why": why, "command": command})
    return rows


def render_waiting(rows):
    if rows is None:
        print("Couldn't ask GitHub about the night shift's pull requests.")
    elif not rows:
        print("No night shift pull requests are open.")
    for r in rows or []:
        print("#%d %s (%s)\n    %s\n    %s" % (r["number"], r["title"], r["branch"],
                                          "ready to merge on its own" if r["merges_on_its_own"] else "waits: " + r["why"], r["url"]))


def main(args):
    if args.hook_cmd == "permission":
        return permission()
    target = args.target
    if target is None:
        rows = waiting(os.getcwd())
        core.emit(rows, args.json, render_waiting)
        return 0 if rows is not None else 1
    if target.isdigit():
        approve, why, command = check_pr(int(target))
        core.emit({"pr": int(target), "approve": approve, "why": why, "command": command}, args.json,
                  lambda d: print(("✓ would merge on its own: " + d["command"]) if d["approve"] else "✗ would ask the human: " + d["why"]))
        return 0 if approve else 1
    approve, why = decide({"tool_name": "Bash", "tool_input": {"command": "git push -u origin %s" % target},
                           "cwd": os.getcwd()}, core.config())
    core.emit({"branch": target, "approve": approve, "why": why}, args.json,
              lambda d: print(("✓ would push on its own: " if d["approve"] else "✗ would ask the human: ") + d["why"]))
    return 0 if approve else 1
