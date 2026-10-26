"""Test helpers: every test runs against a throwaway CLAUDE_OS_HOME."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))


REAL_HOME = os.path.expanduser("~")


def test_port():
    """The localhost port a test's own server binds: any (0) normally; inside the evolve
    sandbox, the one port it may use (core.run_sandboxed), so model-written tests reach
    nothing else on localhost. One server at a time, closed before the next binds."""
    return int(os.environ.get("COS_TEST_PORT") or 0)


class TempHome(unittest.TestCase):
    """Points both HOME and CLAUDE_OS_HOME at a throwaway folder, so no test can touch
    the real home folder or the real ~/.claude-os."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cos-test-")
        self._old = {k: os.environ.get(k) for k in ("CLAUDE_OS_HOME", "HOME", "CLAUDE_OS_DAEMON", "COS_SANDBOXED")}
        # Tests that need these set them themselves. `cos evolve merge` runs the suite with
        # both set (core.run_sandboxed), and code that refuses inside a sandbox must not
        # fail its own tests there.
        os.environ.pop("CLAUDE_OS_DAEMON", None)
        os.environ.pop("COS_SANDBOXED", None)
        os.environ["CLAUDE_OS_HOME"] = os.path.join(self.tmp, "state")
        os.environ["HOME"] = os.path.join(self.tmp, "home")
        os.makedirs(os.environ["HOME"])

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)
