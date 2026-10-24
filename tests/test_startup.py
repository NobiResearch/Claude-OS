import os
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


if __name__ == "__main__":
    unittest.main()
