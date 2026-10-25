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
        self.assertEqual(by["ffmpeg"]["look"], "major")
        self.assertIsNone(by["jq"]["look"])

    def test_brew_downgrade_and_scheme(self):
        blob = json.dumps({"formulae": [
            {"name": "ssl", "installed_versions": ["3.6.5"], "current_version": "3.5.9"},
            {"name": "llm", "installed_versions": ["9430"], "current_version": "0.7.0"},
            {"name": "rebuilt", "installed_versions": ["9.0.2"], "current_version": "9.0.2_1"},
        ]})
        by = {i["name"]: i for i in updates.parse_brew_outdated(blob)}
        self.assertEqual(by["ssl"]["look"], "downgrade")
        self.assertFalse(by["ssl"]["major"])
        self.assertEqual(by["llm"]["look"], "scheme")
        self.assertIsNone(by["rebuilt"]["look"])


class TestLook(unittest.TestCase):
    def test_look(self):
        cases = [
            ("1.5.1", "1.16.0", None),            # numeric, not string, comparison
            ("1.4.2", "1.5", None),
            ("2.19", "2.19.1", None),
            ("1.0.0", "1.0", None),               # trailing zeros are the same version
            ("2.0", "2.0.0_1", None),
            ("4.7.1_1", "4.7.2", None),           # brew revision on the old side
            ("2.1.12_2", "2.1.12_1", "downgrade"),  # revision went backwards
            ("3.6b", "3.8", None),
            ("2026.5.1", "2026.10.3", None),      # calendar versions compare normally
            ("2025.1", "2026.1", "major"),
            ("1.2.3,456", "1.2.4,460", None),     # cask build suffix is ignored
            ("20240722", "1.0.0", "scheme"),
            ("0.7.0", "9431", "scheme"),
            ("26.0.1", "27.0.1.0.3", "major"),
            ("6.0.0-beta.1", "5.9.2", "downgrade"),  # npm "latest" behind an installed prerelease
            ("?", "1.0", "major"),                # unknown installed version: look first
            ("1.0", "latest", "major"),
        ]
        for installed, latest, want in cases:
            self.assertEqual(updates._look(installed, latest), want, (installed, latest))

    def test_render_marks(self):
        import io
        from contextlib import redirect_stdout
        data = {"fetched": True, "missing_tools": [], "sources": {"brew": {"items": [
            updates._classify({"name": "ssl", "kind": "formula", "installed": "3.6.5", "latest": "3.5.9"}),
            updates._classify({"name": "llm", "kind": "formula", "installed": "9430", "latest": "0.7.0"}),
            updates._classify({"name": "jq", "kind": "formula", "installed": "1.7", "latest": "1.7.1"}),
            {"name": "old", "kind": "formula", "installed": "1.0", "latest": "2.0", "major": True},  # pre-`look` cache
        ]}}}
        out = io.StringIO()
        with redirect_stdout(out):
            updates.render(data)
        text = out.getvalue()
        self.assertIn("4 outdated, 3 to look at first", text)
        self.assertIn("▼ ssl", text)
        self.assertIn("(downgrade)", text)
        self.assertIn("≠ llm", text)
        self.assertIn("(new version scheme)", text)
        self.assertIn("▲ old", text)
        self.assertIn("· jq", text)
        self.assertLess(text.index("ssl"), text.index("jq"))  # look-first items sort to the top


if __name__ == "__main__":
    unittest.main()
