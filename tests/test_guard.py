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


class TestPrePush(TempHome):
    """githooks/pre-push: a temporary origin and clone; what a push would publish."""

    def setUp(self):
        super().setUp()
        import subprocess
        self.subprocess = subprocess
        self.origin = os.path.join(self.tmp, "origin.git")
        self.repo = os.path.join(self.tmp, "repo")
        self.git("init", "--quiet", "--bare", "-b", "main", self.origin, cwd=self.tmp)
        self.git("clone", "--quiet", self.origin, self.repo, cwd=self.tmp)
        self.commit("README.md", "hello\n")
        self.git("push", "--quiet", "origin", "main")
        self.git("remote", "set-head", "origin", "main")
        self.git("checkout", "--quiet", "-b", "night/x")

    def git(self, *args, cwd=None, email="1+someone@users.noreply.github.com"):
        env = dict(os.environ, GIT_AUTHOR_NAME="Someone", GIT_AUTHOR_EMAIL=email,
                   GIT_COMMITTER_NAME="Someone", GIT_COMMITTER_EMAIL=email)
        r = self.subprocess.run(["git"] + list(args), cwd=cwd or self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commit(self, path, text, message="A change", email="1+someone@users.noreply.github.com"):
        with open(os.path.join(self.repo, path), "w") as f:
            f.write(text)
        self.git("add", path)
        self.git("commit", "--quiet", "-m", message, email=email)
        return self.git("rev-parse", "HEAD")

    def pushed(self, sha, remote="0" * 40):
        line = "refs/heads/night/x %s refs/heads/night/x %s\n" % (sha, remote)
        return guard.push_problems(guard.push_ranges(line, "origin/main"), cwd=self.repo)

    def test_a_clean_push_passes(self):
        self.assertEqual(self.pushed(self.commit("notes.md", "fine\n")), [])

    def test_a_secret_in_any_pushed_commit_blocks_it_even_if_a_later_one_removes_it(self):
        key = "AKIA" + "Q" * 16
        self.commit("config.txt", "key = %s\n" % key)
        last = self.commit("config.txt", "key = (removed)\n")
        problems = self.pushed(last)
        self.assertTrue(any("AWS access key" in why for _, why in problems), problems)

    def test_a_secret_in_a_commit_message_blocks_it(self):
        sha = self.commit("notes.md", "fine\n", message="token ghp_" + "a" * 36)
        self.assertTrue(any("message" in where for where, _ in self.pushed(sha)))

    def test_only_noreply_addresses_are_published(self):
        sha = self.commit("notes.md", "fine\n", email="someone@example.com")
        problems = self.pushed(sha)
        self.assertEqual([where.split()[1] for where, _ in problems], ["author", "committer"])

    def test_deletions_publish_nothing_and_an_unknown_remote_tip_is_checked_from_main(self):
        self.assertEqual(guard.push_ranges("refs/heads/x %s refs/heads/x %s\n" % ("0" * 40, "a" * 40), "origin/main"), [])
        sha = self.commit("notes.md", "fine\n", email="someone@example.com")
        self.assertTrue(self.pushed(sha, remote="b" * 40), "a force push past an unknown tip is still checked")

    def test_it_fails_closed(self):
        import io
        from contextlib import redirect_stderr
        from unittest import mock
        from types import SimpleNamespace
        with mock.patch.object(guard, "push_problems", side_effect=RuntimeError("boom")), \
                mock.patch("sys.stdin", io.StringIO("")), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(guard.main(SimpleNamespace(push=True, text=None, all=False, quiet=False)), 1)
        self.assertIn("couldn't check it", err.getvalue())

    def test_the_hook_is_installed_beside_pre_commit(self):
        hook = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "githooks", "pre-push")
        self.assertTrue(os.access(hook, os.X_OK))
        with open(hook) as f:
            self.assertIn("guard --push", f.read())


if __name__ == "__main__":
    unittest.main()
