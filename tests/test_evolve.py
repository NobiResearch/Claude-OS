import argparse
import io
import json
import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import core, evolve


class TestEvolveSafety(TempHome):
    def test_only_evolve_branches(self):
        for bad in ("main", "master", "feature/x", "evolve/../main", "", None):
            with self.assertRaises(SystemExit, msg=repr(bad)):
                evolve._check_branch(bad)
        evolve._check_branch("evolve/2026-10-24")
        evolve._check_branch("evolve/2026-10-24-2")

    def test_remove_refuses_main_without_touching_anything(self):
        before = set(os.listdir(str(core.ROOT)))
        with self.assertRaises(SystemExit):
            evolve.remove("main")
        self.assertEqual(set(os.listdir(str(core.ROOT))), before)

    def test_friction_refs_parsed_from_commits(self):
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        g = lambda *a: subprocess.run(["git", "-C", repo, "-c", "user.email=t@example.com", "-c", "user.name=t"] + list(a),
                                      capture_output=True, check=True)
        g("init", "-q", "-b", "main")
        g("commit", "-q", "--allow-empty", "-m", "base")
        g("checkout", "-q", "-b", "evolve/x")
        g("commit", "-q", "--allow-empty", "-m", "fix\n\nAddresses friction #3 and Friction #12")
        original = evolve.git
        evolve.git = lambda *a, **k: original(*a, cwd=repo, **{x: y for x, y in k.items() if x != "cwd"})
        try:
            self.assertEqual(evolve.addressed_frictions("evolve/x", "main"), [3, 12])
        finally:
            evolve.git = original


class TestWorkspace(TempHome):
    def test_clone_branch_fetch_and_cleanup(self):
        """The nightly flow: clone main, commit on evolve/<date>, fetch back, remove."""
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(repo, "tests"))
        run = lambda *a, cwd=repo: subprocess.run(["git", "-C", cwd, "-c", "user.email=t@example.com",
                                                   "-c", "user.name=t"] + list(a), capture_output=True, check=True)
        run("init", "-q", "-b", "main")
        open(os.path.join(repo, "README.md"), "w").write("hi\n")
        run("add", "-A")
        run("commit", "-q", "-m", "base")
        original_root = core.ROOT
        from pathlib import Path
        core.ROOT = Path(repo)
        try:
            ws = evolve.new_workspace()
            self.assertTrue(ws["branch"].startswith("evolve/"))
            self.assertTrue(ws["path"].startswith(os.environ["CLAUDE_OS_HOME"]))
            open(os.path.join(ws["path"], "NEW.md"), "w").write("change\n")
            run("add", "-A", cwd=ws["path"])
            run("commit", "-q", "--no-verify", "-m", "a nightly change", cwd=ws["path"])
            original_tests = evolve.run_tests
            evolve.run_tests = lambda path: core.Result(0, "", "")
            try:
                summary = evolve.after_run(ws, "done")
            finally:
                evolve.run_tests = original_tests
            self.assertIn("a nightly change", summary)
            self.assertIn(ws["branch"], evolve.branches(), "the branch came back into the main repo")
            evolve.remove(ws["branch"])
            self.assertFalse(os.path.exists(ws["path"]))
            self.assertEqual(evolve.branches(), [])
        finally:
            core.ROOT = original_root


class TestSafetyFiles(TempHome):
    """A branch that changes Claude OS's gate merges only after a guardian review (0013)."""

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "lib", "cos"))
        self.g("init", "-q", "-b", "main")
        self.g("commit", "-q", "--allow-empty", "-m", "base")
        self.g("checkout", "-q", "-b", "evolve/x")
        for path in ("lib/cos/hook.py", "docs.md"):
            open(os.path.join(self.repo, path), "w").write("x\n")
        self.g("add", "-A")
        self.g("commit", "-q", "-m", "a nightly change")
        self.g("checkout", "-q", "main")
        original = evolve.git
        evolve.git = lambda *a, **k: original(*a, cwd=self.repo, **{x: y for x, y in k.items() if x != "cwd"})
        self.addCleanup(setattr, evolve, "git", original)

    def g(self, *a):
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@example.com", "-c", "user.name=t"] + list(a),
                       capture_output=True, check=True)

    def merge(self, yes=True, reviewed=False, tip=None):
        args = argparse.Namespace(evolve_cmd="merge", branch="evolve/x", yes=yes, reviewed=reviewed, tip=tip, json=False)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(evolve, "_github", return_value=True), \
                mock.patch.object(evolve, "guard_branch", return_value=[("x", "stop here")]) as guard, \
                redirect_stdout(out), redirect_stderr(err):
            try:
                rc = evolve.main(args)
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue() + err.getvalue(), guard.called

    def test_it_lists_the_safety_files(self):
        self.assertEqual(evolve.safety_files("evolve/x"), ["lib/cos/hook.py"])
        self.assertEqual(evolve.status_rows()[0]["protected"], ["lib/cos/hook.py"])

    def test_merge_wants_a_review_first(self):
        rc, said, checked = self.merge(yes=False)
        self.assertEqual(rc, 2)
        self.assertIn("a guardian agent reviews it first", said)
        rc, said, checked = self.merge()
        self.assertNotEqual(rc, 0)
        self.assertIn("lib/cos/hook.py", said)
        self.assertFalse(checked, "nothing else runs before the review")
        rc, said, checked = self.merge(reviewed=True)
        self.assertTrue(checked, "reviewed: on to the Guardian and the tests")

    def test_a_review_covers_the_commit_that_was_shown(self):
        shown = evolve.status_rows()[0]["tip"]
        self.assertEqual(shown, evolve.tip("evolve/x"))
        rc, said, checked = self.merge(reviewed=True, tip=shown)
        self.assertTrue(checked)
        self.g("checkout", "-q", "evolve/x")
        self.g("commit", "-q", "--allow-empty", "-m", "arrived after the review")
        self.g("checkout", "-q", "main")
        rc, said, checked = self.merge(reviewed=True, tip=shown)
        self.assertNotEqual(rc, 0)
        self.assertIn("has moved since it was reviewed", said)
        self.assertFalse(checked)

    def test_what_github_has_is_the_base(self):
        """A commit only this Mac's main has, carried along by the branch, counts too."""
        base = subprocess.run(["git", "-C", self.repo, "rev-parse", "main"], capture_output=True, text=True).stdout.strip()
        self.g("update-ref", "refs/remotes/origin/main", base)
        os.makedirs(os.path.join(self.repo, "lib", "cos"), exist_ok=True)
        open(os.path.join(self.repo, "lib", "cos", "core.py"), "w").write("local only\n")
        self.g("add", "-A")
        self.g("commit", "-q", "-m", "on this Mac's main only")
        self.g("checkout", "-q", "-b", "evolve/y")
        self.g("checkout", "-q", "main")
        self.assertEqual(evolve.safety_files("evolve/y"), ["lib/cos/core.py"])


class TestVerdicts(TempHome):
    """A branch whose tests failed in the sandbox says so wherever it's listed (friction #18)."""

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.g("init", "-q", "-b", "main")
        self.g("commit", "-q", "--allow-empty", "-m", "base")
        self.g("checkout", "-q", "-b", "evolve/x")
        self.g("commit", "-q", "--allow-empty", "-m", "a nightly change")
        self.g("checkout", "-q", "main")
        original = evolve.git
        evolve.git = lambda *a, **k: original(*a, cwd=self.repo, **{x: y for x, y in k.items() if x != "cwd"})
        self.addCleanup(setattr, evolve, "git", original)

    def g(self, *a):
        subprocess.run(["git", "-C", self.repo, "-c", "user.email=t@example.com", "-c", "user.name=t"] + list(a),
                       capture_output=True, check=True)

    def ran(self, ok, tip="now"):
        data = {"branch": "evolve/x", "tests_ok": ok}
        if tip:
            data["tip"] = evolve.tip("evolve/x") if tip == "now" else tip
        core.journal("evolve", "evolve/x: tests", **data)

    def test_the_last_run_on_the_current_tip_counts(self):
        self.assertEqual(evolve.verdicts(["evolve/x"]), {"evolve/x": None}, "nothing ran yet")
        self.ran(False)
        self.assertEqual(evolve.status_rows(), [{"branch": "evolve/x", "commits": evolve.ahead("evolve/x"), "tests_ok": False,
                                                 "protected": [], "tip": evolve.tip("evolve/x")}])
        self.ran(True)
        self.assertIs(evolve.verdicts(["evolve/x"])["evolve/x"], True)

    def test_a_branch_that_moved_since_has_no_verdict(self):
        self.ran(False)
        self.g("branch", "-f", "evolve/x", "main")
        self.assertIsNone(evolve.verdicts(["evolve/x"])["evolve/x"])

    def test_entries_from_before_tips_were_journaled_still_count(self):
        self.ran(False, tip=None)
        self.assertIs(evolve.verdicts(["evolve/x"])["evolve/x"], False)

    def test_the_banner_marks_a_failing_branch(self):
        from cos import shell
        self.assertEqual(shell._evolve_line(), "  evolve: 1 branch(es) awaiting review: evolve/x (cos evolve)")
        self.ran(False)
        self.assertIn("evolve/x (its tests FAIL)", shell._evolve_line())
        self.g("branch", "-D", "evolve/x")
        self.assertIsNone(shell._evolve_line())


class TestMergeViaPR(TempHome):
    """CI runs for the pull request, not the push, so it shows up a few seconds after the pull
    request opens; `gh pr checks --watch` gives up at once while there are none."""
    SHA = "a" * 40

    def setUp(self):
        super().setUp()
        self.calls = []
        self.polls = 0
        for name, fake in (("git", lambda *a, **k: core.Result(0, "", "")), ("catch_up", lambda **k: {}),
                           ("_gh", self.gh), ("main_branch", lambda *a: "main")):
            p = mock.patch.object(evolve, name, fake)
            p.start()
            self.addCleanup(p.stop)

    def gh(self, *args, timeout=120):
        self.calls.append(args)
        if args[:2] == ("pr", "view"):
            self.polls += 1
            runs = [{"__typename": "CheckRun", "name": "test", "status": "QUEUED"}] if self.polls >= 3 else []
            return core.Result(0, json.dumps({"statusCheckRollup": runs}), "")
        return core.Result(0, "", "")

    def test_it_waits_for_the_check_to_show_up(self):
        with mock.patch.object(evolve.time, "sleep"):
            self.assertTrue(evolve.wait_for_ci("evolve/x", wait=60, every=0))
        self.assertEqual(self.polls, 3)
        self.polls = -1000
        self.assertFalse(evolve.wait_for_ci("evolve/x", wait=0), "a check that never shows up")

    def test_the_merge_is_pinned_to_the_checked_commit(self):
        with mock.patch.object(evolve.time, "sleep"):
            evolve.merge_via_pr("evolve/x", ["abc123 a nightly change"], self.SHA)
        verbs = [c[:2] for c in self.calls]
        self.assertLess(verbs.index(("pr", "view")), verbs.index(("pr", "checks")), "waits before watching")
        merge = [c for c in self.calls if c[:2] == ("pr", "merge")][0]
        self.assertEqual(merge[merge.index("--match-head-commit") + 1], self.SHA)

    def test_ci_that_never_starts_isnt_reported_as_failing(self):
        with mock.patch.object(evolve, "wait_for_ci", return_value=False), \
                mock.patch.object(core, "die", side_effect=SystemExit) as die:
            with self.assertRaises(SystemExit):
                evolve.merge_via_pr("evolve/x", ["abc123 a nightly change"], self.SHA)
        self.assertIn("hadn't started", die.call_args[0][0])
        self.assertFalse([c for c in self.calls if c[:2] in (("pr", "checks"), ("pr", "merge"))])


def _can_sandbox():
    """sandbox-exec can't apply a profile from inside another sandbox (e.g. evolve's own)."""
    if not core.which("sandbox-exec"):
        return False
    return core.run(["sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"], timeout=10).ok


class TestGuardEveryCommit(TempHome):
    def test_a_file_added_then_deleted_is_still_caught(self):
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        g = lambda *a: subprocess.run(["git", "-C", repo, "-c", "user.email=t@example.com", "-c", "user.name=t"] + list(a),
                                      capture_output=True, check=True)
        g("init", "-q", "-b", "main")
        g("commit", "-q", "--allow-empty", "-m", "base")
        g("checkout", "-q", "-b", "evolve/x")
        open(os.path.join(repo, "memory.json"), "w").write("{}")
        g("add", "-A")
        g("commit", "-q", "-m", "oops")
        os.remove(os.path.join(repo, "memory.json"))
        g("add", "-A")
        g("commit", "-q", "-m", "cover it up")
        original = evolve.git
        evolve.git = lambda *a, **k: original(*a, cwd=repo, **{x: y for x, y in k.items() if x != "cwd"})
        try:
            problems = evolve.guard_branch("evolve/x", "main")
        finally:
            evolve.git = original
        self.assertTrue(any("memory.json" in where for where, _ in problems), problems)


class TestSandbox(TempHome):
    @unittest.skipUnless(_can_sandbox(), "needs sandbox-exec outside any other sandbox")
    def test_untrusted_code_cannot_write_home_or_use_network(self):
        work = os.path.join(self.tmp, "work")
        os.makedirs(work)
        target = os.path.join(os.path.dirname(os.path.realpath(str(core.ROOT))), ".cos-sandbox-probe")
        r = core.run_sandboxed(["sh", "-c", "touch inside && touch %s; curl -s -m 3 https://example.com" % target], cwd=work)
        self.assertTrue(os.path.exists(os.path.join(work, "inside")))
        self.assertFalse(os.path.exists(target))
        self.assertNotEqual(r.rc, 0)
        secret = os.path.join(os.path.expanduser("~"), ".ssh")
        if os.path.isdir(secret):
            r = core.run_sandboxed(["ls", secret], cwd=work)
            self.assertNotEqual(r.rc, 0, "private folders aren't readable from the sandbox")


if __name__ == "__main__":
    unittest.main()
