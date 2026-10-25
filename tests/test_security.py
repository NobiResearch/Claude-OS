import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import cli, core, daemon, hook, security

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class FakeMac:
    """Stands in for core.run: the firewall's state, and what the password dialog does."""

    def __init__(self, firewall=False, dialog="ok"):
        self.firewall, self.dialog, self.calls = firewall, dialog, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] == security.FIREWALL:
            return core.Result(0, "Firewall is %s. (State = %d)" % (("enabled", 1) if self.firewall else ("disabled", 0)), "")
        if cmd[0] == security.OSASCRIPT:
            if self.dialog == "ok":
                self.firewall = True
                return core.Result(0, "", "")
            if self.dialog == "cancel":
                return core.Result(1, "", "0:120: execution error: Brukeren avbrøt. (-128)")
            return core.Result(0, "", "")  # "managed": accepted, nothing changed
        return core.Result(0, "", "")


class TestSecurity(TempHome):
    def turn_on(self, mac, yes=True):
        with mock.patch.object(security.core, "run", mac), redirect_stdout(io.StringIO()) as out:
            rc = security.turn_on("firewall", yes=yes)
        return rc, out.getvalue()

    def test_only_ever_on_and_nothing_filled_in(self):
        for name, script in security.SWITCHES.items():
            self.assertIn(" on", script, name)
            for word in ("off", "disable", "remove", "%", "{"):
                self.assertNotIn(word, script.lower(), name)
            self.assertIn('with prompt "Claude OS wants to', script, "the dialog says who is asking")
        self.assertEqual(list(security.SWITCHES), ["firewall"], "FileVault, SIP and Gatekeeper aren't switches")
        parser = cli.build_parser()
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            parser.parse_args(["security", "off", "firewall"])
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            parser.parse_args(["security", "on", "gatekeeper"])

    def test_turns_it_on_and_checks(self):
        mac = FakeMac()
        rc, out = self.turn_on(mac)
        self.assertEqual(rc, 0)
        self.assertIn("✓ The firewall is on", out)
        osa = [c for c in mac.calls if c[0] == security.OSASCRIPT]
        self.assertEqual(osa, [[security.OSASCRIPT, "-e", "with timeout of 120 seconds", "-e", security.SWITCHES["firewall"], "-e", "end timeout"]])
        self.assertEqual(core.read_journal(days=1, kind="action")[-1]["msg"], "security: firewall turned on")

    def test_a_cancelled_dialog_in_any_language(self):
        rc, out = self.turn_on(FakeMac(dialog="cancel"))
        self.assertEqual(rc, 1)
        self.assertIn("cancelled at the password dialog", out)
        self.assertIn("unchanged", core.read_journal(days=1, kind="action")[-1]["msg"])

    def test_it_trusts_the_state_not_the_exit_code(self):
        rc, out = self.turn_on(FakeMac(dialog="managed"))
        self.assertEqual(rc, 1)
        self.assertIn("managed by your organization", out)

    def test_dry_run_and_already_on(self):
        mac = FakeMac()
        rc, out = self.turn_on(mac, yes=False)
        self.assertEqual(rc, 2)
        self.assertIn("password dialog", out)
        self.assertFalse(any(c[0] == security.OSASCRIPT for c in mac.calls))
        mac = FakeMac(firewall=True)
        self.assertEqual(self.turn_on(mac)[0], 0)
        self.assertFalse(any(c[0] == security.OSASCRIPT for c in mac.calls), "nothing to do, no dialog")

    def test_never_from_a_background_job_or_a_test_sandbox(self):
        for env in ({"CLAUDE_OS_DAEMON": "morning"}, {"COS_SANDBOXED": "1"}):
            mac = FakeMac()
            with mock.patch.dict(os.environ, env), mock.patch.object(security.core, "run", mac), \
                    mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as ctx:
                security.turn_on("firewall", yes=True)
            self.assertEqual(ctx.exception.code, 3)
            self.assertEqual(mac.calls, [])

    def test_the_read_view_says_how(self):
        state = {"filevault": True, "sip": True, "firewall": False, "gatekeeper": None}
        with redirect_stdout(io.StringIO()) as out:
            security.render(state)
        text = out.getvalue()
        self.assertIn("✗ Firewall", text)
        self.assertIn("cos security on firewall --yes", text)
        self.assertIn("couldn't tell", text)

    def test_root_code_is_protected_and_imports_only_core(self):
        self.assertTrue(hook.protected("lib/cos/security.py"))
        with open(security.__file__) as f:
            imports = [l.strip() for l in f if l.startswith(("import ", "from "))]
        self.assertEqual(sorted(imports), ["from . import core", "import os", "import re"])


class TestMutationRegistry(unittest.TestCase):

    def test_every_mutation_asks_and_no_daemon_may_run_it(self):
        with open(os.path.join(ROOT, ".claude", "settings.json")) as f:
            asks = json.load(f)["permissions"]["ask"]
        for key in cli.MUTATING:
            words = " ".join(key)
            self.assertTrue(any(d.startswith("Bash(cos %s" % words) for d in daemon.ALWAYS_DENIED)
                            or any(d == "Bash(cos %s*)" % key[0] for d in daemon.ALWAYS_DENIED), key)
            for prefix in ("bin/cos", "./bin/cos", "cos"):
                self.assertTrue(any(a.startswith("Bash(%s %s" % (prefix, words)) for a in asks), (prefix, key))


if __name__ == "__main__":
    unittest.main()
