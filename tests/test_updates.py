import json
import unittest

import helpers  # noqa: F401  (puts lib/ on sys.path)

from cos import updates

SOFTWAREUPDATE = """Software Update Tool

Finding available software
Software Update found the following new or updated software:
* Label: macOS Example 27.0.2-26A500
\tTitle: macOS Example 27.0.2, Version: 27.0.2, Size: 1534000KiB, Recommended: YES, Action: restart,
* Label: Safari19.1
\tTitle: Safari, Version: 19.1, Size: 120000KiB, Recommended: YES,
"""


class TestParsers(unittest.TestCase):
    def test_softwareupdate(self):
        items = updates.parse_softwareupdate(SOFTWAREUPDATE)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["version"], "27.0.2")
        self.assertTrue(items[0]["restart"])
        self.assertFalse(items[1]["restart"])
        self.assertTrue(items[1]["recommended"])

    def test_softwareupdate_nothing(self):
        self.assertEqual(updates.parse_softwareupdate("No new software available.\n"), [])

    def test_brew_outdated(self):
        blob = json.dumps({
            "formulae": [{"name": "ffmpeg", "installed_versions": ["8.0"], "current_version": "9.0", "pinned": False},
                         {"name": "jq", "installed_versions": ["1.7"], "current_version": "1.7.1", "pinned": True}],
            "casks": [{"name": "firefox", "installed_versions": ["140.0"], "current_version": "141.0"}],
        })
        items = updates.parse_brew_outdated(blob)
        by = {i["name"]: i for i in items}
        self.assertTrue(by["ffmpeg"]["major"])
        self.assertFalse(by["jq"]["major"])
        self.assertTrue(by["jq"]["pinned"])
        self.assertEqual(by["firefox"]["kind"], "cask")


if __name__ == "__main__":
    unittest.main()
