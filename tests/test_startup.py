import os
import plistlib
import tempfile
import unittest

import helpers  # noqa: F401

from cos import startup

UID = os.getuid()
DUMP = """
========================
 Records for UID %d : 0000
========================
 Items:

 #1:
                 UUID: 1
                 Name: Example Agent
       Developer Name: Example Inc
                 Type: legacy agent (0x10008)
          Disposition: [enabled, allowed, notified] (0xb)
           Identifier: 16.com.example.agent
                  URL: file:///Users/%d/Library/LaunchAgents/com.example.agent.plist
      Executable Path: /Users/%d/.example/bin/agent
             Last Use: 2026-01-01 10:00:00+02:00

 #2:
                 Name: Example App
                 Type: app (0x2)
          Disposition: [disabled, allowed, notified] (0x2)
           Identifier: 2.com.example.app
                  URL: file:///Applications/Example%%20App.app/
      Executable Path: Contents/MacOS/Example
""" % (UID, UID, UID)


class TestStartup(unittest.TestCase):
    def test_parse_and_paths(self):
        items = startup.parse_btm(DUMP)
        self.assertEqual([i["name"] for i in items], ["Example Agent", "Example App"])
        agent, app = items
        self.assertEqual(agent["type"], "launch agent")
        self.assertTrue(agent["enabled"])
        self.assertEqual(agent["path"], os.path.expanduser("~/.example/bin/agent"), "uid-style home paths map back")
        self.assertFalse(app["enabled"])
        self.assertEqual(app["path"], "/Applications/Example App.app/Contents/MacOS/Example", "relative to the bundle")

    def test_findings(self):
        item = {"path": "/definitely/not/here", "enabled": True, "allowed": True, "authority": "ad hoc",
                "last_use": 86400}
        found = startup.findings(item, now=200 * 86400)
        self.assertEqual(len(found), 3)
        self.assertIn("missing", found[0])


    def test_launchd_plists_need_no_password(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "com.example.sync.plist"), "wb") as f:
                plistlib.dump({"Label": "com.example.sync", "ProgramArguments": ["/opt/example/bin/sync", "--daemon"],
                               "RunAtLoad": True}, f)
            with open(os.path.join(d, "com.example.off.plist"), "wb") as f:
                plistlib.dump({"Label": "com.example.off", "Program": "/opt/example/off", "Disabled": True}, f,
                              fmt=plistlib.FMT_BINARY)
            with open(os.path.join(d, "broken.plist"), "w") as f:
                f.write("not a plist")
            items = startup.launchd_items([(d, "launch agent", "me")])
        by = {i["name"]: i for i in items}
        self.assertEqual(sorted(by), ["com.example.off", "com.example.sync"], "unreadable plists are skipped")
        self.assertEqual(by["com.example.sync"]["path"], "/opt/example/bin/sync")
        self.assertTrue(by["com.example.sync"]["enabled"])
        self.assertFalse(by["com.example.off"]["enabled"])
        self.assertEqual(by["com.example.sync"]["uid"], UID)

    def test_scripts_are_named_not_called_unsigned(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write("#!/bin/sh\necho hi\n")
        try:
            self.assertEqual(startup.signer(f.name)["authority"], "script")
        finally:
            os.unlink(f.name)
        found = startup.findings({"path": "/bin/sh", "enabled": True, "allowed": True, "authority": "script", "last_use": None})
        self.assertEqual(len(found), 1)
        self.assertIn("script", found[0])

    def test_launchctl_overrides(self):
        text = '\tdisabled services = {\n\t\t"com.example.a" => enabled\n\t\t"com.example.b" => disabled\n\t\t"com.example.c" => true\n\t}'
        self.assertEqual(startup.parse_overrides(text),
                         {"com.example.a": True, "com.example.b": False, "com.example.c": False})

    def test_default_audit_never_runs_sfltool(self):
        from unittest import mock
        from cos import core
        calls = []
        with mock.patch.object(startup.core, "run", side_effect=lambda argv, **k: calls.append(argv[0]) or core.Result(0, "", "")):
            data = startup.audit()
        self.assertNotIn("sfltool", calls, "sfltool shows macOS's admin password dialog")
        self.assertFalse(data["full"])
        self.assertIn("--full", data["note"])


if __name__ == "__main__":
    unittest.main()
