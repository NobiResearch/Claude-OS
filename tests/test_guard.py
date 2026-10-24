import os
import unittest

from helpers import REAL_HOME, TempHome

from cos import guard


class TestGuard(TempHome):
    def test_blocks_private_paths(self):
        bad = ["var/journal.jsonl", ".claude-os/memory.md", ".env", ".env.local", "keys/server.pem",
               ".ssh/id_ed25519", ".claude/settings.local.json", "notes/friction.json"]
        good = ["README.md", "lib/cos/mem.py", "docs/lessons.md", ".claude/settings.json", "etc/feeds.txt"]
        flagged = {p for p, _ in guard.check_paths(bad + good)}
        self.assertEqual(flagged, set(bad))

    def test_detects_secrets(self):
        fake = "sk-ant-" + "a" * 30
        problems = guard.check_text("x.py", "key = '%s'\nok = 1\n" % fake, guard.SECRET_PATTERNS)
        self.assertEqual(problems, [("x.py", "line 1: Anthropic API key")])
        self.assertEqual(guard.check_text("y.py", "nothing here", guard.SECRET_PATTERNS), [])

    def test_detects_this_users_home_path(self):
        home = os.path.expanduser("~")
        problems = guard.scan(["a.md"], lambda p: "see %s/Music for details" % home)
        self.assertTrue(any("home folder" in why for _, why in problems))

    def test_new_key_formats_and_paths(self):
        text = "a=sk-proj-%s b=github_pat_%s" % ("A" * 40, "b" * 30)
        found = {why for _, why in guard.check_text("f", text, guard.SECRET_PATTERNS)}
        self.assertEqual(found, {"line 1: OpenAI-style key", "line 1: GitHub fine-grained token"})
        self.assertEqual(len(guard.check_paths([".envrc", "a/.npmrc", "AuthKey_X.p8"])), 3)

    def test_machine_generated_emails_are_caught(self):
        for bad in ("<someone@Some-MacBook-Air.local>", "<x@box.lan>", "<(none)>"):
            self.assertTrue(guard.LOCAL_EMAIL.search(bad), bad)
        for ok in ("<123+someone@users.noreply.github.com>", "<me@example.com>"):
            self.assertFalse(guard.LOCAL_EMAIL.search(ok), ok)

    def test_repository_is_clean(self):
        """The real repo must never contain secrets or this machine's personal paths."""
        from cos import core
        os.environ["HOME"] = REAL_HOME  # check against the real home path, not the temp one
        tracked = guard.publishable()

        def read(p):
            try:
                with open(os.path.join(str(core.ROOT), p), errors="replace") as f:
                    return f.read()
            except OSError:
                return ""
        self.assertEqual(guard.scan(tracked, read), [])


if __name__ == "__main__":
    unittest.main()
