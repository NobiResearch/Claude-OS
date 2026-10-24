"""cos evolve — the self-improvement loop's plumbing.

The nightly evolve daemon works in its own local clone under ~/.claude-os/worktrees, on a
branch named evolve/<date>. A clone (not a git worktree) keeps every write, commits
included, inside the run's sandbox. Afterwards the branch is fetched into this repository,
where you (or Claude, with your OK) review and merge it with `cos evolve review|merge|discard`.
Your checkout is never touched, and the daemon never pushes.

`main` is protected (pull requests with passing CI only), so merging pushes the branch,
opens a pull request, waits for CI and squash-merges it. Repositories without a GitHub
remote fall back to a local fast-forward.
"""

import datetime as dt
import os
import re
import shutil

from . import core

STATE = "evolve.json"  # branch -> workspace path


def git(*args, cwd=None, timeout=60):
    return core.run(["git"] + list(args), cwd=str(cwd or core.ROOT), timeout=timeout)


def main_branch():
    r = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if r.ok and "/" in r.out:
        return r.out.split("/", 1)[1]
    return "main"


def _workspaces():
    return core.load_json(core.home("state", STATE), {}) or {}


def _remember(branch, path):
    ws = _workspaces()
    if path:
        ws[branch] = path
    else:
        ws.pop(branch, None)
    core.save_json(core.home("state", STATE), ws)


def new_workspace():
    """A fresh clone of main on a new evolve/<date> branch."""
    base = main_branch()
    day = dt.date.today().isoformat()
    branch, n = "evolve/%s" % day, 1
    while git("rev-parse", "--verify", "--quiet", branch).ok:
        n += 1
        branch = "evolve/%s-%d" % (day, n)
    path = core.home("worktrees", branch.replace("/", "-"))
    if os.path.exists(str(path)):
        shutil.rmtree(str(path), ignore_errors=True)
    r = git("clone", "--quiet", "--local", "--branch", base, str(core.ROOT), str(path), timeout=180)
    if not r.ok:
        raise RuntimeError("git clone failed: %s" % r.err)
    for args in (("checkout", "-q", "-b", branch), ("config", "core.hooksPath", "githooks")):
        r = git(*args, cwd=path)
        if not r.ok:
            raise RuntimeError("preparing the evolve workspace failed: %s" % r.err)
    _remember(branch, str(path))
    return {"branch": branch, "path": str(path), "base": base}


def ahead(branch, base=None, cwd=None):
    base = base or main_branch()
    r = git("log", "--oneline", "%s..%s" % (base, branch), cwd=cwd)
    return [l for l in r.out.splitlines() if l.strip()]


def addressed_frictions(branch, base=None):
    """Friction ids named in commit messages ("Addresses friction #3")."""
    body = git("log", "--format=%B", "%s..%s" % (base or main_branch(), branch)).out
    return sorted({int(n) for n in re.findall(r"friction #(\d+)", body, re.I)})


def run_tests(path):
    """The branch's tests were written by a model: run them sandboxed."""
    return core.run_sandboxed(["python3", "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=path)


def guard_branch(branch, base=None):
    """Run the Guardian over every file the branch changes, as the branch has it."""
    from . import guard
    names = git("diff", "--name-only", "-z", "--diff-filter=d", "%s...%s" % (base or main_branch(), branch)).out
    paths = [p for p in names.split("\0") if p]
    return guard.scan(paths, lambda p: git("show", "%s:%s" % (branch, p)).out)


def after_run(ws, summary):
    commits = ahead(ws["branch"], ws["base"], cwd=ws["path"])
    if not commits:
        _discard_workspace(ws["branch"])
        return "evolve: no change tonight (%s)" % summary
    r = git("fetch", "--quiet", ws["path"], "%s:%s" % (ws["branch"], ws["branch"]))
    if not r.ok:
        return "evolve: committed on %s but couldn't bring it back: %s" % (ws["branch"], r.err[:200])
    t = run_tests(ws["path"])
    verdict = "tests pass" if t.ok else "TESTS FAIL"
    core.journal("evolve", "%s: %d commit(s), %s" % (ws["branch"], len(commits), verdict),
                 branch=ws["branch"], commits=commits, tests_ok=t.ok)
    return "evolved: %s (%s) · review: cos evolve review %s" % (commits[0].split(" ", 1)[-1], verdict, ws["branch"])


def branches():
    r = git("branch", "--list", "evolve/*", "--format=%(refname:short)")
    return [b for b in r.out.splitlines() if b.strip()]


def workspace_path(branch):
    path = _workspaces().get(branch)
    return path if path and os.path.isdir(path) else None


def _check_branch(branch):
    if not re.match(r"^evolve/[\w.-]+$", branch or ""):
        core.die("only evolve/* branches can be merged or discarded, not %r" % branch)


def _discard_workspace(branch):
    path = _workspaces().get(branch)
    if path:
        root = os.path.realpath(str(core.home("worktrees")))
        real = os.path.realpath(path)
        if not real.startswith(root + os.sep):
            core.die("refusing to remove %s: not an evolve workspace" % path)
        shutil.rmtree(real, ignore_errors=True)
    _remember(branch, None)


def remove(branch):
    """Delete an evolve branch and its workspace. Never anything else."""
    _check_branch(branch)
    _discard_workspace(branch)
    git("branch", "-D", branch)


def _github():
    return git("remote", "get-url", "origin").ok and bool(core.which("gh"))


def _gh(*args, timeout=120):
    return core.run(["gh"] + list(args), cwd=str(core.ROOT), timeout=timeout)


def merge_via_pr(branch, commits):
    """Push, open a pull request, wait for CI, squash-merge: what the ruleset on main asks."""
    r = git("push", "--quiet", "-u", "origin", branch, timeout=180)
    if not r.ok:
        core.die("push failed: %s" % r.err[:300])
    title = commits[0].split(" ", 1)[-1] if commits else branch
    body = ("A change from Claude OS's nightly evolve loop (`%s`).\n\n%s\n\nThe Guardian and the tests "
            "passed locally before this pull request was opened.\n\n🤖 Generated with "
            "[Claude Code](https://claude.com/claude-code)") % (branch, "\n".join("- " + c for c in commits))
    r = _gh("pr", "create", "--base", main_branch(), "--head", branch, "--title", title, "--body", body)
    if not r.ok and "already exists" not in r.err:
        core.die("couldn't open a pull request: %s" % r.err[:300])
    print("opened %s" % (r.out.strip() or "the pull request"))
    r = _gh("pr", "checks", branch, "--watch", "--interval", "15", timeout=1800)
    if not r.ok:
        core.die("CI didn't pass; the pull request stays open for a look:\n%s" % (r.out or r.err)[-1500:])
    r = _gh("pr", "merge", branch, "--squash", "--delete-branch", timeout=180)
    if not r.ok:
        core.die("merge failed: %s" % r.err[:300])
    if git("rev-parse", "--abbrev-ref", "HEAD").out == main_branch() and not git("status", "--porcelain").out:
        git("pull", "--quiet", "--ff-only", "origin", main_branch(), timeout=180)


def main(args):
    c = args.evolve_cmd or "status"
    if c == "status":
        rows = [{"branch": b, "commits": ahead(b)} for b in branches()]
        if args.json:
            core.emit(rows, True, None)
            return 0
        if not rows:
            print("No evolve branches waiting. (The nightly evolve daemon creates them: cos daemon install evolve)")
        for r in rows:
            print("%s  (%d commit%s)" % (r["branch"], len(r["commits"]), "" if len(r["commits"]) == 1 else "s"))
            for c_ in r["commits"][:5]:
                print("    %s" % c_)
        return 0
    if c == "review":
        base = main_branch()
        print(git("log", "--stat", "%s..%s" % (base, args.branch)).out)
        print(git("diff", "%s...%s" % (base, args.branch)).out[:20000])
        return 0
    if c == "merge":
        _check_branch(args.branch)
        github = _github()
        if not args.yes:
            how = "push it, open a pull request, wait for CI and squash-merge" if github else "fast-forward %s" % main_branch()
            print("Would check %s with the Guardian and its tests, then %s. Add --yes." % (args.branch, how))
            return 2
        problems = guard_branch(args.branch)
        if problems:
            for path, why in problems:
                print("  guard: %s: %s" % (path, why))
            core.die("the Guardian blocks this branch (it would publish private data)")
        path = workspace_path(args.branch)
        t = run_tests(path) if path else None
        if t is not None and not t.ok:
            print((t.err or t.out)[-2000:])
            core.die("the branch's tests fail; not merging")
        fixed = addressed_frictions(args.branch)
        commits = ahead(args.branch)
        if github:
            merge_via_pr(args.branch, commits)
        else:
            if git("rev-parse", "--abbrev-ref", "HEAD").out != main_branch():
                core.die("check out %s first" % main_branch())
            if git("status", "--porcelain").out:
                core.die("your checkout has uncommitted changes; commit or stash first")
            r = git("merge", "--ff-only", args.branch)
            if not r.ok:
                core.die("fast-forward failed (rebase the branch first): %s" % r.err)
        remove(args.branch)
        from . import mem
        for fid in fixed:
            mem.close_friction(fid, note="merged %s" % args.branch)
        core.journal("action", "evolve merged %s" % args.branch, branch=args.branch, closed=fixed)
        print("merged %s%s" % (args.branch, " (closed friction %s)" % ", ".join("#%d" % f for f in fixed) if fixed else ""))
        return 0
    if c == "discard":
        _check_branch(args.branch)
        if not args.yes:
            print("Would delete %s and its workspace. Add --yes." % args.branch)
            return 2
        remove(args.branch)
        core.journal("action", "evolve discarded %s" % args.branch, branch=args.branch)
        print("discarded %s" % args.branch)
        return 0
    core.die("unknown evolve command %r" % c)
