import io
import os
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from helpers import TempHome

from cos import core, hook, mem, system

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "skills")


def frontmatter(name):
    with open(os.path.join(SKILLS, name, "SKILL.md")) as f:
        text = f.read()
    return text, re.search(r"^description: (.*)$", text, re.M).group(1)


class TestEverywhere(TempHome):
    def test_install_links_the_mac_skills_and_uninstall_removes_only_ours(self):
        mine = os.path.join(system.skills_dir(), "update")
        os.makedirs(mine)  # the human's own skill with the same name stays
        with redirect_stdout(io.StringIO()):
            steps = system.link_skills()
        self.assertTrue(any("left it alone" in s and "update" in s for s in steps))
        for name in ("music", "tidy", "startup"):
            path = os.path.join(system.skills_dir(), name)
            self.assertTrue(os.path.islink(path), name)
            self.assertEqual(os.path.realpath(path), os.path.realpath(os.path.join(SKILLS, name)))
        self.assertFalse(os.path.islink(mine))
        self.assertEqual(system.link_skills()[-1].count("/music"), 1, "running it again is harmless")
        self.assertEqual(system.unlink_skills(), 3)
        self.assertTrue(os.path.isdir(mine), "the human's own skill is still there")
        self.assertEqual(sorted(os.listdir(system.skills_dir())), ["update"])

    def test_install_without_daemons_says_which_are_still_running(self):
        rows = [{"name": "pulse", "loaded": True, "llm": False}, {"name": "morning", "loaded": True, "llm": True},
                {"name": "evolve", "loaded": False, "llm": True}]
        note = system.daemon_note(rows, skipped=True)
        self.assertEqual(note[0], "Background jobs left as they are: pulse, morning running.")
        self.assertEqual(note[1], "LLM daemons are opt-in (they use your Claude plan): cos daemon install evolve")
        none = [dict(r, loaded=False) for r in rows]
        self.assertIn("No background jobs are running", system.daemon_note(none, skipped=True)[0])
        everything = [dict(r, loaded=True) for r in rows]
        self.assertEqual(system.daemon_note(everything, skipped=False), [], "nothing to suggest")

    def test_only_the_mac_skills_go_everywhere(self):
        self.assertEqual(system.EVERYWHERE, ("music", "tidy", "update", "startup"))
        for repo_only in ("brief", "board", "evolve", "lab"):
            self.assertNotIn(repo_only, system.EVERYWHERE)

    def test_shipped_skills_run_anywhere_and_say_what_they_are_not_for(self):
        for name in system.EVERYWHERE:
            text, desc = frontmatter(name)
            self.assertIn("Mac", desc, name)
            self.assertIn("Not for", desc, name)
            self.assertIsNone(re.search(r"(?<![`/])bin/cos (?!…)", text), "%s calls bin/cos, which only works in the repo" % name)
            self.assertIn("never the project or client", text, name)
        self.assertIn("project's own dependencies", frontmatter("update")[1])
        self.assertIn("code or a project", frontmatter("tidy")[1])
        self.assertIn("video, app or other project", frontmatter("music")[1])
        self.assertIn("cos memory", frontmatter("music")[0], "no boot banner outside the repo")

    def test_what_loads_everywhere_is_protected(self):
        for path in (".claude/skills/music/SKILL.md", "lib/cos/system.py"):
            self.assertTrue(hook.protected(path), path)

    def test_friction_from_another_project_is_marked_not_located(self):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        elsewhere = tempfile.mkdtemp(prefix="client-project-")
        os.chdir(elsewhere)
        item = mem.add_friction("the tidy skill missed a cache")
        self.assertTrue(item["outside"])
        self.assertNotIn(elsewhere, str(core.load_json(core.home("friction.json"))))
        os.chdir(str(core.home()))
        self.assertNotIn("outside", mem.add_friction("seen from Claude OS's own state folder"))
        with redirect_stdout(io.StringIO()) as out:
            mem.friction_main(SimpleNamespace(friction_cmd=None, all=False, json=False))
        self.assertIn("from another project; don't quote it", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class TestNoUsernameInOutput(TempHome):
    """What install and doctor print gets pasted into public bug reports."""

    def test_paths_print_from_the_home_folder(self):
        home = os.path.expanduser("~")
        self.assertEqual(system._tilde(os.path.join(home, ".claude-os")), "~/.claude-os")
        self.assertEqual(system._tilde(home), "~")
        self.assertEqual(system._tilde(home + "-other/x"), home + "-other/x", "only the home folder itself")
        self.assertEqual(system._tilde("/opt/homebrew/bin"), "/opt/homebrew/bin")
