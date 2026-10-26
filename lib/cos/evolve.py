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
import time

from . import core

STATE = "evolve.json"  # branch -> workspace path


def git(*args, cwd=None, timeout=60):
    return core.run(["git"] + list(args), cwd=str(cwd or core.ROOT), timeout=timeout)


def main_branch(cwd=None):
    r = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=cwd)
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


def guard_branch(branch, base=None, cwd=None):
    """Run the Guardian over every commit the branch would publish, one by one, and its
    message: a file added in one commit and deleted in the next is still pushed."""
    r = git("rev-list", "--reverse", "%s..%s" % (base or main_branch(cwd), branch), cwd=cwd)
    if not r.ok:
        return [(branch, "git couldn't list what it would publish")]
    return guard_commits(r.out.split(), cwd=cwd)


def guard_commits(commits, cwd=None):
    """The Guardian over each commit's files and message. Root commits and merges count too
    (`--root -m`: plain diff-tree prints nothing for either), and anything git can't read
    is a problem, never an empty file."""
    from . import guard

    def git_(*args):
        return git(*args, cwd=cwd)
    problems = []
    patterns = guard.SECRET_PATTERNS + guard.personal_patterns()
    for c in commits:
        names = git_("diff-tree", "--root", "-m", "--no-commit-id", "--name-only", "-r", "-z", "--diff-filter=d", c)
        if not names.ok:
            problems.append((c[:8], "git couldn't list its files"))
            continue
        paths = sorted(set(p for p in names.out.split("\0") if p))
        unread = []

        def read(p, c=c):
            shown = git_("show", "%s:%s" % (c, p))
            if not shown.ok:
                unread.append(p)
            return shown.out
        problems += [("%s %s" % (c[:8], p), why) for p, why in guard.scan(paths, read)]
        problems += [("%s %s" % (c[:8], p), "git couldn't read it") for p in unread]
        message = git_("log", "-1", "--format=%B", c)
        if not message.ok:
            problems.append(("%s message" % c[:8], "git couldn't read it"))
            continue
        problems += [("%s message" % c[:8], why) for _, why in guard.check_text("message", message.out, patterns)]
    return problems


def test_commit(branch):
    """Run the tests of exactly what would be merged: a fresh checkout of the branch tip,
    not a workspace that might hold uncommitted edits. None if they couldn't run at all."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="cos-evolve-test-") as tmp:
        path = os.path.join(tmp, "repo")
        r = git("clone", "--quiet", "--local", "--branch", branch, str(core.ROOT), path, timeout=180)
        if not r.ok:
            return None
        return run_tests(path)


def after_run(ws, summary):
    commits = ahead(ws["branch"], ws["base"], cwd=ws["path"])
    if not commits:
        _discard_workspace(ws["branch"])
        return "evolve: no change tonight (%s)" % summary
    r = git("fetch", "--quiet", ws["path"], "%s:%s" % (ws["branch"], ws["branch"]))
    if not r.ok:
        return "evolve: committed on %s but couldn't bring it back: %s" % (ws["branch"], r.err[:200])
    sha = tip(ws["branch"])
    t = test_commit(ws["branch"])
    verdict = "tests pass" if t is not None and t.ok else "TESTS FAIL"
    core.journal("evolve", "%s: %d commit(s), %s" % (ws["branch"], len(commits), verdict),
                 branch=ws["branch"], commits=commits, tip=sha, tests_ok=bool(t is not None and t.ok))
    return "evolved: %s (%s) · review: cos evolve review %s" % (commits[0].split(" ", 1)[-1], verdict, ws["branch"])


def branches():
    r = git("branch", "--list", "evolve/*", "--format=%(refname:short)")
    return [b for b in r.out.splitlines() if b.strip()]


def tip(branch):
    return git("rev-parse", "--verify", "--quiet", branch + "^{commit}").out.strip()


def verdicts(names):
    """{branch: True | False | None}: what the last sandboxed test run said about each branch
    as it is now. None when none ran on its current tip (it was rebased since, say).
    Entries from before tips were journaled count for the branch as it is."""
    last = {}
    for e in core.read_journal(days=60, kind="evolve"):
        if e.get("branch") in names and "tests_ok" in e:
            last[e["branch"]] = e
    out = {}
    for b in names:
        e = last.get(b)
        out[b] = e["tests_ok"] if e and e.get("tip") in (None, tip(b)) else None
    return out


TESTS_SAID = {True: " · tests pass", False: " · its tests FAIL in the sandbox (merge refuses it)"}


def status_rows():
    names = branches()
    ok = verdicts(names)
    return [{"branch": b, "commits": ahead(b), "tests_ok": ok[b]} for b in names]


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
    catch_up(apply=True, fetch="force", source="evolve merge")


# ---------------------------------------------------------------- catching up (decision 0011)

GITHUB_COMMITTER = "GitHub <noreply@github.com>"
SQUASHED = re.compile(r"\(#\d+\)$")
# Nothing from the incoming tree runs (core.hooksPath is relative, so a merged githooks/
# post-merge would), and nothing can stop to ask for a login: a boot must never stall.
SAFE_GIT = ["-c", "core.hooksPath=/dev/null", "-c", "credential.helper=",
            "-c", "submodule.recurse=false", "-c", "core.fsmonitor=false"]
QUIET = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": ""}
FETCH_EVERY = 600


def _origin_problem(cwd):
    """Why origin can't be taken for Claude OS on GitHub, or None."""
    from . import hook
    if not hook.GITHUB.match(git("config", "--get", "remote.origin.url", cwd=cwd).out or ""):
        return "origin isn't a GitHub repository"
    if git("config", "--get-regexp", r"^url\..*insteadof$", cwd=cwd).out:
        return "a url.*.insteadOf rule could send the fetch somewhere else"
    return None


def _stranger(target, cwd):
    """The first incoming commit that isn't GitHub squash-merging a pull request, or None.
    Main's ruleset only allows those, so anything else is worth a human's look. "?" when git
    can't say: that's never taken for "none"."""
    r = git("log", "--first-parent", "--format=%H%x1f%P%x1f%cn <%ce>%x1f%s", "HEAD.." + target, cwd=cwd)
    lines = [l for l in r.out.splitlines() if l]
    if not r.ok or not lines:
        return "?"
    for line in lines:
        sha, parents, committer, subject = (line.split("\x1f") + ["", "", ""])[:4]
        if len(parents.split()) != 1 or committer != GITHUB_COMMITTER or not SQUASHED.search(subject):
            return sha[:7]
    return None


def _lock(wait):
    """One process moves the checkout at a time, and one about to load Claude OS's code waits
    for a move in progress. -> an open file holding the lock, or None after `wait` seconds."""
    import fcntl
    f = open(str(core.home("state", "catch-up.lock")), "w")
    deadline = time.time() + wait
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() >= deadline:
                f.close()
                return None
            time.sleep(0.2)


def wait_for_moves(wait=15):
    """Before importing the server: let a catch-up that's under way finish first."""
    lock = _lock(wait)
    if lock:
        lock.close()


def hold_serving():
    """Every `cos serve` holds this shared lock while it runs, so a catch-up can tell that a
    server has Claude OS's code loaded (the app's, or one in a browser). Keep the file open."""
    import fcntl
    f = open(str(core.home("state", "serve.lock")), "a")
    fcntl.flock(f, fcntl.LOCK_SH)
    return f


def serving():
    """Is some `cos serve` running? An answer we can't get counts as yes."""
    import fcntl
    try:
        f = open(str(core.home("state", "serve.lock")), "a")
    except OSError:
        return True
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(f, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        f.close()


def code_in_use():
    """Would moving the checkout pull code from under something that has it loaded?"""
    return serving() or core.app_running("ClaudeOS", unknown=True)


def catch_up(apply=False, fetch=True, source="cli", cwd=None, retry=False):
    """Where the live checkout stands against main on GitHub; with apply, fast-forward it.

    Only a clean main with no commits of its own moves, only forward, and only over commits
    GitHub made by squash-merging a pull request. Everything is decided about one commit,
    resolved once, and that's the one merged. fetch: True fetches when the last fetch is 10
    minutes old, "force" always, False never. A move that failed for a commit isn't tried
    again for it unless `retry` (the human asked). The answer is cached for the banner."""
    cwd = str(cwd or core.ROOT)
    lock = _lock(wait=15) if apply else None
    if apply and not lock:
        out = _where(cwd, fetch=False)
        out["why"] = out["why"] or "another catch-up is running"
        return out
    try:
        out = _where(cwd, fetch, retry)
        if apply and out["behind"] and not out["why"] and (os.environ.get("CLAUDE_OS_DAEMON") or os.environ.get("COS_SANDBOXED")):
            out["why"] = "a background job never moves Claude OS's own code"
        if apply and out["behind"] and not out["why"]:
            _fast_forward(out, cwd, source)
        core.cache_put("catch-up", {k: v for k, v in out.items() if k != "target"})
        return out
    finally:
        if lock:
            lock.close()


def _where(cwd, fetch, retry=False):
    from . import hook
    main = main_branch(cwd)
    base = "origin/" + main
    origin = _origin_problem(cwd)
    fetched = None
    if fetch and not origin and (fetch == "force" or not core.cache_get("catch-up-fetch", max_age=FETCH_EVERY)):
        r = core.run(["git"] + SAFE_GIT + ["fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", main],
                     cwd=cwd, timeout=8 if fetch == "force" else 4, env=QUIET)
        fetched = r.ok
        core.cache_put("catch-up-fetch", {"ok": r.ok})
    resolved = git("rev-parse", "--verify", "--quiet", base + "^{commit}", cwd=cwd)
    target = resolved.out if resolved.ok else ""
    counts = git("rev-list", "--left-right", "--count", "HEAD..." + target, cwd=cwd).out.split() if target else []
    ahead, behind = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (0, 0)
    out = {"behind": behind, "ahead": ahead, "head": git("rev-parse", "--short", "HEAD", cwd=cwd).out,
           "latest": target[:7], "target": target, "subjects": [], "protected": [],
           "paths": [], "updated": False, "fetched": fetched, "why": None}
    if behind:
        out["subjects"] = git("log", "--format=%s", "HEAD.." + target, cwd=cwd).out.splitlines()
        out["paths"] = git("diff", "--no-renames", "--name-only", "HEAD", target, cwd=cwd).out.splitlines()
        out["protected"] = [p for p in out["paths"] if hook.protected(p)]
    stranger = _stranger(target, cwd) if behind else None
    failed = ((core.cache_get("catch-up-failed") or {}).get("data") or {})
    if len(counts) != 2:
        out["why"] = "git can't compare it with %s" % base
    elif git("symbolic-ref", "--short", "HEAD", cwd=cwd).out != main:
        out["why"] = "the checkout isn't on %s" % main
    elif git("status", "--porcelain", "--untracked-files=no", cwd=cwd).out.strip():
        out["why"] = "it has uncommitted changes"
    elif ahead:
        out["why"] = "it has %d commit%s GitHub hasn't got" % (ahead, "" if ahead == 1 else "s")
    elif origin:
        out["why"] = origin
    elif stranger == "?":
        out["why"] = "git couldn't say where the incoming commits came from"
    elif stranger:
        out["why"] = "commit %s didn't come from a GitHub pull request merge" % stranger
    elif behind and not retry and failed.get("target") == target:
        out["why"] = failed.get("why")
    return out


def _fast_forward(out, cwd, source):
    old = git("rev-parse", "HEAD", cwd=cwd).out
    r = core.run(["git"] + SAFE_GIT + ["merge", "--ff-only", "--no-overwrite-ignore", "--quiet", out["target"]],
                 cwd=cwd, timeout=60, env=QUIET)
    if not r.ok:
        out["why"] = "git refused the fast-forward: %s" % (r.err or r.out)[:200]
        core.cache_put("catch-up-failed", {"target": out["target"], "why": out["why"]})
        return
    try:
        core.home("cache", "catch-up-failed.json").unlink()
    except OSError:
        pass
    out.update(updated=True, head=git("rev-parse", "--short", "HEAD", cwd=cwd).out, ahead=0)
    core.journal("action", "Claude OS caught up with main: %d change%s" % (
                     out["behind"], "" if out["behind"] == 1 else "s"),
                 source=source, old=old, new=git("rev-parse", "HEAD", cwd=cwd).out,
                 subjects=out["subjects"][:20], protected=out["protected"], undo="git reset --keep %s" % old)
    out["behind"] = 0
    core.cache_put("caught-up", {"subjects": out["subjects"], "protected": out["protected"],
                                 "source": source, "head": out["head"]})


def auto_catch_up(source, cwd=None):
    """With "Keep Claude OS up to date" on (0011, part two), fast-forward. Callers only call
    it where no old code is loaded: the app's server before it imports anything, a terminal
    session's boot and pulse while no server has the code loaded (code_in_use).
    -> catch_up's dict, or None when the switch is off."""
    auto = core.config().get("autonomy")
    if not isinstance(auto, dict) or auto.get("catch_up") is not True:
        return None
    if not auto.get("catch_up_url") or git("config", "--get", "remote.origin.url", cwd=cwd).out != auto["catch_up_url"]:
        c = catch_up(fetch=True, source=source, cwd=cwd)
        c["why"] = c["why"] or "origin isn't the repository Keep Claude OS up to date was turned on for"
        return c
    return catch_up(apply=True, fetch=True, source=source, cwd=cwd)


def main(args):
    c = args.evolve_cmd or "status"
    if c == "status":
        rows = status_rows()
        if args.json:
            core.emit(rows, True, None)
            return 0
        if not rows:
            print("No evolve branches waiting. (The nightly evolve daemon creates them: cos daemon install evolve)")
        for r in rows:
            print("%s  (%d commit%s)%s" % (r["branch"], len(r["commits"]), "" if len(r["commits"]) == 1 else "s",
                                         TESTS_SAID.get(r["tests_ok"], "")))
            for c_ in r["commits"][:5]:
                print("    %s" % c_)
        from . import hook
        night = hook.waiting()
        if night:  # quiet when there are none, or GitHub can't be asked
            print("\nNight shift pull requests:")
            hook.render_waiting(night)
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
        sha = tip(args.branch)
        t = test_commit(args.branch)
        if t is None:
            core.die("couldn't run the branch's tests; not merging")
        if not t.ok:
            core.journal("evolve", "%s: tests fail, not merged" % args.branch, branch=args.branch, tip=sha, tests_ok=False)
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
