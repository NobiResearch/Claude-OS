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


class TestSandbox(TempHome):
    @unittest.skipUnless(core.which("sandbox-exec"), "macOS only")
    @unittest.skipIf(os.environ.get("COS_SANDBOXED"), "sandboxes don't nest")
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
