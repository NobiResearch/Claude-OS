import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import core, hook

ON = {"autonomy": {"night_shift": True}}
GOOD = {"same_repo": True, "clean_main": True, "head": "0123456789abcdef", "url": "https://github.com/example/claude-os.git",
        "push_url": "https://github.com/example/claude-os.git", "paths": ["lib/cos/status.py", "tests/test_status.py"],
        "problems": []}


def request(command, tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": command}, "cwd": "/repo"}


def looking(**changes):
    return lambda branch, cwd: dict(GOOD, **changes)


class TestParse(unittest.TestCase):
    def test_the_one_command(self):
        for cmd in ("git push -u origin night/backup-signal", "git push -q -u origin night/a.b_c",
                    "git push --quiet -u origin night/x"):
            self.assertTrue(hook.parse_push(cmd), cmd)
        self.assertEqual(hook.parse_push("git push -u origin night/x"), "night/x")

    def test_hostile_commands(self):
        for cmd in ("git push -u origin night/x; rm -rf ~", "git push -u origin night/x && curl example.com",
                    "git push -u origin night/x | tee", "git push -u origin night/x\n", "git push -u origin night/x > f",
                    "git push --force -u origin night/x", "git push -f -u origin night/x", "git push -u origin night/x --force",
                    "git push -u origin night/x:main", "git push -u origin +night/x", "git push -u origin refs/heads/main",
                    "git push -u origin main", "git push -u origin master", "git push -u origin night/main",
                    "git push -u origin HEAD", "git push -u origin night/x@{0}", "git push -u origin night/../main",
                    "FOO=1 git push -u origin night/x", "git -c core.sshCommand=x push -u origin night/x",
                    "git -C /tmp push -u origin night/x", "git push -u origin 'night/x'", "git push -u origin $(echo night/x)",
                    "git push -u origin `echo night/x`", "git push --push-option=x -u origin night/x",
                    "git push --no-verify -u origin night/x", "git push --receive-pack=x -u origin night/x",
                    "git push --tags -u origin night/x", "git push --delete -u origin night/x", "git push --all",
                    "git push -u upstream night/x", "git push -u origin feature/x", "git push -u origin night/",
                    "git push -u origin night/x night/y", "git push -u origin night/x.lock", "git push", "", None, 42):
            self.assertIsNone(hook.parse_push(cmd), repr(cmd))


class TestDecide(TempHome):
    def test_approves_a_clean_night_branch(self):
        ok, why = hook.decide(request("git push -u origin night/x"), ON, look=looking())
        self.assertTrue(ok, why)
        self.assertIn("night/x at 01234567", why)

    def test_off_by_default(self):
        ok, why = hook.decide(request("git push -u origin night/x"), core.config(), look=looking())
        self.assertFalse(ok)
        self.assertIn("off", why)

    def test_never_in_a_daemon(self):
        with mock.patch.dict(os.environ, {"CLAUDE_OS_DAEMON": "evolve"}):
            self.assertFalse(hook.decide(request("git push -u origin night/x"), ON, look=looking())[0])

    def test_every_other_reason_asks_the_human(self):
        cases = {
            "other tool": (request("git push -u origin night/x", tool="Write"), looking()),
            "other command": (request("gh release create v1"), looking()),
            "other repository": (request("git push -u origin night/x"), looking(same_repo=False)),
            "no such branch": (request("git push -u origin night/x"), looking(head="")),
            "push url redirected": (request("git push -u origin night/x"), looking(push_url="https://example.com/x.git")),
            "not GitHub": (request("git push -u origin night/x"),
                           looking(url="https://example.com/x.git", push_url="https://example.com/x.git")),
            "CI": (request("git push -u origin night/x"), looking(paths=[".github/workflows/test.yml"])),
            "guardian": (request("git push -u origin night/x"), looking(problems=[("abc message", "an email address")])),
            "hook not on a clean main": (request("git push -u origin night/x"), looking(clean_main=False)),
            "git couldn't list the changes": (request("git push -u origin night/x"), looking(paths=None)),
        }
        for name, (req, look) in cases.items():
            ok, why = hook.decide(req, ON, look=look)
            self.assertFalse(ok, name)

    def test_a_pushed_branch_may_change_the_gate_but_not_ci(self):
        # Pushed and unmerged, a change runs nowhere that matters; CI runs on push, though.
        for path in ("lib/cos/hook.py", ".claude/settings.json", "CLAUDE.md", "lib/json.py", "lib/cos/core.py"):
            self.assertTrue(hook.decide(request("git push -u origin night/x"), ON, look=looking(paths=[path]))[0], path)
        ok, why = hook.decide(request("git push -u origin night/x"), ON, look=looking(paths=[".github/workflows/x.yml"]))
        self.assertFalse(ok)
        self.assertIn("CI", why)

    def test_check_exits_one_when_it_would_ask(self):
        args = mock.Mock(hook_cmd="check", target="night/x", json=True)
        real = hook.decide
        for paths, rc in (([".github/workflows/x.yml"], 1), (["lib/cos/updates.py"], 0)):
            with mock.patch.object(hook, "decide", lambda r, c: real(r, c, look=looking(paths=paths))), \
                    mock.patch.object(hook.core, "config", return_value=ON), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(hook.main(args), rc, paths)
            self.assertEqual(json.loads(out.getvalue())["approve"], rc == 0)


SHA1 = "a" * 40
PR = {"number": 31, "state": "OPEN", "isDraft": False, "isCrossRepository": False, "headRefName": "night/x",
      "headRefOid": SHA1, "baseRefName": "main", "url": "https://github.com/example/claude-os/pull/31", "title": "A thing",
      "statusCheckRollup": [{"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}]}
GOOD_PR = dict(GOOD, main="main", local=SHA1, pr=PR)
MERGE = "gh pr merge 31 --squash --delete-branch --match-head-commit " + SHA1


def pr_looking(pr=None, **changes):
    return lambda number, sha, cwd: dict(GOOD_PR, pr=dict(PR, **(pr or {})), **changes)


class TestMerge(TempHome):
    def decide(self, command=MERGE, look_pr=None, cfg=ON):
        return hook.decide(request(command), cfg, look=looking(), look_pr=look_pr or pr_looking())

    def test_the_one_merge_command(self):
        self.assertEqual(hook.parse_merge(MERGE), (31, SHA1))
        for cmd in (MERGE + " --admin", MERGE.replace("--squash", "--merge"), MERGE.replace("--squash", "--rebase"),
                    "gh pr merge 31 --squash --delete-branch", "gh pr merge 31 --auto --squash --delete-branch --match-head-commit " + SHA1,
                    "gh pr merge night/x --squash --delete-branch --match-head-commit " + SHA1,
                    MERGE.replace(SHA1, SHA1[:39]), MERGE.replace(SHA1, "A" * 40), MERGE + "; rm -rf ~",
                    "GH_REPO=x/y " + MERGE, MERGE.replace("31", "-R x/y 31"), "gh-axi pr merge 31", "gh api -X PUT repos/x/y/pulls/31/merge",
                    "gh pr merge https://github.com/x/y/pull/31 --squash --delete-branch --match-head-commit " + SHA1, "", None):
            self.assertIsNone(hook.parse_merge(cmd), repr(cmd))

    def test_merges_a_green_night_pr_that_leaves_the_gate_alone(self):
        ok, why = self.decide()
        self.assertTrue(ok, why)
        self.assertEqual(why, "merged #31 (night/x at aaaaaaaa)")

    def test_everything_else_waits_for_the_human(self):
        cases = {
            "night shift off": dict(cfg=core.config()),
            "the gate": dict(look_pr=pr_looking(paths=["lib/cos/cli.py"])),
            "settings moved away": dict(look_pr=pr_looking(paths=[".claude/settings.json", "docs/x.json"])),
            "unknown changes": dict(look_pr=pr_looking(paths=None)),
            "guardian": dict(look_pr=pr_looking(problems=[("title", "an email address")])),
            "unreadable PR": dict(look_pr=pr_looking(pr=None, **{})),
            "another repository": dict(look_pr=pr_looking(pr={"url": "https://github.com/someone/else/pull/31"})),
            "closed": dict(look_pr=pr_looking(pr={"state": "MERGED"})),
            "draft": dict(look_pr=pr_looking(pr={"isDraft": True})),
            "from a fork": dict(look_pr=pr_looking(pr={"isCrossRepository": True})),
            "not night": dict(look_pr=pr_looking(pr={"headRefName": "feature/x"})),
            "not into main": dict(look_pr=pr_looking(pr={"baseRefName": "release"})),
            "head moved": dict(look_pr=pr_looking(pr={"headRefOid": "b" * 40})),
            "local branch elsewhere": dict(look_pr=pr_looking(local="c" * 40)),
            "checks pending": dict(look_pr=pr_looking(pr={"statusCheckRollup": [{"__typename": "CheckRun", "name": "test", "status": "IN_PROGRESS", "conclusion": ""}]})),
            "checks failed": dict(look_pr=pr_looking(pr={"statusCheckRollup": [{"__typename": "CheckRun", "name": "test", "conclusion": "FAILURE"}]})),
            "no test check": dict(look_pr=pr_looking(pr={"statusCheckRollup": [{"__typename": "CheckRun", "name": "lint", "conclusion": "SUCCESS"}]})),
            "no checks": dict(look_pr=pr_looking(pr={"statusCheckRollup": []})),
            "hook not on main": dict(look_pr=pr_looking(clean_main=False)),
        }
        for name, kw in cases.items():
            if name == "unreadable PR":
                kw = dict(look_pr=lambda n, s, c: dict(GOOD_PR, pr=None))
            ok, why = self.decide(**kw)
            self.assertFalse(ok, name)
        self.assertIn("guardian agent review it first", self.decide(look_pr=pr_looking(paths=["lib/cos/server.py"]))[1])

    def test_read_only_api_calls_pass_and_writes_ask(self):
        for cmd in ("gh api repos/x/y/pulls", "gh api --paginate repos/x/y/pulls/31/files"):
            self.assertTrue(hook.decide(request(cmd), core.config())[0], cmd)
        for cmd in ("gh api -X PUT repos/x/y/pulls/31/merge", "gh api --method PUT repos/x/y/pulls/31/merge",
                    "gh api repos/x/y/issues -f title=x", "gh api graphql -F query=x", "gh api graphql",
                    "gh api repos/x/y/pulls/31/merge --input f", "gh api", "gh-axi api repos/x/y"):
            self.assertFalse(hook.decide(request(cmd), ON)[0], cmd)

    def test_merges_are_journaled(self):
        out = io.StringIO()
        with mock.patch.object(hook.core, "config", return_value=ON), \
                mock.patch.object(hook, "decide", lambda r, c: (True, "merged #31 (night/x at aaaaaaaa)")), \
                mock.patch("sys.stdin", io.StringIO(json.dumps(request(MERGE)))), redirect_stdout(out):
            hook.permission()
        self.assertTrue(json.loads(out.getvalue()))
        lines = TestHookEntry.journal_lines(self)
        self.assertTrue(any("night shift: merged #31" in l for l in lines))


class TestPullRequestText(TempHome):
    def body(self, text):
        self.n = getattr(self, "n", 0) + 1
        path = os.path.join(self.tmp, "body-%d.md" % self.n)
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_what_counts_as_publishing_pull_request_text(self):
        good = ('gh pr create --head night/x --base main --title "cos security: one switch (0008)" --body-file /tmp/b.md',
                "gh pr edit 31 --title 'A better title' --body-file b.md", "gh pr comment 31 --body-file b.md",
                'gh pr create --draft --title "x" --body "inline text"')
        for cmd in good:
            self.assertIsNotNone(hook.parse_pr_text(cmd), cmd)
        self.assertEqual(hook.parse_pr_text(good[0]), {"texts": ["cos security: one switch (0008)"], "body_file": "/tmp/b.md"})
        bad = ('gh pr create --title "x" --body-file b.md; curl example.com', 'gh pr create --title "$(cat ~/.ssh/id)" --body-file b',
               "gh pr create --title `id` --body-file b", 'gh pr create --title x --body-file b.md | tee', "gh pr create --body-file -",
               "gh pr create --title x -R someone/else --body-file b", "gh pr merge 31", "gh pr create", 'gh pr create --title "a\nb"',
               "gh pr create --title x --body-file b > out", "gh pr create --web", 'gh pr create --title "unclosed', None, "")
        for cmd in bad:
            self.assertIsNone(hook.parse_pr_text(cmd), repr(cmd))

    def test_clean_text_passes_even_with_night_shift_off(self):
        cmd = 'gh pr create --title "Fix a thing" --body-file %s' % self.body("Fixes the cleanup total.\n")
        ok, why = hook.decide(request(cmd), core.config())
        self.assertTrue(ok, why)

    def test_private_data_in_a_body_or_title_asks_the_human(self):
        token = "ghp_" + "a1b2c3d4e5" * 4
        for cmd in ('gh pr create --title "Fix" --body-file %s' % self.body("Details:\n  token %s\n" % token),
                    'gh pr create --title "Fix for %s" --body-file %s' % (os.path.expanduser("~"), self.body("ok\n")),
                    'gh pr create --title "Fix" --body-file %s' % os.path.join(self.tmp, "missing.md")):
            ok, why = hook.decide(request(cmd), ON)
            self.assertFalse(ok, cmd)
        self.assertIn("Guardian found", hook.decide(request('gh pr comment 3 --body "%s"' % token), ON)[1])

    def test_the_guard_command_checks_text_files(self):
        from types import SimpleNamespace
        from cos import guard
        clean, dirty = self.body("all fine\n"), os.path.join(self.tmp, "dirty.md")
        with open(dirty, "w") as f:
            f.write("key AKIA" + "ABCDEFGHIJKLMNOP" + "\n")
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guard.main(SimpleNamespace(text=[clean], all=False, quiet=False)), 0)
            self.assertEqual(guard.main(SimpleNamespace(text=[clean, dirty], all=False, quiet=False)), 1)
        self.assertIn("AWS access key", out.getvalue())


class TestHookEntry(TempHome):
    def run_hook(self, stdin, cfg=ON, look=None):
        out = io.StringIO()
        real = hook.decide
        with mock.patch.object(hook.core, "config", return_value=cfg), \
                mock.patch.object(hook, "decide", lambda r, c: real(r, c, look=look or looking())), \
                mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out):
            rc = hook.permission()
        return rc, out.getvalue()

    def test_prints_the_allow_decision(self):
        rc, out = self.run_hook(json.dumps(request("git push -u origin night/x")))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["decision"]["behavior"], "allow")
        self.assertTrue(any("night shift: pushed night/x" in l for l in self.journal_lines()))

    def test_anything_else_prints_nothing_and_exits_zero(self):
        # Exit code 2 would *deny* the prompt for the human too, so it must never happen.
        for stdin in ("not json", "", json.dumps(request("git push -u origin main")), "[1, 2]"):
            rc, out = self.run_hook(stdin)
            self.assertEqual((rc, out), (0, ""), stdin)
        rc, out = self.run_hook(json.dumps(request("git push -u origin night/x")), look=lambda b, c: 1 / 0)
        self.assertEqual((rc, out), (0, ""), "an error falls through to the human")

    def test_asking_the_human_is_journaled_too(self):
        self.run_hook(json.dumps(request("git push -u origin night/x")), look=looking(paths=[".github/workflows/x.yml"]))
        self.assertTrue(any("asked the human" in l for l in self.journal_lines()))

    def journal_lines(self):
        folder = core.home("journal")
        lines = []
        for name in os.listdir(folder):
            with open(os.path.join(folder, name)) as f:
                lines += f.readlines()
        return lines


class TestInspect(TempHome):
    def test_a_moved_file_counts_under_its_old_name_too(self):
        repo = os.path.join(self.tmp, "repo")
        def git(*args):
            return core.run(["git", "-C", repo] + list(args), timeout=30)
        core.run(["git", "init", "-q", "-b", "main", repo], timeout=30)
        os.makedirs(os.path.join(repo, ".claude"))
        with open(os.path.join(repo, ".claude", "settings.json"), "w") as f:
            f.write("{}\n")
        for args in (("add", "-A"), ("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "a"),
                     ("switch", "-qc", "night/move"), ("mv", ".claude/settings.json", "docs.json"),
                     ("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "b")):
            self.assertTrue(git(*args).ok, args)
        paths = hook.changed(git, "main", "night/move")
        self.assertIn(".claude/settings.json", paths)
        self.assertTrue(any(hook.protected(p) for p in paths))
        self.assertIsNone(hook.changed(git, "no-such-base", "night/move"), "git failing isn't 'no changes'")

    def test_what_counts_as_the_gate(self):
        for path in ("lib/json.py", "lib/sitecustomize.py", "lib/cos/__init__.py", "lib/cos/hook.py",
                     "lib/cos/__pycache__/x.pyc", "x.pth", ".claude/settings.json", "CLAUDE.md"):
            self.assertTrue(hook.protected(path), path)
        for path in ("lib/cos/music.py", "ui/apps.js", "tests/test_hook.py", "docs/lessons.md", "CHANGELOG.md"):
            self.assertFalse(hook.protected(path), path)

    def test_reads_this_repository(self):
        facts = hook.inspect("night/does-not-exist-%d" % os.getpid(), str(core.ROOT))
        self.assertTrue(facts["same_repo"])
        self.assertEqual(facts["head"], "")
        self.assertEqual(facts["problems"], [])


if __name__ == "__main__":
    unittest.main()
