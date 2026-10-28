import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import cli, core, power

SAMPLE = """2026-10-28 13:00:00 +0100
Assertion status system-wide:
   BackgroundTask                 0
   PreventUserIdleDisplaySleep    1
   PreventSystemSleep             0
   PreventUserIdleSystemSleep     1
Listed by owning process:
   pid 1234(caffeinate): [0x0000000100001234] 00:42:10 PreventUserIdleSystemSleep named: "caffeinate -i"
   pid 5678(exampleapp): [0x0000000100005678] 01:05:00 PreventUserIdleDisplaySleep named: "Playing example video"
   pid 9999(exampleapp): [0x0000000100009999] NoIdleSleepAssertion named: "com.example.audio.noidlesleep"
   pid 1111(exampleapp): [0x0000000100001111] 00:00:30 PreventSystemSleep named: "Example download"
"""


class TestPower(TempHome):
    def test_parse_sample_returns_three_holders(self):
        holders = power.parse_assertions(SAMPLE)
        self.assertEqual(len(holders), 3)
        self.assertEqual(
            [(h["pid"], h["process"], h["assertion"], h["duration_seconds"]) for h in holders],
            [(1234, "caffeinate", "PreventUserIdleSystemSleep", 2530),
             (5678, "exampleapp", "PreventUserIdleDisplaySleep", 3900),
             (1111, "exampleapp", "PreventSystemSleep", 30)])

    def test_non_target_assertions_ignored(self):
        self.assertNotIn("NoIdleSleepAssertion",
                         [h["assertion"] for h in power.parse_assertions(SAMPLE)])

    def test_three_digit_hour_duration(self):
        # pmset's %02d hour field is a minimum width: hours keep counting
        # past 99, so a holder at 123 hours must still parse.
        holders = power.parse_assertions(
            '   pid 4321(exampleapp): [0x0000000100004321] 123:04:05 '
            'PreventSystemSleep named: "x"\n')
        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0]["duration_seconds"], 443045)

    def test_duration_and_process_optional(self):
        holders = power.parse_assertions(
            '   pid 194: [0x0000000100000194] PreventUserIdleSystemSleep named: "named-token-12345"\n')
        self.assertEqual(len(holders), 1)
        self.assertIsNone(holders[0]["process"])
        self.assertIsNone(holders[0]["duration"])
        self.assertIsNone(holders[0]["duration_seconds"])

    def test_empty_and_garbage_and_none(self):
        self.assertEqual(power.parse_assertions(""), [])
        self.assertEqual(power.parse_assertions("not pmset output at all"), [])
        self.assertEqual(power.parse_assertions(None), [])

    def test_no_holders_render_and_json(self):
        r = {"holders": [], "preventing": False, "available": True}
        out = io.StringIO()
        with redirect_stdout(out):
            power.render(r)
        self.assertIn("Nothing is keeping the Mac awake", out.getvalue())

    def test_check_unavailable_when_pmset_missing(self):
        with mock.patch.object(power.core, "run",
                               return_value=core.Result(127, "", "not found")):
            r = power.check()
        self.assertEqual(r, {"holders": [], "preventing": False, "available": False})

    def test_check_with_sample(self):
        with mock.patch.object(power.core, "run",
                               return_value=core.Result(0, SAMPLE, "")):
            r = power.check()
        self.assertTrue(r["available"])
        self.assertTrue(r["preventing"])
        self.assertEqual(len(r["holders"]), 3)

    def test_cli_dispatch_text_and_json(self):
        with mock.patch.object(power.core, "run",
                               return_value=core.Result(0, SAMPLE, "")):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.main(["power"])
            self.assertEqual(rc, 0)
            self.assertIn("caffeinate", out.getvalue())
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cli.main(["power", "--json"])
            self.assertEqual(rc, 0)
            data = json.loads(out.getvalue())
            self.assertEqual(len(data["holders"]), 3)

    def test_named_string_never_leaks(self):
        with mock.patch.object(power.core, "run",
                               return_value=core.Result(0, SAMPLE, "")):
            r = power.check()
            out = io.StringIO()
            with redirect_stdout(out):
                power.render(r)
            self.assertNotIn("caffeinate -i", out.getvalue())
            self.assertNotIn("Playing example video", out.getvalue())
            self.assertNotIn("named-token", json.dumps(r))


if __name__ == "__main__":
    unittest.main()
