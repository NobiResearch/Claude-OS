import json
import unittest

from helpers import TempHome

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


class TestUnchecked(unittest.TestCase):
    def test_npm_offline_is_not_up_to_date(self):
        offline = json.dumps({"error": {"code": "ENOTFOUND", "summary": "request failed"}})
        self.assertIsNone(updates.parse_npm_outdated(1, offline))
        self.assertIsNone(updates.parse_npm_outdated(1, ""))
        self.assertIsNone(updates.parse_npm_outdated(1, "not json"))
        self.assertEqual(updates.parse_npm_outdated(0, "{}"), [], "really up to date")
        rows = updates.parse_npm_outdated(1, json.dumps({"gh-axi": {"current": "0.1.35", "latest": "0.1.43"}}))
        self.assertEqual([r["name"] for r in rows], ["gh-axi"], "exit 1 with packages is normal")

    def test_an_unchecked_source_never_says_up_to_date(self):
        import io
        from contextlib import redirect_stdout
        data = {"sources": {"npm": {"items": [], "error": updates.UNCHECKED}, "rustup": {"items": [], "error": None}},
                "total": 0, "fetched": False, "missing_tools": []}
        with redirect_stdout(io.StringIO()) as out:
            updates.render(data)
        self.assertIn("npm (global): couldn't check", out.getvalue())
        self.assertIn("Rust: up to date", out.getvalue())

    def test_the_tools_own_words_never_show(self):
        from unittest import mock
        from cos import core
        with mock.patch.object(updates.core, "which", return_value="/usr/bin/x"), \
                mock.patch.object(updates.core, "run", return_value=core.Result(1, "", "npm error A complete log is in /Users/someone/.npm/_logs/x.log")):
            self.assertEqual(updates.check_npm(), {"items": [], "error": "couldn't check"})
            self.assertEqual(updates.check_mas()["error"], "couldn't check")
            self.assertEqual(updates.check_rustup()["error"], "couldn't check")


class TestApplyOutput(TempHome):
    BREW = """==> Upgrading 2 outdated packages:
harfbuzz 14.2.0 -> 15.0.0
cairo 1.18.4 -> 1.18.6
==> Pouring harfbuzz--15.0.0.arm64.bottle.tar.gz
Warning: The post-install step did not complete successfully
You can try again using:
  brew postinstall harfbuzz
==> Pouring cairo--1.18.6.arm64.bottle.tar.gz
Error: Could not symlink lib/pkgconfig/cairo.pc
Target /opt/homebrew/lib/pkgconfig/cairo.pc
already exists. You may want to remove it:
  rm '/opt/homebrew/lib/pkgconfig/cairo.pc'
==> Summary
"""

    def test_each_notice_keeps_its_details(self):
        blocks = updates.notices(self.BREW.splitlines(True))
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][0], "Warning: The post-install step did not complete successfully")
        self.assertIn("  brew postinstall harfbuzz", blocks[0])
        self.assertIn("already exists. You may want to remove it:", blocks[1])
        self.assertNotIn("==> Pouring cairo--1.18.6.arm64.bottle.tar.gz", blocks[0])

    def test_npm_notices(self):
        out = ["npm warn deprecated x@1: no longer supported\n", "added 3 packages in 2s\n", "npm error code EACCES\n",
               "npm error path /usr/local/lib/node_modules\n"]
        blocks = updates.notices(out)
        self.assertEqual([b[0] for b in blocks], ["npm warn deprecated x@1: no longer supported", "npm error code EACCES",
                                                  "npm error path /usr/local/lib/node_modules"])

    def test_apply_streams_both_streams_and_reports_what_stayed_outdated(self):
        import io
        import os
        from contextlib import redirect_stdout
        from unittest import mock
        from cos import core
        seen = {}

        def fake_stream(cmd, on_line, **kw):
            seen["cmd"] = cmd
            for line in self.BREW.splitlines(True):
                on_line(line)
            return core.Result(1, "", "")

        with mock.patch.object(updates.core, "stream", fake_stream), \
                mock.patch.object(updates, "still_outdated", lambda names: ["cairo"]), \
                redirect_stdout(io.StringIO()) as out:
            rc = updates.apply("brew", ["harfbuzz", "cairo"], yes=True)
        text = out.getvalue()
        self.assertEqual(rc, 1)
        self.assertEqual(seen["cmd"][:3], ["/bin/sh", "-c", 'exec "$0" "$@" 2>&1'])
        self.assertEqual(seen["cmd"][3:], ["brew", "upgrade", "harfbuzz", "cairo"], "arguments pass through untouched")
        self.assertIn("==> Upgrading 2 outdated packages:", text)
        self.assertIn("brew postinstall harfbuzz", text)
        self.assertIn("Still outdated after the upgrade: cairo", text)
        self.assertIn("Full output:", text)
        folder = str(core.home("runs", "updates"))
        logs = os.listdir(folder)
        self.assertEqual(len(logs), 1)
        self.assertEqual(oct(os.stat(os.path.join(folder, logs[0])).st_mode & 0o777), "0o600")
        entry = core.read_journal(days=1, kind="action")[-1]
        self.assertEqual(entry["still_outdated"], ["cairo"])


if __name__ == "__main__":
    unittest.main()
