"""cos backup — Time Machine, and which connected disk could hold the backups (decision 0012).

Read-only. Whether Time Machine has a destination comes from `tmutil destinationinfo`, which
mounts nothing (0005). The disks come from `diskutil`'s plists, which read the same in every
system language; nothing on a disk is ever listed or opened, so macOS never asks about
removable volumes. How old the last backup is can't be read without Full Disk Access or
mounting the destination, so it isn't shown.

Volume names can be personal ("…'s Passport"): they're printed for the human and returned by
`--json`, and never cached, journaled, signalled or written anywhere else.

`cos backup setup` opens Time Machine's settings; the human chooses the disk there. Ovenbird
never runs `tmutil enable`, `setdestination` or `startbackup`.
"""

import os
import plistlib

from . import core

SETTINGS = "x-apple.systempreferences:com.apple.Time-Machine-Settings.extension"
ROOM = 2  # Apple's rule of thumb: a backup disk at least twice the size of what it backs up
EMPTY = 1e9  # an APFS disk with less than this in use is preferred as empty (it's never erased)
# Partitions that hold no volume of their own: an APFS container's physical store (its
# volumes are listed under the container), EFI, boot and recovery helpers.
NOT_A_VOLUME = {"Apple_APFS", "EFI", "Apple_Boot", "Apple_APFS_Recovery", "Apple_APFS_ISC",
                "Microsoft Reserved", "Apple_Free"}
PARTITION_MAPS = {"GUID_partition_scheme", "FDisk_partition_scheme", "Apple_partition_scheme",
                  "Apple_APFS_Container"}


def parse_backup(text):
    """`tmutil destinationinfo -X` is a plist, an empty dict when Time Machine has no
    destination. Anything we can't read is unknown (None), and unknown is never a signal."""
    try:
        data = plistlib.loads(text.encode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not data:
        return {"configured": False}
    dests = data.get("Destinations")
    return {"configured": bool(dests)} if isinstance(dests, list) else None


def state():
    """Is Time Machine set up? Never mounts or names the destination (decision 0005)."""
    r = core.run(["tmutil", "destinationinfo", "-X"], timeout=10)
    return parse_backup(r.out) if r.ok and r.out else None


def _plist(cmd):
    r = core.run(cmd, timeout=10)
    try:
        data = plistlib.loads(r.out.encode("utf-8")) if r.ok and r.out else None
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def to_back_up():
    """Bytes in use on the startup disk's data volume: roughly what a first backup copies."""
    info = _plist(["diskutil", "info", "-plist", "/System/Volumes/Data"]) or {}
    used = info.get("CapacityInUse")
    if isinstance(used, int) and used > 0:
        return used
    try:
        s = os.statvfs("/")
        return (s.f_blocks - s.f_bfree) * s.f_frsize
    except OSError:
        return None


def volume(info):
    """One volume from `diskutil info -plist`, or None for anything that isn't a physical
    external disk (the startup disk, disk images such as simulator runtimes)."""
    if info.get("Internal") is not False or info.get("BusProtocol") == "Disk Image" or not info.get("FilesystemType"):
        return None
    apfs = info.get("FilesystemType") == "apfs"
    size = info.get("APFSContainerSize") if apfs else info.get("TotalSize")
    free = info.get("APFSContainerFree") if apfs else info.get("FreeSpace")
    if not isinstance(size, int) or size <= 0:
        return None
    # An unmounted volume that isn't APFS reports no free space at all: unknown, not full.
    known = isinstance(free, int) and (apfs or bool(info.get("MountPoint")))
    used = size - free if known else None
    return {"name": info.get("VolumeName") or "(no name)", "format": info.get("FilesystemName") or "unformatted",
            "apfs": apfs, "size": size, "used": used, "mounted": bool(info.get("MountPoint"))}


def disks():
    """Physical external volumes. APFS volumes that share a container count once."""
    listing = _plist(["diskutil", "list", "-plist", "external"]) or {}
    ids = []
    for entry in listing.get("AllDisksAndPartitions") or []:
        parts = (entry.get("Partitions") or []) + (entry.get("APFSVolumes") or [])
        if not parts and entry.get("Content") not in PARTITION_MAPS:
            parts = [entry]  # one filesystem across the whole disk, no partition map
        ids += [p["DeviceIdentifier"] for p in parts
                if p.get("DeviceIdentifier") and p.get("Content") not in NOT_A_VOLUME]
    out, seen = [], set()
    for ident in ids:
        info = _plist(["diskutil", "info", "-plist", ident]) or {}
        v = volume(info)
        if not v:
            continue
        container = info.get("APFSContainerReference") if v["apfs"] else None
        if container in seen:
            continue  # one line per container: its volumes share the space
        if container:
            seen.add(container)
        v["id"] = ident
        out.append(v)
    return out


def judge(v, need):
    """Whether a disk would do, and what Time Machine would do to it, in plain words."""
    empty = v["apfs"] and v["used"] is not None and v["used"] < EMPTY
    v["fits"] = bool(need) and v["size"] >= ROOM * need
    v["erases"] = not v["apfs"]  # Time Machine reformats anything that isn't APFS
    v["empty"] = empty
    if not need:
        v["verdict"] = "can't tell whether it's big enough"
    elif v["size"] < need:
        v["verdict"] = "too small: it can't hold even one backup"
    elif not v["fits"]:
        v["verdict"] = "tight: room for one backup but little history (aim for %s)" % core.human_bytes(ROOM * need)
    else:
        v["verdict"] = "big enough"
    if v["erases"]:
        v["verdict"] += "; Time Machine would reformat it, erasing everything on it%s" % (
            " (%s in use)" % core.human_bytes(v["used"]) if v["used"] is not None else "")
    elif not empty:
        v["verdict"] += "; Time Machine can usually add its own volume beside your files"
    return v


def best(vols):
    """The one to suggest: big enough, and nothing on it would be erased (so APFS only).
    Empty disks first. A disk Time Machine would reformat is never suggested."""
    ok = [v for v in vols if v["fits"] and not v["erases"]]
    return max(ok, key=lambda v: (v["empty"], v["size"])) if ok else None


def check():
    tm = state()
    need = to_back_up()
    vols = [judge(v, need) for v in disks()]
    pick = best(vols)
    return {"configured": (tm or {}).get("configured"), "to_back_up": need, "disks": vols,
            "suggest": pick["id"] if pick else None}


def render(r):
    if r["configured"]:
        print("✓ Time Machine is set up. System Settings › General › Time Machine shows when it last ran.")
        return
    print("✗ Time Machine isn't set up: nothing backs up this Mac." if r["configured"] is False
          else "? Couldn't tell whether Time Machine is set up.")
    need = r["to_back_up"]
    if need:
        print("  to back up  about %s (what's in use on the startup disk)" % core.human_bytes(need))
    if not r["disks"]:
        print("\nNo external disk is connected. Plug in one of at least %s, then run `cos backup` again."
              % (core.human_bytes(ROOM * need) if need else "twice your startup disk's used space"))
    else:
        print("\nConnected disks:")
        for v in r["disks"]:
            print("  %s %-18s %-8s %s%s · %s" % ("●" if v["id"] == r["suggest"] else "·", v["name"][:18], v["format"][:8],
                                                core.human_bytes(v["size"]),
                                                (", %s free" % core.human_bytes(v["size"] - v["used"])) if v["used"] is not None else "",
                                                v["verdict"]))
        pick = [v["name"] for v in r["disks"] if v["id"] == r["suggest"]]
        print("\nSuggested: %s (●)." % pick[0] if pick
              else "\nNone of these is a good fit without erasing something; a disk of at least %s would be." % (
                  core.human_bytes(ROOM * need) if need else "twice your used space"))
    print("Set it up: `cos backup setup` opens Time Machine's settings; you choose the disk there.")


def setup():
    core.run(["open", SETTINGS], timeout=10)
    print("Opened System Settings › Time Machine. Click Add Backup Disk and choose the disk;"
          " macOS says there whether it has to erase it.")
    return 0


def main(args):
    if getattr(args, "backup_cmd", None) == "setup":
        return setup()
    core.emit(check(), args.json, render)
    return 0
