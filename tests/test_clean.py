import os
import tempfile
import unittest

from helpers import TempHome

from cos import clean


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
        with open(os.path.join(proj, "package.json"), "w") as f:
            f.write("{}")
        os.utime(os.path.join(proj, "package.json"), (old, old))
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
