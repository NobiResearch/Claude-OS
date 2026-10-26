import os
import sys
import time
import unittest

from helpers import TempHome

from cos import core


def _can_list_processes():
    """The evolve sandbox can't list other processes (sysmond is out of reach)."""
    return core.run(["pgrep", "-x", "launchd"], timeout=5).rc == 0


class TestCore(TempHome):
    def test_home_is_private_and_overridable(self):
        path = core.home("journal", "x.jsonl")
        self.assertTrue(str(path).startswith(self.tmp))
        self.assertTrue(path.parent.is_dir())

    def test_run_never_raises(self):
        self.assertEqual(core.run(["definitely-not-a-command-xyz"]).rc, 127)
        self.assertEqual(core.run(["sleep", "5"], timeout=0.2).rc, 124)
        r = core.run(["echo", "hi"])
        self.assertTrue(r.ok)
        self.assertEqual(r.out, "hi")

    @unittest.skipUnless(_can_list_processes(), "needs a process list (not inside the evolve sandbox)")
    def test_app_running_sees_its_own_ancestors(self):
        # The app's chat runs inside the app; macOS pgrep skips ancestors unless told not to.
        name = "cosparent%d" % os.getpid()
        shell = os.path.join(self.tmp, name)
        os.symlink("/bin/sh", shell)
        lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
        probe = "import sys; sys.path.insert(0, %r); from cos import core; print(core.app_running(%r))" % (lib, name)
        r = core.run([shell, "-c", '"$0" -c "$1"; true', sys.executable, probe], timeout=20)
        self.assertEqual(r.out, "True")
        self.assertFalse(core.app_running(name + "-not-running"))

    def test_applescript_quoting(self):
        self.assertEqual(core.applescript_str('say "hi" \\ bye'), '"say \\"hi\\" \\\\ bye"')

    def test_human_bytes(self):
        self.assertEqual(core.human_bytes(512), "512 B")
        self.assertEqual(core.human_bytes(1536), "1.5 KB")
        self.assertEqual(core.human_bytes(5 * 1024 ** 3), "5.0 GB")

    def test_ago(self):
        self.assertEqual(core.ago(None), "never")
        self.assertEqual(core.ago(time.time() - 7200), "2h ago")

    def test_journal_roundtrip(self):
        core.journal("note", "hello", extra=1)
        core.journal("music", "played x")
        self.assertEqual([e["msg"] for e in core.read_journal()], ["hello", "played x"])
        self.assertEqual(len(core.read_journal(kind="music")), 1)

    def test_cache_ttl(self):
        core.cache_put("thing", {"a": 1})
        self.assertEqual(core.cache_get("thing")["data"], {"a": 1})
        self.assertIsNone(core.cache_get("thing", max_age=-1))
        self.assertIsNone(core.cache_get("missing"))

    def test_config_merges_defaults(self):
        core.config_set("music.storefront", "no")
        cfg = core.config()
        self.assertEqual(cfg["music"]["storefront"], "no")
        self.assertIn("notify", cfg)

    def test_ssl_context_loads(self):
        self.assertIsNotNone(core.ssl_context())



class TestStream(TempHome):
    """core.stream: the runner every headless Claude run goes through, unattended."""

    def py(self, code):
        return [sys.executable, "-c", code]

    def test_lines_arrive_in_order_with_the_input(self):
        lines = []
        r = core.stream(self.py("import sys; print(sys.stdin.read().upper()); print('two')"), lines.append, input="one", timeout=10)
        self.assertEqual((r.rc, [l.strip() for l in lines]), (0, ["ONE", "two"]))

    def test_a_silent_child_is_killed_on_time(self):
        started = time.time()
        r = core.stream(self.py("import time; time.sleep(30)"), lambda l: None, timeout=1)
        self.assertEqual(r.rc, 124)
        self.assertLess(time.time() - started, 8, "the deadline doesn't wait for output")
        self.assertIn("timed out after 1s", r.err)

    def test_a_stderr_flood_does_not_deadlock(self):
        lines = []
        r = core.stream(self.py("import sys\nfor i in range(20000): sys.stderr.write('x' * 100 + '\\n')\nprint('done')"),
                        lines.append, timeout=20)
        self.assertEqual((r.rc, [l.strip() for l in lines]), (0, ["done"]))
        self.assertLessEqual(len(r.err.splitlines()), 40, "only a short tail is kept")

    def test_grandchildren_are_gone_afterwards(self):
        code = ("import subprocess, sys; p = subprocess.Popen(['sleep', '30'], stdout=subprocess.DEVNULL, "
                "stderr=subprocess.DEVNULL); print(p.pid)")
        pids = []
        core.stream(self.py(code), lambda l: pids.append(int(l)), timeout=10)
        self.assertEqual(len(pids), 1)
        for _ in range(40):
            try:
                os.kill(pids[0], 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        self.fail("the grandchild outlived the run")

    def test_a_failing_handler_loses_a_line_not_the_run(self):
        seen = []

        def handler(line):
            seen.append(line.strip())
            if len(seen) == 1:
                raise ValueError("odd line")
        r = core.stream(self.py("print('a'); print('b')"), handler, timeout=10)
        self.assertEqual((r.rc, seen), (0, ["a", "b"]))

    def test_never_raises_for_a_missing_binary(self):
        self.assertEqual(core.stream(["definitely-not-a-binary-xyz"], lambda l: None).rc, 127)


class TestNotifications(TempHome):
    def test_native_notifications_use_the_outbox_not_the_url(self):
        import os
        core.config_set("notify.native", True)
        core.save_json(core.home("state", "notify.json"), {"authorization": "authorized", "ts": 1})
        calls = []
        orig_run, orig_running = core.run, core.app_running
        core.run = lambda cmd, **k: calls.append(cmd) or core.Result(0, "", "")
        core.app_running = lambda name: name == "ClaudeOS"
        try:
            core.notify("Rain likely around 15:00", subtitle="Pulse")
        finally:
            core.run, core.app_running = orig_run, orig_running
        self.assertEqual(calls, [["open", "-g", "claude-os://notify/flush"]], "the link carries no text")
        outbox = core.home("state", "outbox")
        files = os.listdir(str(outbox))
        self.assertEqual(len(files), 1)
        self.assertEqual(oct(os.stat(str(outbox / files[0])).st_mode & 0o777), "0o600")
        self.assertEqual(core.load_json(outbox / files[0])["body"], "Rain likely around 15:00")
        self.assertNotIn("target", core.load_json(outbox / files[0]))

    def test_a_click_target_comes_from_a_fixed_list(self):
        core.config_set("notify.native", True)
        core.save_json(core.home("state", "notify.json"), {"authorization": "authorized", "ts": 1})
        orig_run, orig_running = core.run, core.app_running
        core.run = lambda cmd, **k: core.Result(0, "", "")
        core.app_running = lambda name: name == "ClaudeOS"
        try:
            core.notify("Board minutes", target="board")
            core.notify("odd", target="javascript:alert(1)")
        finally:
            core.run, core.app_running = orig_run, orig_running
        outbox = core.home("state", "outbox")
        notes = [core.load_json(outbox / f) for f in sorted(os.listdir(str(outbox)))]
        self.assertEqual({n["body"]: n.get("target") for n in notes}, {"Board minutes": "board", "odd": None})

    def test_falls_back_when_the_app_is_not_running(self):
        core.config_set("notify.native", True)
        core.save_json(core.home("state", "notify.json"), {"authorization": "authorized", "ts": 1})
        orig = core.app_running
        core.app_running = lambda name: False
        try:
            self.assertFalse(core.native_notifications())
        finally:
            core.app_running = orig


class TestAppLinks(TempHome):
    def test_app_url_carries_the_nonce(self):
        core.home("state", "app.nonce").write_text("n0nce\n")
        url = core.app_url("music/play", id="123", rid="r1")
        self.assertTrue(url.startswith("claude-os://music/play?"))
        self.assertIn("nonce=n0nce", url)
        self.assertIn("id=123", url)


class TestTrends(TempHome):
    def test_one_line_per_day_and_weekly_rate(self):
        from cos import status
        snap = {"disk": {"free": 100 * 2 ** 30}, "battery": {"health_pct": 99, "cycles": 30}}
        self.assertTrue(status.record_trend(snap, today="2026-10-01"))
        self.assertFalse(status.record_trend(snap, today="2026-10-01"), "second write the same day is a no-op")
        for day in range(2, 9):
            snap["disk"]["free"] -= 2 ** 30
            status.record_trend(snap, today="2026-10-%02d" % day)
        rows = status.trends()
        self.assertEqual(len(rows), 8)
        self.assertAlmostEqual(status.disk_trend(rows), -7 * 2 ** 30)
        self.assertIsNone(status.disk_trend(rows[:3]), "no trend from too little data")


if __name__ == "__main__":
    import unittest
    unittest.main()
