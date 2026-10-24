"""cos evolve — the self-improvement loop's plumbing.

The nightly evolve daemon works in a throwaway git worktree under
~/.claude-os/worktrees on a branch named evolve/<date>. Your checkout is never
touched and nothing is ever pushed. You (or Claude, with your OK) review and
merge with `cos evolve review|merge|discard`.
"""

import datetime as dt
import os
import re
import shutil

from . import core


def git(*args, cwd=None, timeout=60):
    return core.run(["git"] + list(args), cwd=str(cwd or core.ROOT), timeout=timeout)


def main_branch():
    r = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if r.ok and "/" in r.out:
        return r.out.split("/", 1)[1]
    return "main"


def new_worktree():
    base = main_branch()
    day = dt.date.today().isoformat()
    branch, n = "evolve/%s" % day, 1
    while git("rev-parse", "--verify", "--quiet", branch).ok:
        n += 1
        branch = "evolve/%s-%d" % (day, n)
    path = core.home("worktrees", branch.replace("/", "-"))
    r = git("worktree", "add", "-b", branch, str(path), base)
    if not r.ok:
        raise RuntimeError("git worktree add failed: %s" % r.err)
    return {"branch": branch, "path": str(path), "base": base}


def ahead(branch, base=None):
    base = base or main_branch()
    r = git("log", "--oneline", "%s..%s" % (base, branch))
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


def after_run(wt, summary):
    commits = ahead(wt["branch"], wt["base"])
    if not commits:
        remove(wt["branch"])
        return "evolve: no change tonight (%s)" % summary
    t = run_tests(wt["path"])
    verdict = "tests pass" if t.ok else "TESTS FAIL"
    core.journal("evolve", "%s: %d commit(s), %s" % (wt["branch"], len(commits), verdict),
                 branch=wt["branch"], commits=commits, tests_ok=t.ok)
    return "evolved: %s (%s) · review: cos evolve review %s" % (commits[0].split(" ", 1)[-1], verdict, wt["branch"])


def branches():
    r = git("branch", "--list", "evolve/*", "--format=%(refname:short)")
    return [b for b in r.out.splitlines() if b.strip()]


def worktree_path(branch):
    r = git("worktree", "list", "--porcelain")
    path = None
    for line in r.out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == "branch refs/heads/" + branch:
            return path
    return None


def _check_branch(branch):
    if not re.match(r"^evolve/[\w.-]+$", branch or ""):
        core.die("only evolve/* branches can be merged or discarded, not %r" % branch)


def remove(branch):
    """Delete an evolve branch and its worktree. Never anything else."""
    _check_branch(branch)
    path = worktree_path(branch)
    if path:
        root = os.path.realpath(str(core.home("worktrees")))
        real = os.path.realpath(path)
        if not real.startswith(root + os.sep):
            core.die("refusing to remove %s: not an evolve worktree" % path)
        git("worktree", "remove", "--force", real)
        if os.path.isdir(real):
            shutil.rmtree(real, ignore_errors=True)
        git("worktree", "prune")
    git("branch", "-D", branch)


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
        if not args.yes:
            print("Would fast-forward %s onto %s, then delete the branch. Add --yes." % (args.branch, main_branch()))
            return 2
        if git("rev-parse", "--abbrev-ref", "HEAD").out != main_branch():
            core.die("check out %s first" % main_branch())
        if git("status", "--porcelain").out:
            core.die("your checkout has uncommitted changes; commit or stash first")
        _check_branch(args.branch)
        problems = guard_branch(args.branch)
        if problems:
            for path, why in problems:
                print("  guard: %s: %s" % (path, why))
            core.die("the Guardian blocks this branch (it would publish private data)")
        path = worktree_path(args.branch)
        t = run_tests(path) if path else None
        if t is not None and not t.ok:
            print((t.err or t.out)[-2000:])
            core.die("the branch's tests fail; not merging")
        fixed = addressed_frictions(args.branch)
        r = git("merge", "--ff-only", args.branch)
        if not r.ok:
            core.die("fast-forward failed (rebase the branch first): %s" % r.err)
        remove(args.branch)
        from . import mem
        for fid in fixed:
            mem.close_friction(fid, note="merged %s" % args.branch)
        core.journal("action", "evolve merged %s" % args.branch, branch=args.branch, closed=fixed)
        print("merged %s%s. Push when you're happy: git push" % (
            args.branch, " (closed friction %s)" % ", ".join("#%d" % f for f in fixed) if fixed else ""))
        return 0
    if c == "discard":
        _check_branch(args.branch)
        if not args.yes:
            print("Would delete %s and its worktree. Add --yes." % args.branch)
            return 2
        remove(args.branch)
        core.journal("action", "evolve discarded %s" % args.branch, branch=args.branch)
        print("discarded %s" % args.branch)
        return 0
    core.die("unknown evolve command %r" % c)
