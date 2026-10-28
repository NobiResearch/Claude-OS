import contextlib
import copy
import io
import plistlib
import time
import unittest
from unittest import mock

from helpers import TempHome

from cos import core, demo, shell, status

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


VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages active:                            1000.
Pages wired down:                         500.
Pages occupied by compressor:             100.
"""


def refused(cmd, **kw):
    """A sandbox (Claude Code's, say): vm_stat and sw_vers answer, sysctl and ps don't."""
    if cmd[0] == "vm_stat":
        return core.Result(0, VM_STAT, "")
    if cmd[0] == "sw_vers":
        return core.Result(0, "ProductName:\tmacOS\nProductVersion:\t27.0.1\nBuildVersion:\t26A500", "")
    return core.Result(1, "", "sysctl: Operation not permitted")


class TestUnreadable(TempHome):
    """When sysctl and ps are refused, the lines leave out what couldn't be read."""

    def rendered(self, s):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status.render(s)
        return out.getvalue()

    def unread(self):
        s = copy.deepcopy(demo.STATUS)
        s["system"].update(model="", chip="", cores=0)
        s["memory"].update(total=0, swap_used=None)
        s.update(uptime=None, load=[], top={"cpu": [], "memory": []}, signals=[])
        return s

    def test_everything_read(self):
        out = self.rendered(demo.STATUS).splitlines()
        self.assertEqual(out[0], "◆ Mac16,8 · macOS 27.0.1 (26A500) · Apple M4 Pro, 14 cores")
        self.assertEqual(out[2], "  memory   21.4 GB used of 48.0 GB · swap 0 B")
        self.assertIn("  uptime   3d 2h · load 2.41 2.18 1.97", out)
        self.assertTrue(any(l.startswith("  top cpu  Xcode") for l in out))
        self.assertEqual(shell._vitals(demo.STATUS)[0], "  Mac16,8 · macOS 27.0.1 · Apple M4 Pro · up 3d 2h")
        self.assertIn("memory 21.4 GB/48.0 GB", shell._vitals(demo.STATUS)[1])

    def test_nothing_made_up(self):
        out = self.rendered(self.unread())
        self.assertEqual(out.splitlines()[0], "◆ macOS 27.0.1 (26A500)")
        self.assertIn("  memory   21.4 GB used\n", out)
        for wrong in ("0 cores", "of 0 B", "swap", " · ,", "uptime", "load", "top cpu", "top mem"):
            self.assertNotIn(wrong, out)
        lines = shell._vitals(self.unread())
        self.assertEqual(lines[0], "  macOS 27.0.1")
        self.assertIn("memory 21.4 GB used ·", lines[1])
        self.assertNotIn("0 B", lines[1])

    def test_this_mac_when_even_sw_vers_fails(self):
        s = self.unread()
        s["system"].update(macos=None, build=None)
        self.assertTrue(self.rendered(s).startswith("◆ this Mac\n"))
        self.assertTrue(shell._vitals(s)[0].startswith("  disk "))

    def test_swap_unknown_is_not_zero(self):
        with mock.patch.object(status.core, "run", refused):
            m = status.memory()
        self.assertEqual(m, {"total": 0, "used": 1600 * 16384, "swap_used": None})
        s = dict(VITALS, memory=m)
        self.assertEqual([x for x in status.signals(s) if "swap" in x[1]], [], "unknown swap is no signal")
        with mock.patch.object(status.core, "run", lambda cmd, **kw: core.Result(
                0, "total = 2048.00M  used = 5120.00M  free = 0.00M  (encrypted)" if cmd[-1] == "vm.swapusage" else "", "")):
            self.assertEqual(status.memory()["swap_used"], 5 * 2 ** 30)


if __name__ == "__main__":
    unittest.main()
