import io
import json
import os
import plistlib
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import TempHome

from cos import backup, cli, core

GB = 10 ** 9
# Invented disks: a USB drive with room, an old exFAT stick with files on it, a full APFS
# drive, and a simulator runtime's disk image (external, but not a disk anyone plugged in).
LIST = {"AllDisksAndPartitions": [
    {"DeviceIdentifier": "disk4", "Partitions": [{"DeviceIdentifier": "disk4s2"}]},
    {"DeviceIdentifier": "disk5", "APFSVolumes": [{"DeviceIdentifier": "disk5s1"}, {"DeviceIdentifier": "disk5s2"}]},
    {"DeviceIdentifier": "disk6", "Partitions": [{"DeviceIdentifier": "disk6s1"}]},
    {"DeviceIdentifier": "disk7", "APFSVolumes": [{"DeviceIdentifier": "disk7s1"}]},
]}
INFO = {
    "disk4s2": {"Internal": False, "BusProtocol": "USB", "FilesystemType": "exfat", "FilesystemName": "ExFAT",
                "VolumeName": "Old Stick", "TotalSize": 256 * GB, "FreeSpace": 100 * GB, "MountPoint": "/Volumes/Old Stick"},
    "disk5s1": {"Internal": False, "BusProtocol": "USB", "FilesystemType": "apfs", "FilesystemName": "APFS",
                "VolumeName": "Backup Disk", "APFSContainerSize": 2000 * GB, "APFSContainerFree": 2000 * GB - 200 * 10 ** 6,
                "APFSContainerReference": "disk5", "MountPoint": "/Volumes/Backup Disk"},
    "disk5s2": {"Internal": False, "BusProtocol": "USB", "FilesystemType": "apfs", "FilesystemName": "APFS",
                "VolumeName": "Same Container", "APFSContainerSize": 2000 * GB, "APFSContainerFree": 1999 * GB,
                "APFSContainerReference": "disk5"},
    "disk6s1": {"Internal": False, "BusProtocol": "Disk Image", "FilesystemType": "apfs", "FilesystemName": "APFS",
                "VolumeName": "iOS Simulator", "APFSContainerSize": 20 * GB, "APFSContainerFree": 1 * GB},
    "disk7s1": {"Internal": False, "BusProtocol": "Thunderbolt", "FilesystemType": "apfs", "FilesystemName": "APFS",
                "VolumeName": "Photos Drive", "APFSContainerSize": 600 * GB, "APFSContainerFree": 200 * GB},
    "/System/Volumes/Data": {"Internal": True, "CapacityInUse": 400 * GB},
}
NOT_SET = plistlib.dumps({}).decode()


def fake_mac(listing=LIST, info=INFO, tm=NOT_SET):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["tmutil", "destinationinfo"]:
            return core.Result(0, tm, "")
        if cmd[:3] == ["diskutil", "list", "-plist"]:
            return core.Result(0, plistlib.dumps(listing).decode(), "")
        if cmd[:3] == ["diskutil", "info", "-plist"]:
            found = info.get(cmd[3])
            return core.Result(0 if found else 1, plistlib.dumps(found).decode() if found else "", "")
        return core.Result(0, "", "")
    run.calls = calls
    return run


class TestBackup(TempHome):
    def check(self, mac=None):
        mac = mac or fake_mac()
        with mock.patch.object(backup.core, "run", mac):
            return backup.check(), mac

    def test_it_judges_each_physical_disk_and_suggests_one_that_wont_be_erased(self):
        r, _ = self.check()
        self.assertEqual(r["configured"], False)
        self.assertEqual(r["to_back_up"], 400 * GB)
        names = [v["name"] for v in r["disks"]]
        self.assertEqual(names, ["Old Stick", "Backup Disk", "Photos Drive"], "no disk images, one per container")
        by = {v["name"]: v for v in r["disks"]}
        self.assertIn("too small", by["Old Stick"]["verdict"])
        self.assertIn("would erase it", by["Old Stick"]["verdict"])
        self.assertTrue(by["Backup Disk"]["fits"] and by["Backup Disk"]["empty"])
        self.assertIn("tight", by["Photos Drive"]["verdict"])
        self.assertIn("beside your files", by["Photos Drive"]["verdict"])
        self.assertEqual(r["suggest"], "Backup Disk")

    def test_no_disk_says_what_to_plug_in(self):
        r, _ = self.check(fake_mac(listing={}))
        with redirect_stdout(io.StringIO()) as out:
            backup.render(r)
        self.assertIn("No external disk is connected", out.getvalue())
        self.assertIn("at least %s" % core.human_bytes(800 * GB), out.getvalue())

    def test_it_reads_plists_only_and_never_touches_a_disk(self):
        _, mac = self.check()
        self.assertEqual({tuple(c[:2]) for c in mac.calls}, {("tmutil", "destinationinfo"), ("diskutil", "list"),
                                                              ("diskutil", "info")})
        for c in mac.calls:
            self.assertNotIn("enable", c)
            self.assertNotIn("setdestination", c)

    def test_volume_names_stay_on_screen(self):
        r, _ = self.check()
        with redirect_stdout(io.StringIO()):
            backup.render(r)
        trail = json.dumps(core.read_journal(days=1))
        for name in os.listdir(str(core.home("cache"))) if os.path.isdir(str(core.home("cache"))) else []:
            trail += open(str(core.home("cache", name))).read()
        for disk in ("Old Stick", "Backup Disk", "Photos Drive"):
            self.assertNotIn(disk, trail)

    def test_set_up_already(self):
        tm = plistlib.dumps({"Destinations": [{"Kind": "Local"}]}).decode()
        r, _ = self.check(fake_mac(tm=tm))
        with redirect_stdout(io.StringIO()) as out:
            backup.render(r)
        self.assertTrue(out.getvalue().startswith("✓ Time Machine is set up"))

    def test_setup_only_opens_settings_and_never_from_a_background_job(self):
        mac = fake_mac()
        with mock.patch.object(backup.core, "run", mac), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["backup", "setup"]), 0)
        self.assertEqual(mac.calls, [["open", backup.SETTINGS]])
        os.environ["CLAUDE_OS_DAEMON"] = "morning"
        try:
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
                cli.main(["backup", "setup"])
            self.assertEqual(cm.exception.code, 3)
        finally:
            del os.environ["CLAUDE_OS_DAEMON"]


if __name__ == "__main__":
    unittest.main()
