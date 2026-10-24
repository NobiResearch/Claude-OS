import os
import subprocess
import unittest

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


def _can_sandbox():
    """sandbox-exec can't apply a profile from inside another sandbox (e.g. evolve's own)."""
    if not core.which("sandbox-exec"):
        return False
    return core.run(["sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"], timeout=10).ok


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


if __name__ == "__main__":
    unittest.main()
