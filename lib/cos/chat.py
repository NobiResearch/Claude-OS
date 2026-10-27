"""Claude sessions for the Ovenbird app.

Each session is a headless Claude Code process speaking stream-json, running in this
repository (so it gets CLAUDE.md, the skills and the boot banner). Permission prompts
don't go to a terminal: Claude Code sends them to us as `can_use_tool` control requests,
we show them in the app, and the human's click is the answer.

Events are normalized into a small vocabulary for the UI:
  ready · user · text_delta · text · tool_use · tool_result · permission ·
  permission_resolved · result · error · closed
"""

import json
import os
import subprocess
import threading
import time
import uuid

from . import core

MAX_RESULT_CHARS = 6000
IDLE_SECONDS = 4 * 3600


class Session:
    def __init__(self, spawn=True):
        self.id = uuid.uuid4().hex[:12]
        self.created = self.touched = time.time()
        self.title = None
        self.state = "starting"
        self.model = None
        self.cost = 0.0
        self.events = []
        self.pending = {}
        self._cond = threading.Condition()
        self._write_lock = threading.Lock()
        self._seq = 0
        self.proc = None
        if not spawn:  # tests drive _handle() directly
            return
        env = dict(os.environ, CLAUDE_OS_APP="1")
        env.pop("CLAUDE_OS_DAEMON", None)
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--include-partial-messages", "--permission-prompt-tool", "stdio"]
        try:
            self.proc = subprocess.Popen(cmd, cwd=str(core.ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                         bufsize=1, env=env, start_new_session=True)
        except OSError as e:
            self.proc = None
            self._emit("error", message="couldn't start Claude Code: %s" % e)
            self._emit("closed")
            return
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._write({"type": "control_request", "request_id": "init-" + self.id,
                     "request": {"subtype": "initialize"}})

    # ------------------------------------------------------------ plumbing

    def _emit(self, type_, **data):
        with self._cond:
            self._seq += 1
            event = dict(data, type=type_, seq=self._seq, ts=time.time())
            self.events.append(event)
            self._cond.notify_all()
        return event

    def _write(self, obj):
        if not self.proc or self.proc.poll() is not None:
            return False
        try:
            with self._write_lock:
                self.proc.stdin.write(json.dumps(obj) + "\n")
                self.proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def _read_stderr(self):
        tail = []
        for line in self.proc.stderr:
            tail = (tail + [line.rstrip()])[-20:]
        self._stderr_tail = "\n".join(tail)

    def _read_stdout(self):
        for line in self.proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            try:
                self._handle(msg)
            except Exception as e:  # one odd message must not kill the session
                self._emit("error", message="couldn't parse a message from Claude Code: %s" % e)
        closing = self.state == "closing"
        self.state = "closed"
        time.sleep(0.2)  # let the stderr reader catch the last lines
        err = getattr(self, "_stderr_tail", "")
        if err and not closing:
            self._emit("error", message=err[-1000:])
        self._emit("closed")

    def _handle(self, msg):
        t = msg.get("type")
        if t == "system" and msg.get("subtype") == "init":
            self.model = msg.get("model")
            self.state = "ready" if self.state == "starting" else self.state
            self._emit("ready", model=self.model, session_id=msg.get("session_id"))
        elif t == "stream_event":
            ev = msg.get("event") or {}
            delta = ev.get("delta") or {}
            if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                self._emit("text_delta", text=delta.get("text", ""))
        elif t == "assistant":
            for block in (msg.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text"):
                    self._emit("text", text=block["text"])
                elif block.get("type") == "tool_use":
                    self._emit("tool_use", id=block.get("id"), name=block.get("name"), input=block.get("input"))
        elif t == "user":
            content = (msg.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    self._emit("tool_result", tool_use_id=block.get("tool_use_id"),
                               content=_flatten(block.get("content"))[:MAX_RESULT_CHARS],
                               is_error=bool(block.get("is_error")))
        elif t == "control_request":
            req = msg.get("request") or {}
            if req.get("subtype") == "can_use_tool":
                rid = msg.get("request_id")
                self.pending[rid] = req
                self._emit("permission", request_id=rid, tool_name=req.get("tool_name"),
                           input=req.get("input"), description=req.get("description"),
                           tool_use_id=req.get("tool_use_id"))
            else:
                self._write({"type": "control_response", "response": {
                    "subtype": "error", "request_id": msg.get("request_id"),
                    "error": "unsupported request %s" % req.get("subtype")}})
        elif t == "control_cancel_request":
            rid = msg.get("request_id")
            if self.pending.pop(rid, None) is not None:
                self._emit("permission_resolved", request_id=rid, allow=False, cancelled=True)
        elif t == "result":
            self.cost += msg.get("total_cost_usd") or 0
            self.state = "idle"
            self._emit("result", is_error=bool(msg.get("is_error")), cost=msg.get("total_cost_usd"),
                       total_cost=round(self.cost, 4), duration_ms=msg.get("duration_ms"),
                       text=msg.get("result") if msg.get("is_error") else None)

    # ------------------------------------------------------------ api

    def send(self, text):
        self.touched = time.time()
        if self.title is None:
            self.title = text.strip().splitlines()[0][:60] if text.strip() else "New chat"
            core.journal("ask", text.strip()[:300], via="app")
        self.state = "busy"
        self._emit("user", text=text)
        ok = self._write({"type": "user", "message": {"role": "user", "content": text}})
        if not ok:
            self._emit("error", message="Claude Code isn't running anymore. Start a new chat.")
        return ok

    def answer(self, request_id, allow, message=None):
        req = self.pending.pop(request_id, None)
        if req is None:
            return False
        self.touched = time.time()
        if allow:
            response = {"behavior": "allow", "updatedInput": req.get("input") or {}}
        else:
            response = {"behavior": "deny", "message": message or "The human declined this in the Ovenbird app."}
        self._write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id, "response": response}})
        summary = describe(req)
        core.journal("approval", "%s: %s" % ("allowed" if allow else "denied", summary)[:300],
                     tool=req.get("tool_name"), allowed=allow, via="app")
        self._emit("permission_resolved", request_id=request_id, allow=allow)
        return True

    def interrupt(self):
        return self._write({"type": "control_request", "request_id": "int-" + uuid.uuid4().hex[:8],
                            "request": {"subtype": "interrupt"}})

    def close(self):
        self.state = "closing"
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                core._killpg(self.proc)

    def wait(self, after, timeout=15.0):
        """Events with seq > after, blocking up to `timeout` for new ones."""
        deadline = time.time() + timeout
        with self._cond:
            while self._seq <= after and self.state != "closed":
                left = deadline - time.time()
                if left <= 0:
                    break
                self._cond.wait(left)
            return [e for e in self.events if e["seq"] > after]

    def summary(self):
        return {"id": self.id, "title": self.title or "New chat", "state": self.state, "model": self.model,
                "cost": round(self.cost, 4), "created": self.created, "touched": self.touched,
                "pending": len(self.pending)}


def describe(req):
    """One line saying what a tool call would do, for logs and dialogs."""
    inp = req.get("input") or {}
    for key in ("command", "file_path", "path", "url", "pattern", "query"):
        if inp.get(key):
            return "%s %s" % (req.get("tool_name"), str(inp[key])[:200])
    return str(req.get("tool_name"))


def _flatten(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return "" if content is None else str(content)


class Registry:
    def __init__(self, factory=Session):
        self.factory = factory
        self.sessions = {}
        self._lock = threading.Lock()

    def create(self):
        with self._lock:
            self._reap()
            s = self.factory()
            self.sessions[s.id] = s
            return s

    def get(self, sid):
        return self.sessions.get(sid)

    def close(self, sid):
        s = self.sessions.pop(sid, None)
        if s:
            s.close()
        return s is not None

    def close_all(self):
        for sid in list(self.sessions):
            self.close(sid)

    def _reap(self):
        now = time.time()
        for sid, s in list(self.sessions.items()):
            if now - s.touched > IDLE_SECONDS and not s.pending:
                self.close(sid)
