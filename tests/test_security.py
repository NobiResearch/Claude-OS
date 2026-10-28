import io
import json
import os
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
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
            self.assertIn('with prompt "Ovenbird wants to', script, "the dialog says who is asking")
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

    def test_disabled_inside_a_sandbox_means_unknown(self):
        # Friction #25: a sandbox keeps socketfilterfw from its service, and it says "disabled".
        for in_sandbox, expected in ((False, False), (True, None)):
            with mock.patch.object(security.core, "run", FakeMac(firewall=False)), \
                    mock.patch.object(security, "sandboxed", return_value=in_sandbox):
                self.assertIs(security.posture()["firewall"], expected, in_sandbox)
            with mock.patch.object(security.core, "run", FakeMac(firewall=True)), \
                    mock.patch.object(security, "sandboxed", return_value=in_sandbox):
                self.assertIs(security.posture()["firewall"], True, "on is on, sandbox or not")
        self.assertIsInstance(security.sandboxed(), bool)
        with mock.patch.dict(os.environ, {"COS_SANDBOXED": "1"}):
            self.assertTrue(security.sandboxed())

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
    # Merging or dropping an evolve branch only changes this repository, which is Claude's to
    # change without asking (decision 0013). A daemon still may never run them.
    THE_REPOSITORY = {("evolve", "merge"), ("evolve", "discard")}

    def test_every_mutation_asks_and_no_daemon_may_run_it(self):
        with open(os.path.join(ROOT, ".claude", "settings.json")) as f:
            asks = json.load(f)["permissions"]["ask"]
        for key in cli.MUTATING:
            words = " ".join(key)
            self.assertTrue(any(d.startswith("Bash(cos %s" % words) for d in daemon.ALWAYS_DENIED)
                            or any(d == "Bash(cos %s*)" % key[0] for d in daemon.ALWAYS_DENIED), key)
            if key in self.THE_REPOSITORY:
                self.assertFalse(any(words in a for a in asks), key)
                continue
            for prefix in ("bin/cos", "./bin/cos", "cos"):
                self.assertTrue(any(a.startswith("Bash(%s %s" % (prefix, words)) for a in asks), (prefix, key))


if __name__ == "__main__":
    unittest.main()


class TestStrangerSafeSettings(unittest.TestCase):
    """The checked-in .claude/settings.json is what everyone who clones or downloads Ovenbird
    runs (decision 0017). It may let Claude run only what's safe for a stranger without a card:
    Ovenbird's own syscalls (read-only unless --yes, and the mutating ones ask) and a few
    read-only system commands. The owner's broader allows live in their own, gitignored
    .claude/settings.local.json."""

    VETTED = {"Bash(bin/cos)", "Bash(bin/cos *)", "Bash(./bin/cos *)", "Bash(cos *)",
              "Bash(sw_vers*)", "Bash(pmset -g*)", "Bash(mdfind *)", "Bash(shortcuts list*)"}

    def settings(self):
        with open(os.path.join(ROOT, ".claude", "settings.json")) as f:
            return json.load(f)["permissions"]

    def test_only_vetted_allows(self):
        allow = set(self.settings()["allow"])
        self.assertEqual(allow - self.VETTED, set(), "a new allow rule: is it safe for a stranger's Claude?")
        for rule in allow:
            for risky in ("Bash(git", "Bash(gh ", "Bash(gh-", "Bash(python", "Bash(sh ", "Bash(bash", "Bash(curl", "Bash(*"):
                self.assertFalse(rule.startswith(risky), rule)

    def test_the_owner_still_asks_before_publishing(self):
        ask = self.settings()["ask"]
        for rule in ("Bash(gh release*)", "Bash(gh repo delete*)", "Bash(xcrun notarytool*)", "Bash(*app/build.sh --release*)",
                     "Bash(cos app)", "Bash(bin/cos app)", "Bash(./bin/cos app)"):
            self.assertIn(rule, ask)

    def test_the_app_writes_the_same_deny_list(self):
        with open(os.path.join(ROOT, "app", "Sources", "ClaudeOS", "FirstLaunch.swift")) as f:
            swift = f.read()
        line = next(l for l in swift.splitlines() if '"deny":' in l)
        self.assertEqual(re.findall(r'"(Bash\([^"]*\))"', line), core.DOWNLOAD_DENY)


class TestKeepDownloadSettings(TempHome):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "Ovenbird")
        os.makedirs(os.path.join(self.root, ".claude"))
        patcher = mock.patch.object(core, "ROOT", Path(self.root))
        patcher.start()
        self.addCleanup(patcher.stop)

    def local(self):
        return core.load_json(os.path.join(self.root, ".claude", "settings.local.json"), None)

    def test_a_download_gets_its_denies_back_and_keeps_its_own_rules(self):
        from cos import system
        with mock.patch.object(core, "downloaded", return_value=True):
            self.assertTrue(system.keep_download_settings(), "deleted by git clean -X: written again")
            self.assertEqual(self.local()["permissions"]["deny"], core.DOWNLOAD_DENY)
            core.save_json(os.path.join(self.root, ".claude", "settings.local.json"),
                           {"permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(gh *)", "Bash(rm *)"]}})
            self.assertTrue(system.keep_download_settings())
            d = self.local()["permissions"]
            self.assertEqual(d["allow"], ["Bash(ls)"])
            self.assertEqual(set(d["deny"]), set(core.DOWNLOAD_DENY) | {"Bash(rm *)"})
            self.assertFalse(system.keep_download_settings(), "nothing missing: not written")

    def test_a_file_it_cant_read_is_kept_beside_not_lost(self):
        from cos import system
        path = os.path.join(self.root, ".claude", "settings.local.json")
        with open(path, "w") as f:
            f.write('{"permissions": {"allow": ["Bash(ls)"],}}')  # a trailing comma
        with mock.patch.object(core, "downloaded", return_value=True):
            self.assertTrue(system.keep_download_settings())
        aside = [n for n in os.listdir(os.path.dirname(path)) if n.startswith("settings.local.json.broken-")]
        self.assertEqual(len(aside), 1)
        with open(os.path.join(os.path.dirname(path), aside[0])) as f:
            self.assertIn('"Bash(ls)"', f.read(), "the person's rules survive")
        self.assertEqual(self.local()["permissions"]["deny"], core.DOWNLOAD_DENY)

    def test_a_linked_file_is_left_alone(self):
        from cos import system
        target = os.path.join(self.tmp, "elsewhere.json")
        with open(target, "w") as f:
            f.write("{}")
        os.symlink(target, os.path.join(self.root, ".claude", "settings.local.json"))
        with mock.patch.object(core, "downloaded", return_value=True):
            self.assertFalse(system.keep_download_settings())
        with open(target) as f:
            self.assertEqual(f.read(), "{}")

    def test_a_checkout_that_isnt_a_download_is_left_alone(self):
        from cos import system
        with mock.patch.object(core, "downloaded", return_value=False):
            self.assertFalse(system.keep_download_settings())
        self.assertIsNone(self.local())
