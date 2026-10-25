import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import core, hook

ON = {"autonomy": {"night_shift": True}}
GOOD = {"same_repo": True, "head": "0123456789abcdef", "url": "https://github.com/example/claude-os.git",
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
            "safety files": (request("git push -u origin night/x"), looking(paths=["lib/cos/hook.py"])),
            "settings": (request("git push -u origin night/x"), looking(paths=[".claude/settings.json"])),
            "the laws": (request("git push -u origin night/x"), looking(paths=["CLAUDE.md"])),
            "CI": (request("git push -u origin night/x"), looking(paths=[".github/workflows/test.yml"])),
            "guardian": (request("git push -u origin night/x"), looking(problems=[("abc message", "an email address")])),
        }
        for name, (req, look) in cases.items():
            ok, why = hook.decide(req, ON, look=look)
            self.assertFalse(ok, name)

    def test_the_code_the_gate_leans_on_waits_for_the_human(self):
        # Merged on one night, a change here would loosen the checks for the next.
        for path in ("lib/cos/core.py", "lib/cos/cli.py", "lib/cos/evolve.py", "lib/cos/server.py"):
            ok, why = hook.decide(request("git push -u origin night/x"), ON, look=looking(paths=["ui/apps.js", path]))
            self.assertFalse(ok, path)
            self.assertIn("waits for the human", why)
            self.assertIn(path, why)
        self.assertTrue(hook.decide(request("git push -u origin night/x"), ON, look=looking(paths=["lib/cos/updates.py"]))[0])

    def test_check_exits_one_when_it_would_ask(self):
        args = mock.Mock(hook_cmd="check", branch="night/x", json=True)
        real = hook.decide
        for paths, rc in ((["lib/cos/evolve.py"], 1), (["lib/cos/updates.py"], 0)):
            with mock.patch.object(hook, "decide", lambda r, c: real(r, c, look=looking(paths=paths))), \
                    mock.patch.object(hook.core, "config", return_value=ON), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(hook.main(args), rc, paths)
            self.assertEqual(json.loads(out.getvalue())["approve"], rc == 0)


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
        self.run_hook(json.dumps(request("git push -u origin night/x")), look=looking(paths=["CLAUDE.md"]))
        self.assertTrue(any("asked the human" in l for l in self.journal_lines()))

    def journal_lines(self):
        folder = core.home("journal")
        lines = []
        for name in os.listdir(folder):
            with open(os.path.join(folder, name)) as f:
                lines += f.readlines()
        return lines


class TestInspect(unittest.TestCase):
    def test_reads_this_repository(self):
        facts = hook.inspect("night/does-not-exist-%d" % os.getpid(), str(core.ROOT))
        self.assertTrue(facts["same_repo"])
        self.assertEqual(facts["head"], "")
        self.assertEqual(facts["problems"], [])


if __name__ == "__main__":
    unittest.main()
