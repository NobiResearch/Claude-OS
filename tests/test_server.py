import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from helpers import TempHome

from cos import chat, server


class TestRunFiles(unittest.TestCase):
    def test_minutes_without_the_chatter_before_them(self):
        from cos import server
        text, details = server.split_run("Board seats are deliberating.\n\nSteward is in.\n\n# Board minutes\n\n## Votes\n")
        self.assertTrue(text.startswith("# Board minutes"))
        self.assertIn("## Votes", text)
        self.assertEqual(details, "Board seats are deliberating.\n\nSteward is in.")
        self.assertEqual(server.split_run("# Good morning\n\nRain."), ("# Good morning\n\nRain.", ""))
        self.assertEqual(server.split_run("Fixed a thing\n\n---\nstderr:\nnoise")[0], "Fixed a thing")

    def test_one_cover_per_song(self):
        from unittest import mock
        from cos import server
        with mock.patch.object(server, "artwork_for", lambda track, artist: "https://art.example/%s.jpg" % track):
            own = server.with_artwork({"track": "A", "artist": "B", "artwork": "musicKit://artwork/transient/600x600?id=1"})
            app = server.with_artwork({"track": "A", "artist": "B"})
            self.assertEqual(own["artwork"], app["artwork"], "play/pause answers and polls agree")
            self.assertEqual(server.with_artwork({"track": "A", "artwork": "https://x/y.jpg"})["artwork"], "https://x/y.jpg")
            self.assertNotIn("artwork", server.with_artwork({"track": None}))


class TestChanges(TempHome):
    def test_pending_entries_show_under_unreleased_newest_first(self):
        import os
        from pathlib import Path
        from cos import server
        folder = Path(self.tmp) / "changes"
        folder.mkdir()
        (folder / "README.md").write_text("# not an entry")
        (folder / "2026-10-25-a.md").write_text("- older\n")
        (folder / "2026-10-26-b.md").write_text("- newer\n")
        text = server.with_changes("# Changelog\n\n## Unreleased\n\n- merged before\n\n## 0.7.0\n", folder)
        self.assertLess(text.index("- newer"), text.index("- older"))
        self.assertLess(text.index("- older"), text.index("- merged before"))
        self.assertNotIn("not an entry", text)
        self.assertEqual(server.with_changes("# Changelog\n", Path(self.tmp) / "none"), "# Changelog\n")
        self.assertIn("## Unreleased\n\n- newer", server.with_changes("# Changelog\n", folder))


class TestServerSecurity(TempHome):
    def setUp(self):
        super().setUp()
        self.app = server.App("test-token")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(self.app))
        self.httpd.daemon_threads = True
        self.app.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def request(self, method, path, body=None, token="test-token", host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        headers = {"Host": host or "127.0.0.1:%d" % self.app.port}
        if token:
            headers["X-COS-Token"] = token
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body if isinstance(body, (str, bytes)) or body is None else json.dumps(body), headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, dict(res.getheaders()), data

    def test_api_needs_the_token(self):
        self.assertEqual(self.request("GET", "/api/friction", token=None)[0], 401)
        self.assertEqual(self.request("GET", "/api/friction", token="wrong")[0], 401)
        status, _, data = self.request("GET", "/api/friction")
        self.assertEqual((status, json.loads(data)), (200, []))

    def test_dns_rebinding_is_refused(self):
        self.assertEqual(self.request("GET", "/api/friction", host="evil.example:%d" % self.app.port)[0], 421)
        self.assertEqual(self.request("GET", "/", host="evil.example")[0], 421)

    def test_static_files_and_traversal(self):
        status, headers, data = self.request("GET", "/", token=None)
        self.assertEqual(status, 200)
        self.assertIn(b"Claude OS", data)
        self.assertIn("script-src 'self'", headers.get("Content-Security-Policy", ""))
        for bad in ("/../lib/cos/core.py", "/%2e%2e/lib/cos/core.py", "/..%2flib/cos/core.py"):
            self.assertEqual(self.request("GET", bad, token=None)[0], 404, bad)

    def test_writes_and_errors(self):
        status, _, data = self.request("POST", "/api/friction", {"text": "test friction"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["text"], "test friction")
        self.assertEqual(self.request("POST", "/api/friction", "{not json")[0], 400)
        self.assertEqual(self.request("GET", "/api/nope")[0], 404)
        self.assertEqual(self.request("GET", "/api/chat/0123456789ab/events")[0], 404)
        self.assertEqual(self.request("POST", "/api/clean/apply", {"ids": ["../../etc"]})[0], 400)
        self.assertEqual(self.request("POST", "/api/evolve/merge", {"branch": "main"})[0], 400)

    def test_radio_button_reaches_the_player_route(self):
        from cos import music
        orig = music.player_enabled
        music.player_enabled = lambda: False
        self.addCleanup(setattr, music, "player_enabled", orig)
        status, _, data = self.request("POST", "/api/music/play", {"radio": True})
        self.assertEqual(status, 200)
        self.assertIn("Apple Music", json.loads(data)["error"])

    def answer_dialog(self, approved, what="night"):
        """Stand in for Claude OS.app: when the confirm link opens, write the dialog's answer."""
        from urllib.parse import parse_qs, urlparse
        from cos import core
        real_run = core.run

        def fake_run(cmd, **kw):
            if cmd[:2] == ["open", "-g"] and cmd[2].startswith("claude-os://confirm/" + what):
                rid = parse_qs(urlparse(cmd[2]).query)["rid"][0]
                core.save_json(core.home("state", "confirm-%s.json" % what), {"rid": rid, "approved": approved})
                return core.Result(0, "", "")
            return real_run(cmd, **kw)
        return fake_run

    def test_night_shift_turns_on_only_through_the_apps_own_dialog(self):
        from unittest import mock
        from cos import core
        core.home("state", "app.nonce").write_text("n0nce")
        with mock.patch.object(server.core, "app_running", lambda name: name == "ClaudeOS"):
            with mock.patch.object(server.core, "run", self.answer_dialog(False)):
                status, _, data = self.request("POST", "/api/settings/night", {"on": True})
            self.assertEqual(json.loads(data)["night_shift"], False, "declined in the dialog")
            self.assertFalse((core.config().get("autonomy") or {}).get("night_shift"))
            with mock.patch.object(server.core, "run", self.answer_dialog(True)):
                status, _, data = self.request("POST", "/api/settings/night", {"on": True})
            self.assertEqual(json.loads(data)["night_shift"], True)
            self.assertTrue(core.config()["autonomy"]["night_shift"])
        status, _, data = self.request("POST", "/api/settings/night", {"on": False})
        self.assertEqual(json.loads(data)["night_shift"], False, "turning it off needs no dialog")
        with mock.patch.object(server.core, "app_running", lambda name: False):
            reply = json.loads(self.request("POST", "/api/settings/night", {"on": True})[2])
        self.assertFalse(reply["night_shift"])
        self.assertIn("only be turned on in Claude OS.app", reply["error"])
        self.assertFalse(core.config()["autonomy"]["night_shift"])

    def test_keeping_up_to_date_turns_on_only_in_the_dialog_and_pins_the_repository(self):
        from unittest import mock
        from cos import core
        core.home("state", "app.nonce").write_text("n0nce")
        with mock.patch.object(server.core, "app_running", lambda name: name == "ClaudeOS"):
            with mock.patch.object(server.core, "run", self.answer_dialog(False, "catch-up")):
                reply = json.loads(self.request("POST", "/api/settings/catch-up", {"on": True})[2])
            self.assertFalse(reply["catch_up"])
            self.assertFalse(core.config()["autonomy"]["catch_up"])
            with mock.patch.object(server.core, "run", self.answer_dialog(True, "catch-up")):
                reply = json.loads(self.request("POST", "/api/settings/catch-up", {"on": True})[2])
            self.assertTrue(reply["catch_up"])
        auto = core.config()["autonomy"]
        self.assertTrue(auto["catch_up"])
        url = core.run(["git", "-C", str(core.ROOT), "config", "--get", "remote.origin.url"]).out
        self.assertEqual(auto["catch_up_url"], url, "pinned to the origin it was turned on for")
        self.assertIs(json.loads(self.request("GET", "/api/settings")[2])["catch_up"], True)
        self.assertFalse(json.loads(self.request("POST", "/api/settings/catch-up", {"on": False})[2])["catch_up"])

    def test_the_update_item_and_restart_are_only_for_the_app(self):
        from unittest import mock
        from cos import core
        app = server.App("t")
        self.assertFalse(server.code_state(app)["restart"], "a browser's server can't be restarted for it")
        app.managed = True
        self.assertFalse(server.code_state(app)["restart"], "nothing changed")
        app.head = "0000000"
        self.assertTrue(server.code_state(app)["restart"], "the checkout moved under it")
        status, _, data = self.request("POST", "/api/restart", {})
        self.assertEqual(status, 400)
        exits = []
        self.app.managed = True
        with mock.patch.object(server.os, "_exit", exits.append):
            status, _, data = self.request("POST", "/api/restart", {})
            deadline = time.time() + 3
            while not exits and time.time() < deadline:
                time.sleep(0.05)
        self.assertEqual((status, exits), (200, [server.RESTART]))
        self.assertIn("restarted to update", core.read_journal(days=1)[-1]["msg"])

    def test_a_stale_or_forged_answer_doesnt_count(self):
        from unittest import mock
        from cos import core
        core.home("state", "app.nonce").write_text("n0nce")
        core.save_json(core.home("state", "confirm-night.json"), {"rid": "old", "approved": True})

        def wrong_rid(cmd, **kw):
            core.save_json(core.home("state", "confirm-night.json"), {"rid": "guessed", "approved": True})
            return core.Result(0, "", "")
        with mock.patch.object(server.core, "app_running", lambda name: True), \
                mock.patch.object(server.core, "run", wrong_rid):
            self.assertFalse(server.confirm_natively("night", wait=1.2))

    def test_docs_are_whitelisted(self):
        self.assertEqual(self.request("GET", "/api/doc?name=roadmap")[0], 200)
        self.assertEqual(self.request("GET", "/api/doc?name=../CLAUDE")[0], 404)


class TestChatEvents(TempHome):
    def setUp(self):
        super().setUp()
        self.s = chat.Session(spawn=False)

    def types(self):
        return [e["type"] for e in self.s.events]

    def test_stream_is_normalized(self):
        h = self.s._handle
        h({"type": "system", "subtype": "init", "model": "claude-test", "session_id": "x"})
        h({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hel"}}})
        h({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"},
                                                         {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "bin/cos status"}}]}})
        h({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "ok"}]}]}})
        h({"type": "result", "total_cost_usd": 0.02, "duration_ms": 900, "is_error": False})
        self.assertEqual(self.types(), ["ready", "text_delta", "text", "tool_use", "tool_result", "result"])
        self.assertEqual(self.s.events[4]["content"], "ok")
        self.assertEqual(self.s.state, "idle")
        self.assertEqual([e["seq"] for e in self.s.events], [1, 2, 3, 4, 5, 6])

    def test_permission_round_trip_is_journaled(self):
        self.s._handle({"type": "control_request", "request_id": "r1", "request": {
            "subtype": "can_use_tool", "tool_name": "Bash", "input": {"command": "bin/cos clean apply logs --yes"}}})
        self.assertIn("r1", self.s.pending)
        self.assertEqual(self.s.events[-1]["type"], "permission")
        self.assertTrue(self.s.answer("r1", allow=False))
        self.assertFalse(self.s.answer("r1", allow=True), "answering twice must not work")
        self.assertEqual(self.s.events[-1], dict(self.s.events[-1], type="permission_resolved", allow=False))
        from cos import core
        approvals = core.read_journal(kind="approval")
        self.assertIn("denied: Bash bin/cos clean apply logs --yes", approvals[-1]["msg"])

    def test_wait_returns_only_new_events(self):
        self.s._emit("user", text="hi")
        self.s._emit("text", text="hello")
        self.assertEqual([e["text"] for e in self.s.wait(1, timeout=0)], ["hello"])
        self.assertEqual(self.s.wait(2, timeout=0.05), [])


if __name__ == "__main__":
    unittest.main()


class TestDemoMode(TempHome):
    def test_demo_never_reads_or_changes_the_real_machine(self):
        from cos import demo
        app = server.App("t", demo=True)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(app))
        app.port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            def call(method, path, body=None):
                conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=10)
                conn.request(method, path, body=json.dumps(body) if body is not None else None,
                             headers={"Host": "127.0.0.1:%d" % app.port, "X-COS-Token": "t", "Content-Type": "application/json"})
                res = conn.getresponse()
                return res.status, json.loads(res.read())
            self.assertEqual(call("GET", "/api/status")[1]["system"]["model"], "Mac16,8")
            self.assertEqual(call("POST", "/api/clean/apply", {"ids": ["logs"]})[1]["output"], "(demo mode: nothing was changed)")
            self.assertEqual(call("POST", "/api/friction", {"text": "x"})[1]["demo"], True)
            from cos import mem
            self.assertEqual(mem.frictions(), [], "demo writes must not reach ~/.claude-os")
            status, s = call("POST", "/api/chat", {"text": "do I need to clean up?"})
            self.assertEqual(status, 200)
            self.assertIsInstance(app.chats.get(s["id"]), demo.DemoSession)
        finally:
            httpd.shutdown()
            httpd.server_close()
