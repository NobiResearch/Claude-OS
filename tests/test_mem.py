import unittest

from helpers import TempHome

from cos import mem


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


if __name__ == "__main__":
    unittest.main()
