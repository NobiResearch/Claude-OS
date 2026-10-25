"""Test helpers: every test runs against a throwaway CLAUDE_OS_HOME."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))


REAL_HOME = os.path.expanduser("~")


class TempHome(unittest.TestCase):
    """Points both HOME and CLAUDE_OS_HOME at a throwaway folder, so no test can touch
    the real home folder or the real ~/.claude-os."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cos-test-")
        self._old = {k: os.environ.get(k) for k in ("CLAUDE_OS_HOME", "HOME", "CLAUDE_OS_DAEMON")}
        os.environ.pop("CLAUDE_OS_DAEMON", None)  # tests that need it set it themselves
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
