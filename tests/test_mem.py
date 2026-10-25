import io
import os
import stat
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace

from helpers import TempHome

from cos import core, mem


class TestMemory(TempHome):
    def test_friction_lifecycle(self):
        a = mem.add_friction("music: catalog play flaky", area="music")
        b = mem.add_friction("clean: missing target")
        self.assertEqual((a["id"], b["id"]), (1, 2))
        mem.close_friction(1, note="fixed")
        open_ids = [f["id"] for f in mem.frictions() if f["status"] == "open"]
        self.assertEqual(open_ids, [2])
        self.assertIsNone(mem.close_friction(99))

    def test_remember_and_forget(self):
        mem.remember("likes ambient")
        mem.remember("dislikes country")
        text = mem.memory_text()
        self.assertIn("- likes ambient", text)
        self.assertEqual(mem.forget("COUNTRY"), 1)
        self.assertNotIn("country", mem.memory_text())
        self.assertIn("likes ambient", mem.memory_text())

    def test_read_only_state_is_one_clear_line(self):
        mem.add_friction("something to close")
        state = core.home()
        os.chmod(state, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, state, stat.S_IRWXU)
        calls = {
            "friction add": lambda: mem.friction_main(SimpleNamespace(friction_cmd="add", text=["x"], area=None)),
            "friction close": lambda: mem.friction_main(SimpleNamespace(friction_cmd="close", id=1, note=None)),
            "remember": lambda: mem.remember_main(SimpleNamespace(fact=["likes x"])),
            "forget": lambda: mem.memory_main(SimpleNamespace(forget="x")),
        }
        for name, call in calls.items():
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(SystemExit, msg=name) as ctx:
                call()
            self.assertEqual(ctx.exception.code, 1, name)
            self.assertIn("can't write private state", err.getvalue(), name)
            self.assertNotIn("Traceback", err.getvalue(), name)


if __name__ == "__main__":
    unittest.main()
