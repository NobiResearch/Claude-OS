import io
import os
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import core, evolve, shell, updates

GITHUB = {"GIT_COMMITTER_NAME": "GitHub", "GIT_COMMITTER_EMAIL": "noreply@github.com"}
PERSON = {"GIT_AUTHOR_NAME": "A Person", "GIT_AUTHOR_EMAIL": "person@example.com",
          "GIT_COMMITTER_NAME": "A Person", "GIT_COMMITTER_EMAIL": "person@example.com"}


class Repos(TempHome):
    """A bare `origin`, the live checkout cloned from it, and a second clone standing in for
    GitHub's merge button. origin isn't GitHub, so that one check is stubbed out here and
    tested on its own."""
    stub_origin = True

    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.tmp, "origin.git")
        self.live = os.path.join(self.tmp, "live")
        self.hub = os.path.join(self.tmp, "hub")
        self.sh("git", "init", "--quiet", "--bare", "-b", "main", self.origin)
        self.sh("git", "clone", "--quiet", self.origin, self.hub)
        self.merge("Start (#1)", "README.md")
        self.sh("git", "clone", "--quiet", self.origin, self.live)
        if self.stub_origin:
            stub = mock.patch.object(evolve, "_origin_problem", return_value=None)
            stub.start()
            self.addCleanup(stub.stop)

    def sh(self, *cmd, cwd=None, env=None):
        full = dict(os.environ, **PERSON)
        full.update(env or {})
        r = subprocess.run(cmd, cwd=cwd, env=full, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def merge(self, subject, path, text="x\n", committer=GITHUB, mode=None):
        """A commit on main the way GitHub's squash merge makes one, pushed to origin."""
        full = os.path.join(self.hub, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
        if mode:
            os.chmod(full, mode)
        self.sh("git", "add", "-A", cwd=self.hub)
        self.sh("git", "commit", "--quiet", "-m", subject, cwd=self.hub, env=committer)
        self.sh("git", "push", "--quiet", "origin", "main", cwd=self.hub)

    def head(self):
        return self.sh("git", "rev-parse", "HEAD", cwd=self.live)

    def catch_up(self, **kw):
        kw.setdefault("fetch", "force")
        return evolve.catch_up(cwd=self.live, **kw)


class TestCatchUp(Repos):
    def test_it_reports_what_merged_without_moving_anything(self):
        before = self.head()
        self.merge("cos net (#42)", "lib/cos/net.py")
        self.merge("Fix the banner (#43)", "lib/cos/shell.py")
        c = self.catch_up()
        self.assertEqual((c["behind"], c["ahead"], c["why"], c["updated"]), (2, 0, None, False))
        self.assertEqual(c["subjects"], ["Fix the banner (#43)", "cos net (#42)"])
        self.assertEqual(self.head(), before)
        self.assertEqual(core.cache_get("catch-up")["data"]["behind"], 2, "the boot banner reads this")

    def test_it_fast_forwards_a_clean_main_and_journals_the_way_back(self):
        before = self.head()
        self.merge("cos net (#42)", "lib/cos/net.py")
        c = self.catch_up(apply=True)
        self.assertTrue(c["updated"])
        self.assertEqual(self.head(), self.sh("git", "rev-parse", "HEAD", cwd=self.hub))
        entry = core.read_journal(days=1)[-1]
        self.assertEqual(entry["undo"], "git reset --keep %s" % before)
        self.assertEqual(entry["subjects"], ["cos net (#42)"])
        self.assertEqual(self.catch_up()["behind"], 0)

    def test_it_never_moves_a_dirty_tree_another_branch_or_local_commits(self):
        self.merge("cos net (#42)", "lib/cos/net.py")
        with open(os.path.join(self.live, "README.md"), "a") as f:
            f.write("an edit in progress\n")
        self.assertIn("uncommitted", self.catch_up(apply=True)["why"])
        self.sh("git", "checkout", "--quiet", "--", "README.md", cwd=self.live)

        self.sh("git", "checkout", "--quiet", "-b", "mine", cwd=self.live)
        self.assertIn("isn't on main", self.catch_up(apply=True)["why"])
        self.sh("git", "checkout", "--quiet", "main", cwd=self.live)

        with open(os.path.join(self.live, "notes.md"), "w") as f:
            f.write("local\n")
        self.sh("git", "add", "notes.md", cwd=self.live)
        self.sh("git", "commit", "--quiet", "-m", "local work", cwd=self.live)
        before = self.head()
        c = self.catch_up(apply=True)
        self.assertEqual((c["ahead"], c["behind"]), (1, 1))
        self.assertIn("1 commit GitHub hasn't got", c["why"])
        self.assertEqual(self.head(), before, "never rebased, never reset")

    def test_not_over_a_commit_pushed_straight_to_main(self):
        self.merge("pushed straight to main", "lib/cos/x.py")
        c = self.catch_up(apply=True)
        self.assertFalse(c["updated"])
        self.assertIn("didn't come from a GitHub pull request merge", c["why"])

    def test_not_over_a_commit_github_didnt_make(self):
        self.merge("Looks merged (#44)", "lib/cos/y.py", committer=PERSON)
        c = self.catch_up(apply=True)
        self.assertFalse(c["updated"])
        self.assertIn("didn't come from a GitHub pull request merge", c["why"])

    def test_it_names_the_gate_when_it_changes(self):
        self.merge("Tighten the hook (#45)", "lib/cos/hook.py")
        self.merge("Docs (#46)", "docs/x.md")
        c = self.catch_up()
        self.assertEqual(c["protected"], ["lib/cos/hook.py"])
        with mock.patch.object(evolve, "catch_up", return_value=c):
            line = shell._catch_up_line()
        self.assertIn("2 changes merged on GitHub", line)
        self.assertIn("the gate changes too: lib/cos/hook.py", line)
        self.assertIn("cos update apply claude-os --yes", line)

    def test_nothing_from_the_incoming_tree_runs(self):
        # The live checkout uses core.hooksPath=githooks (relative), so a merged
        # githooks/post-merge would run on the fast-forward if git were allowed hooks.
        self.sh("git", "config", "core.hooksPath", "githooks", cwd=self.live)
        marker = os.path.join(self.tmp, "hook-ran")
        self.merge("A hook (#47)", "githooks/post-merge", "#!/bin/sh\ntouch %s\n" % marker, mode=0o755)
        self.assertTrue(self.catch_up(apply=True)["updated"])
        self.assertFalse(os.path.exists(marker))

    def test_the_fetch_is_throttled_hardened_and_its_failure_isnt_fatal(self):
        real, fetches = core.run, []

        def spy(cmd, **kw):
            if "fetch" in cmd:
                fetches.append((cmd, kw))
            return real(cmd, **kw)
        self.merge("cos net (#42)", "lib/cos/net.py")
        with mock.patch.object(core, "run", spy):
            self.assertEqual(self.catch_up(fetch=True)["behind"], 1)
            self.catch_up(fetch=True)
            self.catch_up(fetch=False)
        self.assertEqual(len(fetches), 1, "at most one fetch every 10 minutes")
        cmd, kw = fetches[0]
        for flag in ("core.hooksPath=/dev/null", "credential.helper=", "--no-tags", "--no-recurse-submodules"):
            self.assertIn(flag, cmd)
        self.assertEqual(kw["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertLessEqual(kw["timeout"], 4)

        self.sh("git", "remote", "set-url", "origin", os.path.join(self.tmp, "gone.git"), cwd=self.live)
        c = self.catch_up()
        self.assertFalse(c["fetched"])
        self.assertEqual(c["behind"], 1, "what it fetched before still counts")

    def test_a_background_job_never_moves_the_code(self):
        self.merge("cos net (#42)", "lib/cos/net.py")
        os.environ["CLAUDE_OS_DAEMON"] = "pulse"
        try:
            c = self.catch_up(apply=True)
        finally:
            del os.environ["CLAUDE_OS_DAEMON"]
        self.assertFalse(c["updated"])
        self.assertIn("background job", c["why"])


class TestOrigin(Repos):
    stub_origin = False

    def test_only_github_and_no_url_rewrites(self):
        self.assertIn("isn't a GitHub repository", evolve._origin_problem(self.live))
        self.sh("git", "remote", "set-url", "origin", "https://github.com/example/claude-os.git", cwd=self.live)
        self.assertIsNone(evolve._origin_problem(self.live))
        self.sh("git", "config", "url.%s.insteadOf" % self.origin, "https://github.com/", cwd=self.live)
        self.assertIn("insteadOf", evolve._origin_problem(self.live))


class TestUpdateSource(Repos):
    def test_claude_os_is_an_update_source_and_apply_asks_first(self):
        self.merge("cos net (#42)", "lib/cos/net.py")
        real = evolve.catch_up
        with mock.patch.object(evolve, "catch_up", lambda **kw: real(cwd=self.live, **kw)):
            src = updates.check_claude_os()
            self.assertEqual(src["items"][0]["changes"], ["cos net (#42)"])
            with redirect_stdout(io.StringIO()) as out:
                updates.render_claude_os(src)
                self.assertEqual(updates.apply("claude-os", [], yes=False), 2)
            self.assertIn("1 change merged on GitHub", out.getvalue())
            self.assertNotEqual(self.head(), self.sh("git", "rev-parse", "HEAD", cwd=self.hub))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(updates.apply("claude-os", [], yes=True), 0)
            self.assertIn("✓ Claude OS is at", out.getvalue())
            self.assertEqual(self.head(), self.sh("git", "rev-parse", "HEAD", cwd=self.hub))


if __name__ == "__main__":
    unittest.main()
