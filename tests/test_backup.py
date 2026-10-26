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
# Invented disks, laid out the way diskutil really lists them (GPT disks with an EFI
# partition; an APFS disk's physical store partition first, its volumes under the
# container): a fresh 2 TB APFS backup drive, a 600 GB APFS drive with photos, a 2 TB
# exFAT drive holding 900 MB of files, an old stick formatted across the whole disk, an
# unmounted exFAT partition, and a simulator runtime's disk image.
LIST = {"AllDisksAndPartitions": [
    {"DeviceIdentifier": "disk4", "Content": "GUID_partition_scheme",
     "Partitions": [{"DeviceIdentifier": "disk4s1", "Content": "EFI"}, {"DeviceIdentifier": "disk4s2", "Content": "Apple_APFS"}]},
    {"DeviceIdentifier": "disk5", "Content": "Apple_APFS_Container",
     "APFSVolumes": [{"DeviceIdentifier": "disk5s1"}, {"DeviceIdentifier": "disk5s2"}]},
    {"DeviceIdentifier": "disk6", "Content": "GUID_partition_scheme",
     "Partitions": [{"DeviceIdentifier": "disk6s1", "Content": "EFI"}, {"DeviceIdentifier": "disk6s2", "Content": "Apple_APFS"}]},
    {"DeviceIdentifier": "disk7", "Content": "Apple_APFS_Container", "APFSVolumes": [{"DeviceIdentifier": "disk7s1"}]},
    {"DeviceIdentifier": "disk8", "Content": "GUID_partition_scheme",
     "Partitions": [{"DeviceIdentifier": "disk8s1", "Content": "EFI"},
                    {"DeviceIdentifier": "disk8s2", "Content": "Microsoft Basic Data"},
                    {"DeviceIdentifier": "disk8s3", "Content": "Microsoft Basic Data"}]},
    {"DeviceIdentifier": "disk9", "Content": ""},
    {"DeviceIdentifier": "disk10", "Content": "GUID_partition_scheme",
     "Partitions": [{"DeviceIdentifier": "disk10s1", "Content": "Apple_APFS"}]},
    {"DeviceIdentifier": "disk11", "Content": "Apple_APFS_Container", "APFSVolumes": [{"DeviceIdentifier": "disk11s1"}]},
]}
USB = {"Internal": False, "BusProtocol": "USB"}
INFO = {
    "disk4s1": dict(USB, FilesystemType="msdos", FilesystemName="MS-DOS (FAT32)", TotalSize=209715200),
    "disk4s2": dict(USB, APFSContainerReference="disk5", TotalSize=2000 * GB),
    "disk5s1": dict(USB, FilesystemType="apfs", FilesystemName="APFS", VolumeName="Backup Disk",
                    APFSContainerSize=2000 * GB, APFSContainerFree=2000 * GB - 200 * 10 ** 6,
                    APFSContainerReference="disk5", MountPoint="/Volumes/Backup Disk"),
    "disk5s2": dict(USB, FilesystemType="apfs", FilesystemName="APFS", VolumeName="Same Container",
                    APFSContainerSize=2000 * GB, APFSContainerFree=2000 * GB - 200 * 10 ** 6, APFSContainerReference="disk5"),
    "disk6s2": dict(USB, APFSContainerReference="disk7", TotalSize=600 * GB),
    "disk7s1": dict(USB, BusProtocol="Thunderbolt", FilesystemType="apfs", FilesystemName="APFS", VolumeName="Photos Drive",
                    APFSContainerSize=600 * GB, APFSContainerFree=200 * GB, APFSContainerReference="disk7"),
    "disk8s2": dict(USB, FilesystemType="exfat", FilesystemName="ExFAT", VolumeName="Untitled",
                    TotalSize=2000 * GB, FreeSpace=2000 * GB - 900 * 10 ** 6, MountPoint="/Volumes/Untitled"),
    "disk8s3": dict(USB, FilesystemType="exfat", FilesystemName="ExFAT", VolumeName="Untitled",
                    TotalSize=1000 * GB, FreeSpace=0),
    "disk9": dict(USB, FilesystemType="msdos", FilesystemName="MS-DOS (FAT32)", VolumeName="Old Stick",
                  TotalSize=256 * GB, FreeSpace=100 * GB, MountPoint="/Volumes/Old Stick"),
    "disk10s1": {"Internal": False, "BusProtocol": "Disk Image", "APFSContainerReference": "disk11", "TotalSize": 20 * GB},
    "disk11s1": {"Internal": False, "BusProtocol": "Disk Image", "FilesystemType": "apfs", "FilesystemName": "APFS",
                 "VolumeName": "iOS Simulator", "APFSContainerSize": 20 * GB, "APFSContainerFree": 1 * GB},
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
        self.assertEqual([v["id"] for v in r["disks"]], ["disk5s1", "disk7s1", "disk8s2", "disk8s3", "disk9"],
                         "no EFI, no APFS store partition, no disk image, one line per container")
        by = {v["id"]: v for v in r["disks"]}
        self.assertTrue(by["disk5s1"]["fits"] and by["disk5s1"]["empty"])
        self.assertIn("tight", by["disk7s1"]["verdict"])
        self.assertIn("beside your files", by["disk7s1"]["verdict"])
        self.assertIn("big enough", by["disk8s2"]["verdict"])
        self.assertIn("erasing everything on it", by["disk8s2"]["verdict"], "900 MB of files is not empty")
        self.assertIsNone(by["disk8s3"]["used"], "unmounted: unknown, not full")
        self.assertIn("too small", by["disk9"]["verdict"], "a whole-disk filesystem is still seen")
        self.assertEqual(r["suggest"], "disk5s1", "by device, so two disks called Untitled can't both be marked")

    def test_a_disk_that_would_be_reformatted_is_never_suggested(self):
        only_exfat = {"AllDisksAndPartitions": [LIST["AllDisksAndPartitions"][4]]}
        r, _ = self.check(fake_mac(listing=only_exfat))
        self.assertIsNone(r["suggest"])
        with redirect_stdout(io.StringIO()) as out:
            backup.render(r)
        self.assertIn("None of these is a good fit without erasing something", out.getvalue())
        self.assertEqual(out.getvalue().count("●"), 0)

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
