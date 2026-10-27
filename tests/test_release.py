import os
import plistlib
import sys

from helpers import TempHome

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import release  # noqa: E402


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
        app = os.path.join(self.tmp, "Ovenbird.app")
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

    def test_a_developers_own_keys_never_ship(self):
        problems = release.scan(self.bundle({"ClaudeOSRoot": "/somewhere", "ClaudeOSPath": "/usr/bin"}))
        self.assertTrue(any("ClaudeOSRoot" in p for p in problems))
        self.assertTrue(any("ClaudeOSPath" in p for p in problems))

    def test_a_home_path_anywhere_stops_it(self):
        home = os.path.expanduser("~").encode()
        problems = release.scan(self.bundle({"CFBundleIdentifier": "x"}, resource=b"built in " + home + b"/src"))
        self.assertTrue(any("AppIcon.icns" in p and "home folder" in p for p in problems), problems)
