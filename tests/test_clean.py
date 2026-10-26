import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from helpers import TempHome

from cos import clean, core


class TestTargets(unittest.TestCase):
    def test_registry_is_well_formed(self):
        ids = [t.id for t in clean.TARGETS]
        self.assertEqual(len(ids), len(set(ids)), "target ids must be unique")
        for t in clean.TARGETS:
            self.assertIn(t.safety, clean.SAFETY_ORDER, t.id)
            self.assertIn(t.action, ("contents", "cmd", "list"), t.id)
            if t.action == "cmd":
                self.assertTrue(t.cmd and t.requires, t.id)
            self.assertTrue(t.why.endswith("."), "%s: explain why in a sentence" % t.id)

    def test_careful_targets_never_delete_contents_blindly(self):
        for t in clean.TARGETS:
            if t.safety == "careful":
                self.assertTrue(t.action == "list" or t.apply_fn, t.id)


class TestRemovalGuard(TempHome):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(os.environ["HOME"], "Library", "Caches", "app"))

    def test_refuses_outside_home_and_shallow_paths(self):
        home = os.environ["HOME"]
        for bad in ("/", "/tmp", tempfile.gettempdir(), home, os.path.join(home, "Library"),
                    os.path.join(home, "Library", "Caches"), os.path.join(home, "Documents")):
            with self.assertRaises(ValueError, msg=bad):
                clean._guard(bad)
        clean._guard(os.path.join(home, "Library", "Caches", "app"))

    def test_delete_contents_keeps_the_folder(self):
        cache = os.path.join(os.environ["HOME"], "Library", "Caches", "app")
        os.makedirs(os.path.join(cache, "nested"))
        with open(os.path.join(cache, "f.bin"), "wb") as f:
            f.write(b"x" * 1000)
        clean.delete_contents(cache)
        self.assertTrue(os.path.isdir(cache))
        self.assertEqual(os.listdir(cache), [])

    def test_symlinks_are_unlinked_not_followed(self):
        home = os.environ["HOME"]
        precious = os.path.join(self.tmp, "precious")
        os.makedirs(precious)
        open(os.path.join(precious, "keep.txt"), "w").close()
        cache = os.path.join(home, "Library", "Caches", "app")
        os.symlink(precious, os.path.join(cache, "link"))
        clean.delete_contents(cache)
        self.assertTrue(os.path.exists(os.path.join(precious, "keep.txt")))


class TestNodeModules(TempHome):
    def test_dev_roots_dedupe_case_insensitive_aliases(self):
        home = os.environ["HOME"]
        os.makedirs(os.path.join(home, "code"))
        roots = clean.dev_roots()
        if os.path.exists(os.path.join(home, "Code")):  # case-insensitive volume
            self.assertEqual(len(roots), 1)

    def test_recent_file_deep_in_tree_keeps_project_active(self):
        proj = os.path.join(os.environ["HOME"], "Developer", "app")
        os.makedirs(os.path.join(proj, "node_modules", "dep"))
        os.makedirs(os.path.join(proj, "src", "components"))
        old = 1_000_000_000  # 2001
        for root, dirs, files in os.walk(proj):
            os.utime(root, (old, old))
        for name in ("package.json", "package-lock.json"):
            with open(os.path.join(proj, name), "w") as f:
                f.write("{}")
            os.utime(os.path.join(proj, name), (old, old))
        self.assertEqual([p.name for p in clean.stale_node_modules()], ["node_modules"])
        open(os.path.join(proj, "src", "components", "New.tsx"), "w").close()  # fresh edit, deep down
        self.assertEqual(clean.stale_node_modules(), [])


class TestMeasure(unittest.TestCase):
    def test_du_counts_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "f"), "wb") as f:
                f.write(b"x" * 100000)
            self.assertGreaterEqual(clean.du(d), 100000)

    def test_apply_dry_run_without_yes(self):
        self.assertEqual(clean.apply(["xcode-derived-data"], yes=False), 2)


class TestReviewFindings(TempHome):
    """An independent review of cos clean (night of 26 October): each finding, kept fixed."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        from pathlib import Path
        self.home = os.environ["HOME"]
        patch = mock.patch.object(clean, "HOME", Path(self.home))
        patch.start()
        self.addCleanup(patch.stop)

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def touch(self, *parts, old=False):
        p = self.path(*parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("x")
        if old:
            os.utime(p, (1_000_000_000, 1_000_000_000))
        return p

    def test_a_cache_folder_that_is_a_symlink_is_never_followed(self):
        thesis = self.touch("Documents", "Thesis", "chapter1.md")
        os.makedirs(self.path("Library", "Developer", "Xcode"))
        os.symlink(os.path.dirname(thesis), self.path("Library", "Developer", "Xcode", "DerivedData"))
        with redirect_stdout(io.StringIO()) as out:
            clean.delete_contents(self.path("Library", "Developer", "Xcode", "DerivedData"))
        self.assertTrue(os.path.exists(thesis), "the thesis is still there")
        self.assertIn("symlink", out.getvalue())
        with self.assertRaises(ValueError):
            clean.remove(self.path("Library", "Developer", "Xcode", "DerivedData", "chapter1.md"))

    def test_a_downloads_folder_that_links_elsewhere_isnt_downloads(self):
        self.touch("Documents", "old.pdf", old=True)
        os.symlink(self.path("Documents"), self.path("Downloads"))
        self.assertEqual(clean.old_downloads(), [])

    def test_a_folder_with_a_fresh_file_inside_isnt_an_old_download(self):
        self.touch("Downloads", "client-site", "index.html")  # edited today
        os.utime(self.path("Downloads", "client-site"), (1_000_000_000, 1_000_000_000))
        self.touch("Downloads", "setup.dmg", old=True)
        self.assertEqual([p.name for p in clean.old_downloads()], ["setup.dmg"])

    def test_only_reviewed_items_are_trashed(self):
        from unittest import mock
        for i in range(25):
            self.touch("Downloads", "file%02d.zip" % i, old=True)
        self.assertIsNone(clean._reviewed("downloads-old") if not core.cache_get("clean") else None)
        with mock.patch.object(clean, "du", return_value=1):
            scan = {"targets": [clean.measure(clean.BY_ID["downloads-old"])]}
        scan["targets"][0]["details"] = scan["targets"][0]["details"][:15]  # what someone actually saw
        core.cache_put("clean", scan)
        trashed = []
        with mock.patch.object(clean, "trash", lambda ps: trashed.extend(ps)):
            clean.apply_downloads(clean.BY_ID["downloads-old"])
        self.assertEqual(len(trashed), 15, "never more than was reviewed")

    def test_without_a_scan_nothing_on_a_list_is_removed(self):
        from unittest import mock
        self.touch("Downloads", "setup.dmg", old=True)
        trashed = []
        with mock.patch.object(clean, "trash", lambda ps: trashed.extend(ps)), redirect_stdout(io.StringIO()) as out:
            clean.apply_downloads(clean.BY_ID["downloads-old"])
        self.assertEqual(trashed, [])
        self.assertIn("scan first", out.getvalue())

    def test_trashing_downloads_and_emptying_the_trash_together_is_refused(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            clean.apply(["downloads-old", "trash"], yes=True)

    def test_commands_run_from_home_and_uv_ignores_project_config(self):
        from unittest import mock
        uv = clean.BY_ID["uv-cache"]
        self.assertIn("--no-config", uv.cmd)
        seen = []

        def run(cmd, **kw):
            seen.append((cmd[0], kw.get("cwd")))
            return core.Result(0, "", "")
        with mock.patch.object(clean.core, "run", run), mock.patch.object(clean, "measure", return_value={"bytes": 0}), \
                mock.patch.object(clean.core, "app_running", lambda *a, **k: False), redirect_stdout(io.StringIO()):
            clean.apply(["npm-cache"], yes=True)
        self.assertIn(("npm", self.home), seen)

    def test_node_modules_needs_a_manifest_and_a_lockfile(self):
        proj = self.path("Developer", "app")
        os.makedirs(os.path.join(proj, "node_modules", "dep"))
        for root, dirs, files in os.walk(proj):
            os.utime(root, (1_000_000_000, 1_000_000_000))
        self.assertEqual(clean.stale_node_modules(), [], "no package.json: npm install can't put it back")

    def test_running_apps_keep_their_caches_and_some_folders_are_not_caches(self):
        from unittest import mock
        self.assertIn("pypoetry", clean.NOT_REALLY_CACHES)
        out = '  1) "Spotify" ASN:0x0-0x1:\n    bundleID="com.spotify.client"\n'
        with mock.patch.object(clean.core, "run", return_value=core.Result(0, out, "")):
            self.assertEqual(clean.running_apps(), {"spotify", "com.spotify.client"})

    def test_one_odd_item_doesnt_stop_the_others(self):
        from unittest import mock
        outside = tempfile.mkdtemp(prefix="cos-elsewhere-")
        self.addCleanup(shutil.rmtree, outside, True)
        ok = self.touch("Downloads", "a.dmg", old=True)
        asked = []
        with mock.patch.object(clean.core, "osascript", lambda s, timeout=0: asked.append(s)), \
                redirect_stdout(io.StringIO()) as out:
            clean.trash([outside + "/b.dmg", ok])
        self.assertEqual(len(asked), 1)
        self.assertIn("kept", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class TestRuntimes(unittest.TestCase):
    def test_keeps_the_newest_runtime_per_platform(self):
        data = {
            "a": {"platformIdentifier": "ios", "version": "26.5", "sizeBytes": 8, "deletable": True},
            "b": {"platformIdentifier": "ios", "version": "26.4.1", "sizeBytes": 9, "deletable": True},
            "c": {"platformIdentifier": "ios", "version": "27.0", "sizeBytes": 7, "deletable": True},
            "d": {"platformIdentifier": "tvos", "version": "26.4", "sizeBytes": 3, "deletable": False},
            "e": {"platformIdentifier": "tvos", "version": "27.0", "sizeBytes": 3, "deletable": True},
            "f": {"platformIdentifier": "watch", "version": "11.0", "sizeBytes": 2, "deletable": True},
        }
        self.assertEqual([rt["id"] for rt in clean.pick_old_runtimes(data)], ["b", "a"])
        self.assertEqual(clean.pick_old_runtimes({}), [])


class TestApplyTotals(TempHome):
    def setUp(self):
        super().setUp()
        from unittest import mock
        self.mock = mock

    def test_what_the_apply_deleted_counts_when_measuring_comes_back_empty(self):
        # The first weekly cleanup: CoreSimulator answered nothing just before the delete.
        t = clean.Target("t-runtimes", "x", "y", "review", measure=lambda t: (0, []), apply=lambda t: 22 * 2 ** 30)
        with self.mock.patch.dict(clean.BY_ID, {"t-runtimes": t}), self.mock.patch("builtins.print"):
            self.assertEqual(clean.apply(["t-runtimes"], yes=True), 0)
        from cos import core
        entry = core.read_journal(days=1, kind="action")[-1]
        self.assertEqual(entry["freed"], 22 * 2 ** 30)

    def test_a_cache_in_use_is_skipped_with_a_reason(self):
        ran = []
        t = clean.Target("t-uv", "x", "y", "safe", action="cmd", cmd=["true"], busy=("uv",),
                         measure=lambda t: ran.append("measure") or (5, []))
        out = []
        with self.mock.patch.dict(clean.BY_ID, {"t-uv": t}), \
                self.mock.patch.object(clean.core, "app_running", lambda name: name == "uv"), \
                self.mock.patch("builtins.print", lambda *a: out.append(" ".join(map(str, a)))):
            clean.apply(["t-uv"], yes=True)
        self.assertEqual(ran, [], "nothing ran, nothing waited")
        self.assertTrue(any("skipped: uv is running" in l for l in out))
