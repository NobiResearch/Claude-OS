import json
import os
import plistlib
import sys
import tempfile
from unittest import mock

from helpers import TempHome

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import release  # noqa: E402
from cos import core  # noqa: E402


class TestRelease(TempHome):
    """`app/build.sh --release` (decision 0015): an app signed with the human's name that
    strangers download, so every check refuses rather than guesses."""

    def test_a_release_is_cut_by_hand(self):
        for var in ("CI", "CLAUDE_OS_DAEMON", "COS_SANDBOXED"):
            self.assertTrue(any(var in p for p in release.preflight({var: "1"})), var)

    def profile(self, **kw):
        p = {"ProvisionsAllDevices": True, "Platform": ["OSX"], "TeamIdentifier": ["TEAM123456"],
             "Name": "Ovenbird Developer ID", "AppIDName": "Ovenbird",
             "Entitlements": {"com.apple.application-identifier": "TEAM123456.app.claude-os.desktop"}}
        p.update(kw)
        return p

    def test_only_a_developer_id_profile_for_the_release_app_id(self):
        problems, app_id, team = release.profile_problems(self.profile(), "app.claude-os.desktop")
        self.assertEqual((problems, app_id, team), ([], "TEAM123456.app.claude-os.desktop", "TEAM123456"))
        dev = self.profile(ProvisionsAllDevices=None, ProvisionedDevices=["00008112-ABC"])
        self.assertIn("not a Developer ID profile", release.profile_problems(dev, "app.claude-os.desktop")[0][0])
        self.assertTrue(release.profile_problems(self.profile(), "local.claude-os.desktop")[0])
        self.assertTrue(release.profile_problems(self.profile(Platform=["iOS"]), "app.claude-os.desktop")[0])

    def test_the_profile_is_named_neutrally(self):
        home = os.path.expanduser("~")
        problems = release.profile_problems(self.profile(Name="Ovenbird for " + home), "app.claude-os.desktop")[0]
        self.assertTrue(any("Name holds something private" in p for p in problems), problems)

    def test_entitlements_come_from_the_allowlist(self):
        ents = release.entitlements("T.app.claude-os.desktop", "T")
        self.assertEqual(set(ents) - set(release.ALLOWED),
                         {"com.apple.application-identifier", "com.apple.developer.team-identifier"})
        for key in ("com.apple.security.get-task-allow", "com.apple.security.cs.allow-jit", "anything.else"):
            with self.assertRaises(ValueError, msg=key):
                release.entitlements("T.x", "T", extra={key: True})

    def bundle(self, info, resource=b"icon"):
        app = os.path.join(tempfile.mkdtemp(dir=self.tmp), "Ovenbird.app")
        os.makedirs(os.path.join(app, "Contents", "MacOS"))
        os.makedirs(os.path.join(app, "Contents", "Resources"))
        with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
            plistlib.dump(info, f)
        with open(os.path.join(app, "Contents", "MacOS", "ClaudeOS"), "wb") as f:
            f.write(b"\x00\x00not really a binary, just its strings\x00")
        with open(os.path.join(app, "Contents", "Resources", "AppIcon.icns"), "wb") as f:
            f.write(resource)
        return app

    def test_the_bundle_is_scanned_before_it_is_signed(self):
        clean = {"CFBundleIdentifier": "app.claude-os.desktop", "ClaudeOSCommit": "a" * 40}
        self.assertEqual(release.scan(self.bundle(clean)), [])

    def test_the_profile_is_in_the_bundle_when_it_is_scanned(self):
        with open(os.path.join(release.__file__.rsplit(os.sep, 1)[0], "build.sh")) as f:
            build = f.read()
        checked, copied = build.index("release.py profile"), build.index('cp -X "$COS_RELEASE_PROFILE"')
        self.assertLess(checked, copied)
        self.assertLess(copied, build.index("release.py scan"))
        self.assertLess(build.index("release.py scan"), build.index("codesign --force --options runtime"))

    def embedded(self, text, team):
        app = self.bundle({"CFBundleIdentifier": "x"})
        with open(os.path.join(app, release.EMBEDDED_PROFILE), "w") as f:
            f.write(text)
        decoded = plistlib.dumps({"TeamName": team}).decode() if team else None
        real = release._run
        return app, mock.patch.object(release, "_run", side_effect=lambda cmd: decoded if cmd[0] == "security" else real(cmd))

    def test_the_scan_reads_the_embedded_profile(self):
        app, security = self.embedded("<string>built in %s</string>" % os.path.expanduser("~"), "A Team")
        with security:
            self.assertTrue(any("embedded.provisionprofile" in p and "home folder" in p for p in release.scan(app)))

    def test_only_the_team_name_gets_past_a_private_term(self):
        with open(str(core.home("guard.json")), "w") as f:
            json.dump({"extra": ["A Team", "Some Term"]}, f)
        app, security = self.embedded("<key>TeamName</key><string>A Team</string>", "A Team")
        with security:
            self.assertEqual(release.scan(app), [], "the signature carries the same name (0015, step 2)")
        app, security = self.embedded("<string>A Team</string><string>Some Term</string>", "A Team")
        with security:
            problems = release.scan(app)
        self.assertTrue(any("embedded.provisionprofile" in p for p in problems), problems)
        # With the term set, the name anywhere but the profile is a problem like any other.
        app, security = self.embedded("<string>A Team</string>", "A Team")
        with open(os.path.join(app, "Contents", "Resources", "AppIcon.icns"), "wb") as f:
            f.write(b"made by A Team")
        with security:
            problems = release.scan(app)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("AppIcon.icns", problems[0])

    def test_an_unreadable_profile_lets_nothing_through(self):
        with open(str(core.home("guard.json")), "w") as f:
            json.dump({"extra": ["A Team"]}, f)
        app, security = self.embedded("<string>A Team</string>", None)
        with security:
            self.assertTrue(release.scan(app))

    def test_a_developers_own_keys_never_ship(self):
        problems = release.scan(self.bundle({"ClaudeOSRoot": "/somewhere", "ClaudeOSPath": "/usr/bin"}))
        self.assertTrue(any("ClaudeOSRoot" in p for p in problems))
        self.assertTrue(any("ClaudeOSPath" in p for p in problems))

    def test_a_home_path_anywhere_stops_it(self):
        home = os.path.expanduser("~").encode()
        problems = release.scan(self.bundle({"CFBundleIdentifier": "x"}, resource=b"built in " + home + b"/src"))
        self.assertTrue(any("AppIcon.icns" in p and "home folder" in p for p in problems), problems)
