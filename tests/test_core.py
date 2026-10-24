import os
import time

from helpers import TempHome

from cos import core


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

    def test_falls_back_when_the_app_is_not_running(self):
        core.config_set("notify.native", True)
        core.save_json(core.home("state", "notify.json"), {"authorization": "authorized", "ts": 1})
        orig = core.app_running
        core.app_running = lambda name: False
        try:
            self.assertFalse(core.native_notifications())
        finally:
            core.app_running = orig


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
