"""The small findings of the first outside review (Fable 5.1, 27 October 2026), one test each."""

import inspect
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import cli, core, daemon, evolve, feeds, guard, hook, server


class TestReviewFindings(TempHome):
    def test_f6_clones_copy_objects_instead_of_linking_them(self):
        # A hardlinked object rewritten inside a clone would be the live repository's object too.
        calls = []
        with mock.patch.object(evolve, "git", side_effect=lambda *a, **k: calls.append(a) or core.Result(1, "", "stop")):
            self.assertIsNone(evolve.test_commit("night/x"))
        self.assertIn("--no-hardlinks", calls[0])
        self.assertNotIn("--local", calls[0])
        source = inspect.getsource(evolve)
        self.assertEqual(source.count('git("clone"'), source.count('git("clone", "--quiet", "--no-hardlinks"'))

    def test_f15_a_feed_is_read_up_to_a_limit(self):
        class Huge:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                self.asked = n
                return b"x" * (n if n > 0 else feeds.MAX_BYTES * 2)
        resp = Huge()
        with mock.patch.object(core, "http_get", return_value=resp):
            r = feeds.fetch({"url": "https://example.com/feed"}, {})
        self.assertEqual(resp.asked, feeds.MAX_BYTES + 1)  # never an unbounded read
        self.assertEqual((r["ok"], r["error"]), (False, "larger than 5 MB"))
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout=b"ok")) as run:
            core.curl_get("-o /tmp/x https://example.com", max_bytes=10)
        argv = run.call_args[0][0]
        self.assertEqual(argv[argv.index("--max-filesize") + 1], "10")
        self.assertEqual(argv[-2:], ["--", "-o /tmp/x https://example.com"])  # a URL is never an option

    def test_f16_a_section_that_isnt_a_dict_keeps_the_defaults(self):
        core.save_json(core.home("config.json"), {"autonomy": True, "music": "on", "extra": 3})
        cfg = core.config()
        self.assertIsInstance(cfg["autonomy"], dict)
        self.assertFalse(cfg["autonomy"].get("night_shift"))  # a hand edit never turns anything on
        self.assertIsInstance(cfg["music"], dict)
        self.assertEqual(cfg["extra"], 3)  # a section with no default is kept as written

    def test_f17_a_package_name_never_starts_with_a_dash(self):
        for ok in ("node", "@scope/pkg", "python@3.14", "a.b+c-d", "3to2"):
            self.assertTrue(server.UPDATE_NAME.fullmatch(ok), ok)
        for bad in ("-g", "--force", "", "a b", "x;y", "-", "../x", ".hidden", "_x", "a/../b"):
            self.assertFalse(server.UPDATE_NAME.fullmatch(bad), bad)  # nor a local folder (the guardian on #120)

    def test_f16_cos_config_refuses_to_write_a_section_as_a_plain_value(self):
        for argv in (["config", "notify", "false"], ["config", "music", "on"]):
            with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
                cli.main(argv)
            self.assertEqual(e.exception.code, 2, argv)
        self.assertEqual(core.load_json(core.home("config.json"), {}) or {}, {})  # nothing was written
        with redirect_stdout(io.StringIO()):
            cli.main(["config", "notify.enabled", "false"])
        self.assertFalse(core.config()["notify"]["enabled"])

    def test_f12_background_runs_are_denied_everything_cos_refuses_them(self):
        for key in cli.MUTATING | cli.DAEMON_REFUSED:
            for pre in ("bin/cos", "./bin/cos", "cos"):
                self.assertIn("Bash(%s %s*)" % (pre, " ".join(key)), daemon.ALWAYS_DENIED, key)
        known = {" ".join(k) for k in cli.MUTATING | cli.DAEMON_REFUSED} | {"app"}
        self.assertEqual(set(daemon._MUTATING), known)

    def test_f12_a_background_run_never_asks_github(self):
        with mock.patch.dict(os.environ, {"CLAUDE_OS_DAEMON": "morning"}), mock.patch.object(core, "run") as run:
            self.assertIsNone(hook.waiting())
            run.assert_not_called()
            for argv in (["hook", "check"], ["hook", "check", "118"]):
                with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
                    cli.main(argv)
                self.assertEqual(e.exception.code, 3, argv)
            run.assert_not_called()

    def test_f10_the_guard_knows_the_login_and_the_macs_names(self):
        def fake_run(argv, **kw):
            answers = {"ComputerName": "Ada’s MacBook Pro", "LocalHostName": "Adas-MacBook-Pro"}
            return core.Result(0, answers.get(argv[-1], ""), "")
        with mock.patch.object(guard, "login_name", return_value="adalove"), mock.patch.object(core, "run", side_effect=fake_run):
            pats = guard.personal_patterns()
        found = lambda text: sorted(why.split(": ", 1)[1] for _, why in guard.check_text("f", text, pats))
        self.assertEqual(found("adalove@Adas-MacBook-Pro ~ % ls"), ["your Mac's network name", "your login name"])
        self.assertEqual(found("Ada’s MacBook Pro"), ["your Mac's name"])
        self.assertEqual(found("ls ~adalove/notes"), ["your login name"])
        self.assertEqual(found("cd /home/adalove"), ["your login name"])
        # Only where it names someone (the guardian on #120): not a word, not a noreply address.
        for text in ("adaloveliness", "adalove alone", "12345+adalove@users.noreply.github.com",
                     "adalove-tools", "notes.adalove@x"):
            self.assertEqual(found(text), [], text)
        # A Mac renamed "Home" or "Studio" isn't a person: no pattern that would block half the tree.
        for computer in ("Home", "Studio", "Pi", "Office Mac"):
            with mock.patch.object(guard, "login_name", return_value=""), \
                    mock.patch.object(core, "run", side_effect=lambda argv, **kw: core.Result(0, computer, "")):
                self.assertFalse([w for w, _ in guard.personal_patterns() if "Mac" in w], computer)
        # A model name is not a person: never a pattern.
        for name in ("MacBook Pro", "Mac-mini-2", "MacBook-Air.local", "iMac (2)"):
            self.assertTrue(guard.generic_mac_name(name), name)
        self.assertFalse(guard.generic_mac_name("Ada’s MacBook Pro"))
        with mock.patch("pwd.getpwuid", return_value=mock.Mock(pw_name="runner")):
            self.assertEqual(guard.login_name(), "")  # CI's login, and other names everyone has

    def test_f10_the_guard_reads_encoded_paths_and_pictures(self):
        home = [("your home folder path", __import__("re").compile("/Users/ada", __import__("re").I))]
        self.assertTrue(guard.check_text("f", "see https://x.test/?p=%2FUsers%2Fada%2Fnotes", home))
        picture = "\x89PNG\x00\x00tEXtAuthor\x00%s/Desktop/shot.png\x00\xff\xfe" % os.path.expanduser("~")
        self.assertTrue(guard.scan(["docs/shot.png"], lambda p: picture))
        self.assertFalse(guard.scan(["docs/shot.png"], lambda p: "\x89PNG\x00\x00IDAT\xff\x01\x02"))


if __name__ == "__main__":
    unittest.main()
