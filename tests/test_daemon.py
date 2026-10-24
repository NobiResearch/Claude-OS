import unittest

from helpers import TempHome

from cos import daemon


class TestDaemons(TempHome):
    def test_definitions_are_complete(self):
        defs = daemon.definitions()
        self.assertIn("pulse", defs)
        for name, spec in defs.items():
            self.assertIn("description", spec, name)
            self.assertIn("schedule", spec, name)
            self.assertTrue(("prompt" in spec) != ("builtin" in spec), "%s: prompt xor builtin" % name)
            if "prompt" in spec:
                self.assertIn("budget_usd", spec, "%s: LLM daemons need a budget cap" % name)

    def test_interval_plist(self):
        p = daemon.build_plist("pulse", {"schedule": {"every_minutes": 120}}, root="/opt/cos", path_env="/usr/bin")
        self.assertEqual(p["Label"], "com.claude-os.pulse")
        self.assertEqual(p["StartInterval"], 7200)
        self.assertEqual(p["ProgramArguments"][2:], ["/opt/cos/bin/cos", "daemon", "run", "pulse"])
        self.assertEqual(p["EnvironmentVariables"]["PATH"], "/usr/bin")

    def test_calendar_plist(self):
        p = daemon.build_plist("board", {"schedule": {"weekday": 0, "hour": 10, "minute": 5}}, root="/x")
        self.assertEqual(p["StartCalendarInterval"], {"Hour": 10, "Minute": 5, "Weekday": 0})

    def test_schedule_descriptions(self):
        self.assertEqual(daemon.describe_schedule({"every_minutes": 120}), "every 2h")
        self.assertEqual(daemon.describe_schedule({"hour": 8, "minute": 0}), "daily 08:00")
        self.assertEqual(daemon.describe_schedule({"weekday": 0, "hour": 10}), "Sun 10:00")

    def test_headless_runs_can_never_mutate_or_publish(self):
        for name, spec in daemon.definitions().items():
            if "prompt" not in spec:
                continue
            cmd = daemon.claude_command(spec)
            denied = cmd[cmd.index("--disallowedTools") + 1:]
            for must in ("Bash(git push*)", "Bash(bin/cos clean apply*)", "Bash(bin/cos update apply*)"):
                self.assertIn(must, denied, name)
            self.assertIn("--max-budget-usd", cmd)
            self.assertNotEqual(spec.get("permission_mode"), "bypassPermissions", name)


if __name__ == "__main__":
    unittest.main()
