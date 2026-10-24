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


if __name__ == "__main__":
    import unittest
    unittest.main()
