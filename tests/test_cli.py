import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import cli, core

COS = os.path.join(str(core.ROOT), "bin", "cos")


class TestCli(TempHome):
    def cos(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(list(args))
        return rc, out.getvalue()

    def test_every_command_has_a_parser(self):
        parser = cli.build_parser()
        choices = parser._subparsers._group_actions[0].choices
        self.assertEqual(set(choices), cli.COMMANDS)

    def test_json_flag_anywhere(self):
        rc, out = self.cos("friction", "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), [])
        self.cos("friction", "add", "something broke", "--area", "test")
        rc, out = self.cos("--json", "friction")
        self.assertEqual(json.loads(out)[0]["text"], "something broke")

    def test_mutations_must_be_canonical(self):
        for argv in (["--json", "clean", "apply", "logs", "--yes"], ["clean", "--deep", "apply", "logs"],
                     ["update", "--fetch", "apply", "brew", "--yes"]):
            with self.assertRaises(SystemExit) as cm:
                self.cos(*argv)
            self.assertEqual(cm.exception.code, 2, argv)

    def test_daemons_cannot_mutate(self):
        os.environ["CLAUDE_OS_DAEMON"] = "morning"
        try:
            for argv in (["clean", "apply", "logs", "--yes"], ["evolve", "merge", "evolve/x", "--yes"],
                         ["daemon", "install", "pulse"], ["daemon", "run", "evolve"], ["uninstall"]):
                with self.assertRaises(SystemExit) as cm:
                    self.cos(*argv)
                self.assertEqual(cm.exception.code, 3, argv)
            rc, _ = self.cos("friction")  # reading is fine
            self.assertEqual(rc, 0)
        finally:
            del os.environ["CLAUDE_OS_DAEMON"]

    def test_daemons_cannot_change_settings_music_or_feeds(self):
        os.environ["CLAUDE_OS_DAEMON"] = "morning"
        try:
            for argv in (["cal", "connect"], ["weather", "set", "Lisbon"], ["feeds", "add", "https://x.example/feed"],
                         ["config", "notify.native", "true"], ["music", "play", "anything"], ["music", "like"],
                         ["music", "radio"], ["music", "radio", "anything"], ["remember", "a fact"],
                         ["memory", "--forget", "a fact"], ["ask", "anything"], ["serve"], ["app", "build"],
                         ["startup", "--full"]):
                with self.assertRaises(SystemExit) as cm:
                    self.cos(*argv)
                self.assertEqual(cm.exception.code, 3, argv)
            rc, _ = self.cos("config")  # reading the config is fine
            self.assertEqual(rc, 0)
            rc, _ = self.cos("memory")  # and reading the memory
            self.assertEqual(rc, 0)
        finally:
            del os.environ["CLAUDE_OS_DAEMON"]

    def test_startup_full_must_be_written_so_the_ask_rule_sees_it(self):
        # Refused before anything runs: `--full` summons macOS's admin password dialog.
        with self.assertRaises(SystemExit) as cm:
            self.cos("startup", "--json", "--full")
        self.assertEqual(cm.exception.code, 2)

    def test_free_text_never_spawns_claude_without_a_terminal(self):
        r = subprocess.run([sys.executable, COS, "please clean everything"], capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown command", r.stderr)

    def test_status_json_shape(self):
        rc, out = self.cos("status", "--json")
        data = json.loads(out)
        for key in ("system", "disk", "memory", "signals"):
            self.assertIn(key, data)

    def test_boot_is_fast_and_offline(self):
        # Its one network call, a fetch of main, waits 10 minutes after the last one (0011).
        core.cache_put("catch-up-fetch", {"ok": True})
        real, ran = core.run, []

        def spy(cmd, **kw):
            ran.append(cmd)
            return real(cmd, **kw)
        with mock.patch.object(core, "run", spy):
            rc, out = self.cos("boot")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("◆ Claude OS"))
        self.assertEqual([c for c in ran if "fetch" in c], [])

    def test_entry_point_runs_under_system_python(self):
        # macOS's own Python. The evolve sandbox puts the developer folder on PATH and that one
        # is used there: /usr/bin/python3 is an xcrun shim to it, and xcrun can't run inside.
        developer = [os.path.join(d, "python3") for d in os.environ.get("PATH", "").split(":")
                     if d.endswith("/Developer/usr/bin")]
        python = next((p for p in developer + ["/usr/bin/python3"] if os.path.exists(p)), sys.executable)
        r = subprocess.run([python, COS, "version"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Claude OS", r.stdout)

    def test_statusline_reads_claude_payload(self):
        r = subprocess.run([sys.executable, COS, "statusline"], input='{"model": {"display_name": "Test"}}',
                           capture_output=True, text=True, timeout=30, env=dict(os.environ))
        self.assertIn("Claude OS", r.stdout)
        self.assertIn("Test", r.stdout)


if __name__ == "__main__":
    unittest.main()
