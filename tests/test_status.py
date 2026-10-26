import plistlib
import time
import unittest
from unittest import mock

from helpers import TempHome

from cos import core, status

NONE_SET = plistlib.dumps({}).decode()
ONE_SET = plistlib.dumps({"Destinations": [{"ID": "00000000-0000-0000-0000-000000000000", "Kind": "Local",
                                            "Name": "Example Backups"}]}).decode()
VITALS = {"disk": {"free": 500 * 2 ** 30, "free_pct": 50}, "memory": {"swap_used": 0}, "battery": None,
          "security": {}, "uptime": 3600}


class TestBackupSignal(TempHome):
    def test_parse_destinationinfo(self):
        self.assertEqual(status.parse_backup(NONE_SET), {"configured": False}, "an empty dict: not set up")
        self.assertEqual(status.parse_backup(ONE_SET), {"configured": True})
        self.assertNotIn("Example", str(status.parse_backup(ONE_SET)), "destination names never leave tmutil")
        for garbage in ("", "tmutil: No destinations configured.", "<plist><array/></plist>",
                        plistlib.dumps({"Other": 1}).decode()):
            self.assertIsNone(status.parse_backup(garbage), garbage)

    def test_a_failing_tmutil_is_unknown(self):
        with mock.patch.object(status.core, "run", return_value=core.Result(1, "", "tmutil: failed")):
            self.assertIsNone(status.backup())
        with mock.patch.object(status.core, "run", return_value=core.Result(0, NONE_SET, "")) as run:
            self.assertEqual(status.backup(), {"configured": False})
        self.assertEqual(run.call_args[0][0], ["tmutil", "destinationinfo", "-X"], "nothing that mounts a volume")

    def backup_notes(self):
        return [m for _, m in status.signals(VITALS) if "Time Machine" in m]

    def test_a_quiet_note_only_when_not_set_up(self):
        self.assertEqual(self.backup_notes(), [], "no cache, no signal")
        core.cache_put("backup", {"configured": False})
        self.assertIn(("note", "Time Machine isn't set up: cos backup"), status.signals(VITALS), "a note, never a warning")
        core.cache_put("backup", {"configured": True})
        self.assertEqual(self.backup_notes(), [])
        core.cache_put("backup", None)
        self.assertEqual(self.backup_notes(), [], "unknown is no signal")

    def test_backup_check_turns_it_off(self):
        core.cache_put("backup", {"configured": False})
        core.config_set("pulse.backup_check", False)
        self.assertEqual(self.backup_notes(), [])
        with mock.patch.object(status, "backup") as backup:
            status.refresh_backup(max_age=0)
        backup.assert_not_called()

    def test_refresh_is_daily(self):
        with mock.patch.object(status, "backup", return_value={"configured": False}) as backup:
            status.refresh_backup()
            status.refresh_backup()
            self.assertEqual(backup.call_count, 1, "a fresh cache isn't refreshed")
            status.refresh_backup(max_age=0)
            self.assertEqual(backup.call_count, 2)
        self.assertEqual(core.cache_get("backup")["data"], {"configured": False})


class TestWeatherSignal(TempHome):
    def weather_notes(self, first_hour_started):
        now = time.time()
        core.cache_put("weather", {"alert": {"level": "note", "msg": "rain likely around 02:00 (93%)"}, "hours": [
            {"time": "02:00", "ts": now - first_hour_started, "pp": 93, "code": 61},
            {"time": "03:00", "ts": now - first_hour_started + 3600, "pp": 10, "code": 3}]})
        return [m for _, m in status.signals(VITALS) if m.startswith("Rain")]

    def test_rain_at_an_hour_that_is_over_is_no_signal(self):
        self.assertEqual(self.weather_notes(first_hour_started=40 * 60), ["Rain likely around 02:00 (93%)"])
        self.assertEqual(self.weather_notes(first_hour_started=90 * 60), [], "the boot banner at 03:30")


PS = """  101  12.5 2048000 /Applications/Firefox.app/Contents/MacOS/firefox
  102   3.0 1024000 /Applications/Firefox.app/Contents/MacOS/plugin-container.app/Contents/MacOS/plugin-container
  103   0.5 3072000 /Applications/Firefox.app/Contents/MacOS/plugin-container.app/Contents/MacOS/plugin-container
  200  20.0  512000 /System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer
  300   0.0       0 /usr/libexec/somed
garbage line
"""


class TestTopProcesses(unittest.TestCase):
    def test_helpers_count_as_their_app(self):
        rows = {r["name"]: r for r in status.parse_ps(PS)}
        self.assertEqual(set(rows), {"Firefox", "WindowServer", "somed"})
        ff = rows["Firefox"]
        self.assertEqual((ff["count"], ff["cpu"], ff["rss"], ff["pid"]), (3, 16.0, 6144000 * 1024, 103))
        self.assertEqual(rows["somed"]["cpu"], 0.0)
        self.assertEqual(status.app_name("/usr/bin/python3"), "python3")

    def test_the_line_says_how_many(self):
        self.assertEqual(status._proc({"name": "Firefox", "count": 3}, "6 GB"), "Firefox ×3 6 GB")
        self.assertEqual(status._proc({"name": "WindowServer", "count": 1}, "20%"), "WindowServer 20%")


class TestLocale(unittest.TestCase):
    def test_ps_and_sysctl_run_in_the_c_locale(self):
        seen = []

        def run(cmd, **kw):
            seen.append((cmd[0], (kw.get("env") or {}).get("LC_ALL")))
            return core.Result(0, "", "")
        with mock.patch.object(status.core, "run", run):
            status.top_processes()
            status._sysctl("vm.loadavg")
        self.assertEqual(seen, [("ps", "C"), ("sysctl", "C")], "Norwegian ps prints 12,5")

    def test_tools_inside_a_bundle_keep_their_name(self):
        self.assertEqual(status.app_name("/Applications/Xcode.app/Contents/Developer/usr/bin/git"), "git")
        self.assertEqual(status.app_name("/Applications/Firefox.app/Contents/MacOS/plugin-container.app/Contents/MacOS/plugin-container"), "Firefox")
        self.assertEqual(status.app_name("/Applications/Google Chrome.app/Contents/Frameworks/G.framework/Helpers/Google Chrome Helper.app/Contents/MacOS/Google Chrome Helper"), "Google Chrome")


if __name__ == "__main__":
    unittest.main()
