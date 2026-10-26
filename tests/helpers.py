"""Test helpers: every test runs against a throwaway CLAUDE_OS_HOME."""
import http.client
import os
import shutil
import socket
import socketserver
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))


REAL_HOME = os.path.expanduser("~")
# Read before any TempHome clears it: inside the evolve sandbox, tests have no network at all.
IN_SANDBOX = bool(os.environ.get("COS_SANDBOXED"))


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    """The tests' HTTP servers listen on a Unix socket in the test's own temp folder: the
    evolve sandbox gives model-written tests no network, only sockets in their own folder
    (core.run_sandboxed). The server's handler doesn't care which socket it's on."""
    daemon_threads = True

    def get_request(self):
        request, _ = self.socket.accept()
        return request, ("local", 0)  # BaseHTTPRequestHandler wants an address pair


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=10):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


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
