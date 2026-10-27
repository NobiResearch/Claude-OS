"""cos security — the Mac's protections, and turning the firewall on.

Read: FileVault, System Integrity Protection, the firewall and Gatekeeper, each with what it
does and how to turn it on. Act: `cos security on firewall --yes` is the one switch a command
may flip, and only ever on. It's a fixed command, run as admin through macOS's own password
dialog, which says that Ovenbird is asking; the password never reaches Claude. FileVault and
SIP can't be turned on by a script, and spctl lost its global Gatekeeper switch in macOS 15,
so for those it says where to go.

This module runs as root when the human approves, so it's on the night shift's protected list
(lib/cos/hook.py) and imports nothing but core.
"""

import os
import re

from . import core

OSASCRIPT = "/usr/bin/osascript"
FIREWALL = "/usr/libexec/ApplicationFirewall/socketfilterfw"
# Everything `cos security on` can run, as complete literals: nothing is ever filled in, and
# there's no way to turn anything off.
SWITCHES = {
    "firewall": 'do shell script "/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on" '
                'with prompt "Ovenbird wants to turn on the macOS firewall." with administrator privileges',
}
NAMES = {"filevault": "FileVault", "sip": "System Integrity Protection", "firewall": "Firewall",
         "gatekeeper": "Gatekeeper"}
WHAT = {
    "filevault": "encrypts the disk, so a lost or stolen Mac doesn't give up its files",
    "sip": "stops anything, even with an admin password, from changing macOS's own files",
    "firewall": "blocks incoming connections to apps that haven't been allowed",
    "gatekeeper": "only opens apps from the App Store and identified developers",
}
HOW = {
    "filevault": "System Settings › Privacy & Security › FileVault (keep the recovery key it shows somewhere safe)",
    "sip": "only from Recovery: shut down, hold the power button, open Terminal, run `csrutil enable`, restart",
    "firewall": "`cos security on firewall --yes` (macOS asks for your password), or System Settings › Network › Firewall",
    "gatekeeper": "System Settings › Privacy & Security › Security: allow apps from the App Store and identified developers",
}


def posture():
    """{protection: True (on) | False (off) | None (couldn't tell)}."""
    fv = core.run(["fdesetup", "status"], timeout=5).out
    sip = core.run(["csrutil", "status"], timeout=5).out
    fw = core.run([FIREWALL, "--getglobalstate"], timeout=5).out
    gk = core.run(["spctl", "--status"], timeout=5)
    return {
        "filevault": "On" in fv if fv else None,
        "sip": "enabled" in sip if sip else None,
        "firewall": ("enabled" in fw or "State = 1" in fw) if fw else None,
        "gatekeeper": "enabled" in (gk.out + gk.err) if (gk.out or gk.err) else None,
    }


def render(state):
    for key in ("filevault", "sip", "firewall", "gatekeeper"):
        on = state.get(key)
        print("%s %-28s %s" % ("✓" if on else ("✗" if on is False else "?"), NAMES[key],
                               "on" if on else ("OFF" if on is False else "couldn't tell")))
        print("    %s" % WHAT[key])
        if on is False:
            print("    turn it on: %s" % HOW[key])


def _error_number(err):
    """osascript ends its errors with the number in parentheses, whatever the system language."""
    m = re.search(r"\((-?\d+)\)\s*$", (err or "").strip())
    return int(m.group(1)) if m else None


def turn_on(name, yes=False):
    if name not in SWITCHES:
        core.die("`cos security on` only knows: %s" % ", ".join(sorted(SWITCHES)))
    if os.environ.get("CLAUDE_OS_DAEMON") or os.environ.get("COS_SANDBOXED"):
        core.die("turning on the %s needs the human at the Mac" % name, 3)
    if posture().get(name):
        print("The %s is already on." % name)
        return 0
    if not yes:
        print("Would turn on the macOS %s. macOS shows its own password dialog, saying Ovenbird is asking;\n"
              "the password goes to macOS, not to Claude. Undo any time: System Settings › Network › Firewall.\n"
              "(add --yes to do it)" % name)
        return 2
    r = core.run([OSASCRIPT, "-e", "with timeout of 120 seconds", "-e", SWITCHES[name], "-e", "end timeout"], timeout=150)
    if posture().get(name):
        core.journal("action", "security: %s turned on" % name, target=name, before=False, after=True)
        core.run(["rm", "-f", str(core.home("cache", "status.json"))])
        print("✓ The %s is on. An app that listens on the network may ask once whether to accept incoming "
              "connections; that's the firewall working." % name)
        return 0
    code = _error_number(r.err)
    if code == -128:
        why = "cancelled at the password dialog"
    elif r.ok:
        why = "macOS accepted the command but the %s is still off: it may be managed by your organization" % name
    else:
        why = "failed (%s)" % ("osascript error %d" % code if code is not None else "exit %d" % r.rc)
    core.journal("action", "security: %s unchanged (%s)" % (name, why), target=name, before=False, after=False)
    print("✗ The %s is still off: %s." % (name, why))
    return 1


def main(args):
    if args.security_cmd == "on":
        return turn_on(args.name, yes=args.yes)
    core.emit(posture(), args.json, render)
    return 0
