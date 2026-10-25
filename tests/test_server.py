import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from helpers import TempHome

from cos import chat, server


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
