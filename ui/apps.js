// Claude OS apps. Each app renders into a window body using COS helpers.
"use strict";

(function () {
  const { api, job, h, clear, icon, fmt, toast } = COS;

  // ------------------------------------------------------------ shared bits
  const pill = (level, text) => h("span", { class: "pill " + level }, text || level);
  const card = (title, ...kids) => h("div", { class: "card" }, title ? h("div", { class: "card-title" }, title) : null, ...kids);
  const btn = (label, onclick, kind, ico) => h("button", { class: "btn " + (kind || ""), onclick }, ico ? icon(ico, 14) : null, label);
  const spinner = () => h("span", { class: "spinner" });
  const empty = (text, sub) => h("div", { class: "empty" }, h("div", { class: "empty-mark" }, "◆"), h("div", null, text), sub ? h("div", { class: "empty-sub" }, sub) : null);
  const meter = (frac, tone) => h("div", { class: "meter " + (tone || "") }, h("div", { class: "meter-fill", style: { width: Math.max(0, Math.min(100, frac * 100)) + "%" } }));
  function ring(frac, label, sub, tone) {
    const pct = Math.round(Math.max(0, Math.min(1, frac)) * 100);
    return h("div", { class: "ring " + (tone || ""), style: { "--p": pct } }, h("div", { class: "ring-inner" }, h("div", { class: "ring-label" }, label), sub ? h("div", { class: "ring-sub" }, sub) : null));
  }
  function tabs(w, names, renderers, initial) {
    const bar = h("div", { class: "tabs" });
    const pane = h("div", { class: "tab-pane" });
    let current = initial || names[0];
    const show = (name) => {
      current = name;
      [...bar.children].forEach((b) => b.classList.toggle("active", b.dataset.name === name));
      clear(pane);
      renderers[name](pane);
    };
    names.forEach((n) => bar.appendChild(h("button", { class: "tab", "data-name": n, onclick: () => show(n) }, n)));
    w.body.appendChild(h("div", { class: "tabbed" }, bar, pane));
    show(current);
    return { show, get current() { return current; } };
  }
  async function loading(el, fn) {
    clear(el).appendChild(h("div", { class: "loading" }, spinner(), "Loading…"));
    try { await fn(); } catch (e) { clear(el).appendChild(h("div", { class: "error-box" }, "Couldn't load: " + e.message)); }
  }
  function jobPanel() {
    const out = h("pre", { class: "job-out" });
    const head = h("div", { class: "job-head" }, spinner(), h("span", null, "Working…"));
    const el = h("div", { class: "job" }, head, out);
    return {
      el,
      update(j) {
        out.textContent = j.output || "";
        out.scrollTop = out.scrollHeight;
        if (j.done) {
          clear(head).appendChild(h("span", { class: j.rc === 0 ? "ok-text" : "bad-text" }, j.rc === 0 ? "Done" : "Finished with errors (" + j.rc + ")"));
          head.appendChild(h("span", { class: "muted" }, " · " + j.seconds + "s"));
        }
      },
    };
  }
  const shortPath = (p) => { const parts = String(p || "").split("/"); return parts.length > 3 ? "…/" + parts.slice(-2).join("/") : p; };

  // ------------------------------------------------------------ Claude
  const SUGGESTIONS = ["Do I need to clean up my Mac?", "Find me a chill song on Apple Music", "Catch me up on what's new",
    "What's outdated on my Mac?", "What should Claude OS learn next?"];

  function toolLabel(name, input) {
    input = input || {};
    switch (name) {
      case "Bash": return { ico: "terminal", text: input.command || "shell" };
      case "Read": return { ico: "file", text: "Read " + shortPath(input.file_path) };
      case "Edit": case "Write": case "MultiEdit": case "NotebookEdit": return { ico: "file", text: name + " " + shortPath(input.file_path || input.notebook_path) };
      case "Grep": case "Glob": return { ico: "search", text: name + " " + (input.pattern || "") };
      case "WebSearch": return { ico: "globe", text: "Search the web: " + (input.query || "") };
      case "WebFetch": return { ico: "globe", text: "Fetch " + (input.url || "") };
      case "Skill": return { ico: "spark", text: "Using /" + (input.skill || input.name || input.command || "skill") };
      case "Agent": case "Task": return { ico: "spark", text: "Asking " + (input.subagent_type || "a helper") + (input.description ? ": " + input.description : "") };
      case "TodoWrite": return { ico: "check", text: "Planning steps" };
      default: return { ico: "spark", text: name.replace(/^mcp__[^_]+__/, "") };
    }
  }

  COS.register({
    id: "claude", title: "Claude", icon: "claude", color: "linear-gradient(140deg,#ec916f,#b4532f)", size: [640, 680],
    keywords: "chat ask assistant",
    render(w) {
      let sid = null, stop = null, lastSeq = 0, live = null, busy = false, pending = 0;
      const chips = {};
      const log = h("div", { class: "chat-log" });
      const working = h("div", { class: "chat-working", hidden: true }, h("span", { class: "pulse-mark" }, "◆"), h("span", null, "Claude is working…"));
      const input = h("textarea", { class: "chat-input", rows: 1, placeholder: "Ask Claude anything about your Mac…" });
      const sendBtn = h("button", { class: "chat-send", title: "Send (Enter)", onclick: () => submit() }, icon("send", 16));
      const cost = h("span", { class: "chat-cost" });
      w.actions.appendChild(cost);
      w.actions.appendChild(btn("New chat", () => reset(), "ghost small", "plus"));
      w.body.appendChild(h("div", { class: "chat" }, log, working, h("div", { class: "chat-composer" }, input, sendBtn)));

      function welcome() {
        clear(log).appendChild(h("div", { class: "chat-welcome" },
          h("div", { class: "chat-welcome-mark" }, "◆"),
          h("div", { class: "chat-welcome-title" }, "What can I do for you?"),
          h("div", { class: "chat-welcome-sub" }, "I can see and run this Mac through Claude OS. Anything that changes something asks you first."),
          h("div", { class: "chips" }, SUGGESTIONS.map((s) => h("button", { class: "chip", onclick: () => ask(s) }, s)))));
      }
      welcome();

      function setBusy(b) {
        busy = b;
        working.hidden = !b || !!live;
        clear(sendBtn).appendChild(icon(b ? "stop" : "send", 16));
        sendBtn.title = b ? "Stop" : "Send (Enter)";
        sendBtn.classList.toggle("stop", b);
      }
      function scroll() { log.scrollTop = log.scrollHeight; }
      function bubble(role, raw) {
        const content = h("div", { class: "md" });
        const el = h("div", { class: "msg " + role }, content);
        if (role === "user") content.textContent = raw; else content.innerHTML = MD.render(raw);
        log.appendChild(el);
        return { el, content, raw };
      }
      let renderQueued = false;
      function renderLive() {
        if (renderQueued) return;
        renderQueued = true;
        requestAnimationFrame(() => { renderQueued = false; if (live) { live.content.innerHTML = MD.render(live.raw); scroll(); } });
      }
      function setPending(delta) {
        pending = Math.max(0, pending + delta);
        COS.badge("claude", pending || null);
      }

      function handle(e) {
        if (e.seq) lastSeq = Math.max(lastSeq, e.seq);
        switch (e.type) {
          case "user":
            if (log.querySelector(".chat-welcome")) clear(log);
            bubble("user", e.text);
            setBusy(true);
            break;
          case "text_delta":
            if (!live) { live = bubble("assistant", ""); working.hidden = true; }
            live.raw += e.text;
            renderLive();
            break;
          case "text":
            if (live) { live.raw = e.text; live.content.innerHTML = MD.render(e.text); live = null; }
            else bubble("assistant", e.text);
            working.hidden = !busy;
            break;
          case "tool_use": {
            live = null;
            const t = toolLabel(e.name, e.input);
            const detail = h("pre", { class: "tool-detail", hidden: true });
            const status = h("span", { class: "tool-status" }, spinner());
            const chip = h("div", { class: "tool" },
              h("button", { class: "tool-head", onclick: () => { detail.hidden = !detail.hidden; } }, icon(t.ico, 13), h("span", { class: "tool-text" }, t.text), status),
              detail);
            detail.textContent = JSON.stringify(e.input, null, 2);
            chips[e.id] = { chip, status, detail };
            log.appendChild(chip);
            working.hidden = false;
            break;
          }
          case "tool_result": {
            const c = chips[e.tool_use_id];
            if (c) {
              clear(c.status).appendChild(icon(e.is_error ? "x" : "check", 13));
              c.chip.classList.add(e.is_error ? "error" : "done");
              c.detail.textContent = (e.content || "(no output)").slice(0, 6000);
            }
            break;
          }
          case "permission": {
            setPending(1);
            const t = toolLabel(e.tool_name, e.input);
            const what = e.tool_name === "Bash" ? "run a command" : /Edit|Write/.test(e.tool_name) ? "change a file" : "use " + t.text;
            const actions = h("div", { class: "perm-actions" },
              btn("Deny", () => answer(e.request_id, false, cardEl), "ghost"),
              btn("Allow", () => answer(e.request_id, true, cardEl), "primary"));
            const cardEl = h("div", { class: "perm", "data-rid": e.request_id },
              h("div", { class: "perm-title" }, icon("claude", 14), "Claude wants to " + what),
              h("pre", { class: "perm-cmd" }, t.text),
              e.description ? h("div", { class: "perm-desc" }, e.description) : null,
              actions);
            log.appendChild(cardEl);
            COS.focus("claude");
            if (!document.hasFocus()) toast("Claude is waiting for your OK", "accent");
            break;
          }
          case "permission_resolved": {
            const el = log.querySelector('.perm[data-rid="' + e.request_id + '"]');
            if (el && !el.classList.contains("resolved")) { resolveCard(el, e.allow, e.cancelled); setPending(-1); }
            break;
          }
          case "result":
            live = null;
            setBusy(false);
            cost.textContent = e.total_cost ? "$" + e.total_cost.toFixed(2) : "";
            if (e.is_error && e.text) log.appendChild(h("div", { class: "chat-error" }, e.text));
            COS.refreshStatus();
            break;
          case "error":
            log.appendChild(h("div", { class: "chat-error" }, e.message));
            break;
          case "closed":
            setBusy(false);
            log.appendChild(h("div", { class: "chat-note" }, "Session ended. Your next message starts a new one."));
            sid = null;
            break;
          case "stream_end":
            if (sid) setTimeout(() => sid && connect(), 1200);
            break;
        }
        scroll();
      }

      function resolveCard(el, allow, cancelled) {
        el.classList.add("resolved", allow ? "allowed" : "denied");
        const a = el.querySelector(".perm-actions");
        if (a) a.replaceWith(h("div", { class: "perm-result" }, cancelled ? "No longer needed" : allow ? "Allowed" : "Denied"));
      }
      async function answer(rid, allow, el) {
        try {
          await api("/api/chat/" + sid + "/permission", { body: { request_id: rid, allow } });
          if (!el.classList.contains("resolved")) { resolveCard(el, allow); setPending(-1); }
        } catch (e) { toast("Couldn't answer: " + e.message, "bad"); }
      }
      function connect() {
        if (stop) stop();
        stop = COS.stream("/api/chat/" + sid + "/events?after=" + lastSeq, handle);
      }
      async function ask(text) {
        text = (text || "").trim();
        if (!text) return;
        setBusy(true);
        try {
          if (!sid) {
            const s = await api("/api/chat", { body: { text } });
            sid = s.id;
            lastSeq = 0;
            connect();
          } else {
            await api("/api/chat/" + sid + "/send", { body: { text } });
          }
        } catch (e) {
          setBusy(false);
          log.appendChild(h("div", { class: "chat-error" }, "Couldn't reach Claude: " + e.message));
        }
      }
      function submit() {
        if (busy) { if (sid) api("/api/chat/" + sid + "/interrupt", { body: {} }).catch(() => {}); return; }
        const text = input.value;
        input.value = "";
        autosize();
        ask(text);
      }
      function reset() {
        if (stop) stop();
        if (sid) api("/api/chat/" + sid + "/close", { body: {} }).catch(() => {});
        sid = null; live = null; lastSeq = 0; pending = 0;
        COS.badge("claude", null);
        cost.textContent = "";
        setBusy(false);
        welcome();
        input.focus({ preventScroll: true });
      }
      function autosize() { input.style.height = "auto"; input.style.height = Math.min(160, input.scrollHeight) + "px"; }
      input.addEventListener("input", autosize);
      input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } });
      w.ask = ask;
      w.cleanup.push(() => { if (stop) stop(); if (sid) api("/api/chat/" + sid + "/close", { body: {} }).catch(() => {}); COS.badge("claude", null); });
      setTimeout(() => input.focus({ preventScroll: true }), 50);
    },
  });

  // ------------------------------------------------------------ Vitals
  COS.register({
    id: "vitals", title: "Vitals", icon: "vitals", color: "linear-gradient(140deg,#e9727f,#a63a52)", size: [620, 600],
    keywords: "status battery disk memory cpu security",
    render(w) {
      const root = h("div", { class: "pad" });
      w.body.appendChild(root);
      w.actions.appendChild(btn("", () => draw(), "ghost small icon-only", "refresh"));
      const off = [];
      async function draw() {
        try {
          const s = await api("/api/status");
          paint(s);
        } catch (e) { clear(root).appendChild(h("div", { class: "error-box" }, e.message)); }
      }
      function paint(s) {
        clear(root);
        const d = s.disk, m = s.memory, b = s.battery, sy = s.system, sec = s.security || {};
        const used = 1 - d.free / d.total;
        root.appendChild(h("div", { class: "vitals-hero" },
          ring(used, Math.round(used * 100) + "%", "disk used", used > 0.9 ? "bad" : used > 0.8 ? "warn" : ""),
          h("div", { class: "vitals-hero-text" },
            h("div", { class: "big" }, fmt.bytes(d.free) + " free"),
            h("div", { class: "muted" }, "of " + fmt.bytes(d.total) + " · " + sy.model + " · macOS " + sy.macos),
            h("div", { class: "muted" }, sy.chip + " · " + sy.cores + " cores · up " + fmt.uptime(s.uptime)))));
        const signals = s.signals.length ? s.signals.map((x) => h("div", { class: "signal " + x.level }, x.level === "warn" ? "⚠ " : "· ", x.msg))
          : [h("div", { class: "signal ok" }, "All quiet.")];
        root.appendChild(h("div", { class: "grid2" },
          card("Memory", h("div", { class: "kv-big" }, fmt.bytes(m.used), h("span", { class: "muted" }, " of " + fmt.bytes(m.total))), meter(m.used / m.total, m.used / m.total > 0.9 ? "bad" : ""), h("div", { class: "muted small" }, "swap " + fmt.bytes(m.swap_used))),
          b ? card("Battery", h("div", { class: "kv-big" }, b.percent + "%", h("span", { class: "muted" }, " " + b.state)), meter(b.percent / 100, b.percent < 20 ? "bad" : "ok"),
            h("div", { class: "muted small" }, (b.health_pct ? "health " + b.health_pct + "% · " : "") + (b.cycles != null ? b.cycles + " cycles · " : "") + "on " + b.source))
            : card("Power", h("div", { class: "muted" }, "No battery — desktop Mac.")),
          card("Load", h("div", { class: "kv-big" }, (s.load[0] || 0).toFixed(2)), h("div", { class: "muted small" }, "1 / 5 / 15 min: " + s.load.map((x) => x.toFixed(2)).join(" · "))),
          card("Security", h("div", { class: "badges" },
            ["filevault", "sip", "firewall", "gatekeeper"].map((k) => h("span", { class: "sec " + (sec[k] ? "on" : sec[k] === false ? "off" : "") }, { filevault: "FileVault", sip: "SIP", firewall: "Firewall", gatekeeper: "Gatekeeper" }[k]))),
            // Through the chat, so the Allow card and macOS's password dialog both come first.
            sec.firewall === false ? h("div", { class: "row pad-t" }, btn("Turn on the firewall…", () => COS.ask("Turn on my firewall."), "ghost small"),
              h("span", { class: "muted small" }, "macOS asks for your password")) : null),
        ));
        root.appendChild(card("Signals", ...signals));
        const startupBody = h("div", { class: "muted" }, "Checking what starts with this Mac…");
        root.appendChild(card("Starts with your Mac", startupBody));
        api("/api/startup").then((st) => {
          clear(startupBody);
          if (st.error) { startupBody.appendChild(h("span", null, st.error)); return; }
          startupBody.appendChild(h("div", { class: "kv-big" }, String(st.enabled), h("span", { class: "muted" }, " of " + st.count + " items on")));
          startupBody.appendChild(h("div", { class: st.flagged ? "warn-text small" : "muted small" },
            st.flagged ? st.flagged + " worth a look" : "Nothing unusual."));
          startupBody.appendChild(h("div", { class: "row" }, btn("Ask Claude to review", () => COS.ask("/startup"), "ghost small")));
        }).catch(() => { startupBody.textContent = "Couldn't read the login items."; });
        if (s.top) {
          const table = (rows, val) => h("table", { class: "mini" }, h("tbody", null, rows.map((p) => h("tr", null, h("td", null, p.name), h("td", { class: "num" }, val(p))))));
          root.appendChild(h("div", { class: "grid2" },
            card("Top CPU", table(s.top.cpu, (p) => p.cpu.toFixed(0) + "%")),
            card("Top memory", table(s.top.memory, (p) => fmt.bytes(p.rss)))));
        }
        root.appendChild(h("div", { class: "chips" },
          h("button", { class: "chip", onclick: () => COS.ask("Look at my Mac's vitals and tell me if anything needs attention.") }, "◆ Ask Claude to look")));
      }
      draw();
      const t = setInterval(draw, 15000);
      w.cleanup.push(() => clearInterval(t));
      off.push(t);
    },
  });

  // ------------------------------------------------------------ Storage
  COS.register({
    id: "storage", title: "Storage", icon: "storage", color: "linear-gradient(140deg,#f0b75e,#b87a24)", size: [680, 640],
    keywords: "clean disk space cache tidy",
    render(w) {
      const root = h("div", { class: "pad" });
      w.body.appendChild(root);
      let data = null, ts = null;
      async function load(scan, deep) {
        clear(root).appendChild(h("div", { class: "loading" }, spinner(), scan ? "Scanning your disk (about 10 seconds)…" : "Loading…"));
        try {
          const r = await api("/api/clean" + (scan ? "?scan=1" + (deep ? "&deep=1" : "") : ""));
          data = r.data; ts = r.ts;
          paint();
        } catch (e) { clear(root).appendChild(h("div", { class: "error-box" }, e.message)); }
      }
      async function reclaim(ids, label) {
        const targets = data.targets.filter((t) => ids.includes(t.id));
        const total = targets.reduce((a, t) => a + t.bytes, 0);
        const ok = await COS.confirm({
          title: "Reclaim " + fmt.bytes(total) + "?",
          body: h("div", null, targets.map((t) => h("div", { class: "confirm-row" }, pill(t.safety), h("b", null, " " + t.label), h("div", { class: "muted small" }, t.why)))),
          ok: "Reclaim", danger: targets.some((t) => t.safety !== "safe"),
        });
        if (!ok) return;
        const panel = jobPanel();
        root.prepend(panel.el);
        const j = await job("/api/clean/apply", { ids }, panel.update);
        if (j.rc === 0) toast("Reclaimed space: " + label, "ok"); else toast("Cleanup finished with errors", "bad");
        COS.refreshStatus();
        setTimeout(() => load(true), 800);
      }
      function paint() {
        clear(root);
        const totals = data.totals || {};
        const max = Math.max(1, ...data.targets.map((t) => t.bytes));
        const safeIds = data.targets.filter((t) => t.safety === "safe" && t.action !== "list").map((t) => t.id);
        root.appendChild(h("div", { class: "storage-hero" },
          h("div", null,
            h("div", { class: "big accent" }, fmt.bytes(totals.safe || 0)),
            h("div", { class: "muted" }, "safely reclaimable · " + fmt.bytes(totals.review || 0) + " to review · " + fmt.bytes(totals.careful || 0) + " careful"),
            h("div", { class: "muted small" }, (data.deep ? "Deep scan " : "Quick scan ") + fmt.ago(ts))),
          h("div", { class: "row gap" },
            btn("Rescan", () => load(true), "ghost", "refresh"),
            btn("Deep scan", () => load(true, true), "ghost"),
            safeIds.length ? btn("Reclaim all safe", () => reclaim(safeIds, "all safe targets"), "primary") : null)));
        const stack = h("div", { class: "stackbar" });
        const sum = (totals.safe || 0) + (totals.review || 0) + (totals.careful || 0) || 1;
        ["safe", "review", "careful"].forEach((k) => stack.appendChild(h("div", { class: "stack-" + k, style: { width: ((totals[k] || 0) / sum * 100) + "%" }, title: k + ": " + fmt.bytes(totals[k] || 0) })));
        root.appendChild(stack);
        const list = h("div", { class: "targets" });
        data.targets.forEach((t) => {
          const details = h("div", { class: "target-details", hidden: true },
            h("div", { class: "muted" }, t.why),
            h("div", { class: "detail-list" }, (t.details || []).slice(0, 40).map((d) =>
              h("div", { class: "detail" }, h("span", { class: "detail-name" }, d.path || d.name || d.type || d.note || JSON.stringify(d)),
                d.runtime ? h("span", { class: "muted small" }, " " + d.runtime) : null,
                d.last_used ? h("span", { class: "muted small" }, " last used " + d.last_used) : null,
                d.bytes != null ? h("span", { class: "num" }, fmt.bytes(d.bytes)) : null))),
            t.action === "list" ? h("div", { class: "muted small" }, "List only: handle these by hand after a look.")
              : h("div", { class: "row" }, btn("Reclaim " + fmt.bytes(t.bytes), () => reclaim([t.id], t.label), t.safety === "safe" ? "primary small" : "ghost small")));
          list.appendChild(h("div", { class: "target" },
            h("button", { class: "target-head", onclick: () => { details.hidden = !details.hidden; } },
              h("div", { class: "target-label" }, h("span", null, t.label), pill(t.safety)),
              h("div", { class: "target-bar" }, h("div", { class: "target-fill " + t.safety, style: { width: Math.max(2, t.bytes / max * 100) + "%" } })),
              h("div", { class: "target-size" }, fmt.bytes(t.bytes))),
            details));
        });
        root.appendChild(list);
        root.appendChild(h("div", { class: "chips" }, h("button", { class: "chip", onclick: () => COS.ask("Do I need to clean up my Mac?") }, "◆ Ask Claude what to clean")));
      }
      load(false);
    },
  });

  // ------------------------------------------------------------ Updates
  COS.register({
    id: "updates", title: "Updates", icon: "updates", color: "linear-gradient(140deg,#5fc4b8,#23807a)", size: [620, 620],
    keywords: "upgrade brew homebrew npm outdated macos",
    render(w) {
      const root = h("div", { class: "pad" });
      w.body.appendChild(root);
      let ts = null;
      async function load(check, fetch) {
        clear(root).appendChild(h("div", { class: "loading" }, spinner(), check ? (fetch ? "Asking Homebrew and Apple what's new (up to a minute)…" : "Checking…") : "Loading…"));
        try {
          const r = await api("/api/updates" + (check ? "?check=1" + (fetch ? "&fetch=1" : "") : ""));
          ts = r.ts;
          paint(r.data);
        } catch (e) { clear(root).appendChild(h("div", { class: "error-box" }, e.message)); }
      }
      async function apply(source, names, label) {
        const ok = await COS.confirm({ title: label + "?", body: names.length ? names.join(", ") : "Everything outdated in " + source + ".", ok: "Upgrade" });
        if (!ok) return;
        const panel = jobPanel();
        root.prepend(panel.el);
        const j = await job("/api/updates/apply", { source, names }, panel.update);
        toast(j.rc === 0 ? "Updated " + source : "Update finished with errors", j.rc === 0 ? "ok" : "bad");
      }
      function paint(data) {
        clear(root);
        const src = data.sources || {};
        root.appendChild(h("div", { class: "storage-hero" },
          h("div", null, h("div", { class: "big" }, data.total ? data.total + " updates" : "All up to date"),
            h("div", { class: "muted small" }, "checked " + fmt.ago(ts) + (data.fetched ? "" : " · Homebrew metadata not refreshed"))),
          h("div", { class: "row gap" }, btn("Check now", () => load(true, true), "ghost", "refresh"))));
        const mac = (src.macos || {}).items || [];
        root.appendChild(card("macOS", mac.length ? mac.map((it) => h("div", { class: "upd" }, h("span", null, "⚠ " + (it.title || it.label) + " " + (it.version || "")), it.restart ? pill("warn", "restart") : null))
          : h("div", { class: "muted" }, "Up to date."),
          mac.length ? h("div", { class: "row" }, btn("Open Software Update", () => apply("macos", [], "Open Software Update"), "primary small")) : null));
        [["brew", "Homebrew"], ["npm", "npm (global)"], ["mas", "App Store"], ["rustup", "Rust"]].forEach(([key, label]) => {
          const s = src[key];
          if (!s) return;
          const items = s.items || [];
          if (!items.length) { root.appendChild(card(label, h("div", { class: "muted" }, s.error === "couldn't check" ? "Couldn't check (offline?)." : "Up to date."))); return; }
          const checks = {};
          const look = (it) => it.look || (it.major ? "major" : "");
          const lookPill = { major: "major", downgrade: "downgrade", scheme: "new scheme" };
          const rows = items.slice().sort((a, b) => (!!look(b) - !!look(a)) || a.name.localeCompare(b.name)).map((it) => {
            const cb = h("input", { type: "checkbox" });
            cb.checked = !look(it) && !it.pinned;
            checks[it.name] = cb;
            return h("label", { class: "upd" }, cb, h("span", { class: "upd-name" }, it.name), h("span", { class: "muted mono" }, it.installed + " → " + it.latest),
              look(it) ? pill("warn", lookPill[look(it)] || look(it)) : null, it.pinned ? pill("note", "pinned") : null);
          });
          const selected = () => Object.keys(checks).filter((n) => checks[n].checked);
          root.appendChild(card(label + " · " + items.length,
            h("div", { class: "upd-list" }, rows),
            h("div", { class: "row gap" },
              key === "rustup" ? btn("Update Rust", () => apply("rustup", [], "Update Rust"), "primary small")
                : btn("Upgrade selected", () => { const n = selected(); if (n.length) apply(key, n, "Upgrade " + n.length + " package" + (n.length > 1 ? "s" : "")); }, "primary small"),
              h("span", { class: "muted small" }, "Majors and downgrades are unticked: they can break things."))));
        });
        if ((data.missing_tools || []).includes("mas")) root.appendChild(h("div", { class: "muted small pad-t" }, "Tip: `brew install mas` lets Claude OS see App Store updates too."));
      }
      load(false);
    },
  });

  // ------------------------------------------------------------ Music
  COS.register({
    id: "music", title: "Music", icon: "music", color: "linear-gradient(140deg,#f46b8a,#b3264f)", size: [520, 680],
    keywords: "song play apple music playlist",
    render(w) {
      const art = h("div", { class: "np-art" });
      const title = h("div", { class: "np-title" }, "Nothing playing");
      const artist = h("div", { class: "np-artist muted" });
      const prog = h("div", { class: "np-progress" }, h("div", { class: "np-fill" }));
      const times = h("div", { class: "np-times muted small" });
      const playBtn = h("button", { class: "np-btn big", title: "Play/Pause", onclick: () => control("toggle") }, icon("play", 22));
      const vol = h("input", { type: "range", min: 1, max: 100, class: "np-vol", title: "Volume" });
      vol.addEventListener("change", () => control("volume", { level: +vol.value }));
      const np = h("div", { class: "np" }, art, h("div", { class: "np-meta" }, title, artist, prog, times,
        h("div", { class: "np-controls" },
          h("button", { class: "np-btn", title: "Previous", onclick: () => control("prev") }, icon("prev", 18)),
          playBtn,
          h("button", { class: "np-btn", title: "Next", onclick: () => control("next") }, icon("next", 18)),
          h("button", { class: "np-btn", title: "Radio: keep going with similar music", onclick: () => play({ radio: true }, "a radio from this song") }, icon("radio", 17)),
          h("button", { class: "np-btn", title: "Love", onclick: () => control("like").then(() => toast("♥ Saved to your favourites", "ok")) }, icon("heart", 16)),
          vol)));
      const search = h("input", { class: "search", placeholder: "Search your library and Apple Music…" });
      const results = h("div", { class: "results" });
      const moods = h("div", { class: "chips" }, ["Something chill", "Deep focus", "Energy boost", "Rainy evening", "Surprise me"].map((mood) =>
        h("button", { class: "chip", onclick: () => COS.ask("Play " + mood.toLowerCase() + " on Apple Music, picked for my taste.") }, "◆ " + mood)));
      const playlists = h("div", { class: "playlists" });
      w.body.appendChild(h("div", { class: "pad music" }, np, h("div", { class: "section-title" }, "Let Claude DJ"), moods,
        h("div", { class: "search-wrap" }, icon("search", 15), search), results, h("div", { class: "section-title" }, "Playlists"), playlists));
      let now = null, tick = null, artUrl = null;

      function paint(n) {
        now = n;
        const playing = n.running && n.state === "playing";
        clear(playBtn).appendChild(icon(playing ? "pause" : "play", 22));
        if (!n.running) { title.textContent = "Music isn't open"; artist.textContent = "Search below, or let Claude pick."; times.textContent = ""; }
        else if (!n.track) { title.textContent = "Nothing loaded"; artist.textContent = ""; times.textContent = ""; }
        else {
          title.textContent = n.track;
          artist.textContent = [n.artist, n.album].filter(Boolean).join(" — ") + (n.playlist ? " · from " + n.playlist : n.station ? " · radio" : "");
          if (document.activeElement !== vol) vol.value = Math.max(1, n.volume || 1);
        }
        if (n.artwork !== artUrl) {
          artUrl = n.artwork;
          clear(art);
          if (artUrl) art.appendChild(h("img", { src: artUrl, alt: "" })); else art.appendChild(h("div", { class: "np-art-empty" }, "♫"));
        }
        progress();
      }
      function progress() {
        if (!now || !now.duration) { prog.firstChild.style.width = "0%"; return; }
        prog.firstChild.style.width = Math.min(100, now.position / now.duration * 100) + "%";
        times.textContent = fmt.duration(now.position) + " / " + fmt.duration(now.duration);
      }
      async function refresh() { try { paint(await api("/api/music/now")); } catch (e) {} }
      async function control(cmd, extra) {
        try { paint(await api("/api/music/control", { body: Object.assign({ cmd }, extra || {}) })); COS.refreshMusic(); } catch (e) { toast(e.message, "bad"); }
      }
      async function play(body, label) {
        toast("Starting " + label + "…");
        try {
          const r = await api("/api/music/play", { body });
          if (r.ok) toast("▶ " + ((r.now && r.now.track) || label), "ok"); else toast(r.error || "Couldn't play that", "bad");
          refresh(); COS.refreshMusic();
        } catch (e) { toast(e.message, "bad"); }
      }
      let searchTimer = null;
      search.addEventListener("input", () => {
        clearTimeout(searchTimer);
        const q = search.value.trim();
        if (!q) { clear(results); return; }
        searchTimer = setTimeout(async () => {
          clear(results).appendChild(h("div", { class: "loading" }, spinner(), "Searching…"));
          try {
            const r = await api("/api/music/search?q=" + encodeURIComponent(q));
            clear(results);
            if (r.library.length) {
              results.appendChild(h("div", { class: "section-title" }, "In your library"));
              r.library.forEach((t) => results.appendChild(h("button", { class: "song", onclick: () => play({ id: t.id, name: t.name }, t.name) },
                h("div", { class: "song-art lib" }, "♫"), h("div", { class: "song-meta" }, h("div", null, t.name), h("div", { class: "muted small" }, t.artist + " · " + t.album)), icon("play", 14))));
            }
            if (r.catalog.length) {
              results.appendChild(h("div", { class: "section-title" }, "Apple Music"));
              r.catalog.forEach((t) => results.appendChild(h("button", { class: "song", onclick: () => play({ url: t.url, name: t.name, artist: t.artist, album: t.album, track_number: t.track_number }, t.name) },
                h("div", { class: "song-art" }, t.artwork ? h("img", { src: t.artwork.replace("600x600bb", "120x120bb"), alt: "" }) : "♫"),
                h("div", { class: "song-meta" }, h("div", null, t.name), h("div", { class: "muted small" }, t.artist + " · " + t.album + (t.year ? " · " + t.year : ""))), icon("play", 14))));
            }
            if (!r.library.length && !r.catalog.length) results.appendChild(h("div", { class: "muted pad-t" }, "Nothing found."));
          } catch (e) { clear(results).appendChild(h("div", { class: "error-box" }, e.message)); }
        }, 350);
      });
      (async () => {
        try {
          const lists = await api("/api/music/playlists");
          clear(playlists);
          lists.filter((p) => p.tracks > 0).slice(0, 40).forEach((p) => playlists.appendChild(
            h("button", { class: "playlist", onclick: () => play({ playlist: p.name, shuffle: true }, p.name) }, h("span", null, p.name), h("span", { class: "muted small" }, p.tracks))));
        } catch (e) { playlists.appendChild(h("div", { class: "muted" }, "Playlists unavailable: " + e.message)); }
      })();
      refresh();
      const t1 = setInterval(refresh, 4000);
      tick = setInterval(() => { if (now && now.state === "playing" && now.duration) { now.position += 1; progress(); } }, 1000);
      w.cleanup.push(() => { clearInterval(t1); clearInterval(tick); });
    },
  });

  // ------------------------------------------------------------ Feeds
  COS.register({
    id: "feeds", title: "Feeds", icon: "feeds", color: "linear-gradient(140deg,#f2995a,#c25a1d)", size: [820, 620],
    keywords: "rss news read brief",
    onReopen(w, arg) { if (arg === "brief" && w.showBrief) w.showBrief(); },
    render(w, arg) {
      let category = "", showAll = false, items = [];
      const side = h("div", { class: "feeds-side" });
      const list = h("div", { class: "feeds-list" });
      w.actions.appendChild(btn("Brief me", () => COS.ask("/brief"), "ghost small", "claude"));
      w.actions.appendChild(btn("", () => load(true), "ghost small icon-only", "refresh"));
      w.body.appendChild(h("div", { class: "feeds" }, side, list));
      async function load(refresh) {
        clear(list).appendChild(h("div", { class: "loading" }, spinner(), refresh ? "Fetching feeds…" : "Loading…"));
        try {
          const r = await api("/api/feeds?" + new URLSearchParams({ category, all: showAll ? "1" : "", refresh: refresh ? "1" : "" }));
          items = r.items;
          paintSide(r.categories);
          paint();
        } catch (e) { clear(list).appendChild(h("div", { class: "error-box" }, e.message)); }
      }
      function paintSide(cats) {
        clear(side);
        [["", "All"]].concat(cats.map((c) => [c, c === "ai" ? "AI" : c[0].toUpperCase() + c.slice(1)])).forEach(([c, label]) =>
          side.appendChild(h("button", { class: "side-item" + (c === category ? " active" : ""), onclick: () => { category = c; load(false); } }, label)));
        side.appendChild(h("div", { class: "side-sep" }));
        side.appendChild(h("button", { class: "side-item" + (showAll ? " active" : ""), onclick: () => { showAll = !showAll; load(false); } }, showAll ? "Showing read" : "Unread only"));
        side.appendChild(h("button", { class: "side-item", onclick: async () => { await api("/api/feeds/read", { body: { all: true } }); toast("All caught up", "ok"); load(false); } }, "Mark all read"));
        side.appendChild(h("button", { class: "side-item", onclick: () => showBrief() }, "Latest brief"));
      }
      function paint() {
        clear(list);
        if (!items.length) { list.appendChild(empty("Nothing unread.", "You're all caught up.")); return; }
        items.forEach((it) => {
          const node = h("a", { class: "feed-item", href: /^https?:\/\//i.test(it.link || "") ? it.link : null, target: "_blank", rel: "noopener noreferrer" },
            h("div", { class: "feed-meta muted small" }, it.feed + " · " + (it.ts ? fmt.ago(it.ts) : "")), h("div", { class: "feed-title" }, it.title),
            it.summary ? h("div", { class: "feed-summary muted" }, it.summary) : null);
          node.addEventListener("click", () => {
            api("/api/feeds/read", { body: { keys: [it.key] } }).catch(() => {});
            setTimeout(() => node.classList.add("read"), 300);
          });
          list.appendChild(node);
        });
      }
      async function showBrief() {
        const b = await api("/api/brief");
        side.querySelectorAll(".side-item").forEach((x) => x.classList.toggle("active", x.textContent === "Latest brief"));
        clear(list);
        if (!b.text) { list.appendChild(empty("No brief yet.", "Click “Brief me” and Claude will write one.")); return; }
        list.appendChild(h("div", { class: "md brief pad", html: MD.render(b.text) }));
      }
      w.showBrief = showBrief;
      if (arg === "brief") load(false).then(showBrief); else load(false);
    },
  });

  // ------------------------------------------------------------ Evolution
  const EVOLUTION_TABS = ["Friction", "Branches", "Board", "Roadmap"];
  COS.register({
    id: "evolution", title: "Evolution", icon: "evolution", color: "linear-gradient(140deg,#8fcf7c,#3f8a3a)", size: [720, 640],
    keywords: "evolve board friction roadmap improve lab", dockGap: true,
    onReopen(w, arg) { if (w.showTab && EVOLUTION_TABS.includes(arg)) w.showTab(arg); },
    render(w, arg) {
      w.showTab = tabs(w, EVOLUTION_TABS, {
        Friction(pane) {
          const input = h("input", { class: "search", placeholder: "What got in your way? (Claude OS will work on it)" });
          const add = async () => {
            const text = input.value.trim();
            if (!text) return;
            await api("/api/friction", { body: { text } });
            input.value = "";
            draw();
          };
          input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
          const listEl = h("div", { class: "list" });
          pane.appendChild(h("div", { class: "pad" }, h("div", { class: "row gap" }, input, btn("Log it", add, "primary")), listEl));
          async function draw() {
            await loading(listEl, async () => {
              const items = (await api("/api/friction")).slice().reverse();
              clear(listEl);
              if (!items.length) listEl.appendChild(empty("No friction logged.", "When something annoys you, write it here."));
              items.forEach((f) => listEl.appendChild(h("div", { class: "list-row" + (f.status === "closed" ? " dim" : "") },
                h("span", { class: "muted mono" }, "#" + f.id), f.area ? pill("note", f.area) : null, h("span", { class: "grow" }, f.text),
                f.status === "open" ? btn("Close", async () => { await api("/api/friction/close", { body: { id: f.id, note: "closed in the app" } }); draw(); }, "ghost small") : pill("ok", "closed"))));
            });
          }
          draw();
        },
        Branches(pane) {
          const root = h("div", { class: "pad" });
          pane.appendChild(root);
          async function draw() {
            await loading(root, async () => {
              const brs = await api("/api/evolve");
              clear(root);
              if (!brs.length) {
                root.appendChild(empty("No evolve branches waiting.", "The nightly evolve daemon proposes one small improvement at a time. Turn it on in Settings, or ask Claude to /evolve now."));
                root.appendChild(h("div", { class: "chips center" }, h("button", { class: "chip", onclick: () => COS.ask("/evolve") }, "◆ Evolve something now")));
                return;
              }
              brs.forEach((b) => {
                const diff = h("pre", { class: "diff", hidden: true });
                root.appendChild(card(b.branch,
                  h("div", { class: "list" }, b.commits.map((c) => h("div", { class: "mono small" }, c))),
                  h("div", { class: "row gap" },
                    btn("Review", async () => {
                      if (!diff.hidden) { diff.hidden = true; return; }
                      const d = await api("/api/evolve/diff?branch=" + encodeURIComponent(b.branch));
                      paintDiff(diff, d.log + "\n" + d.diff);
                      diff.hidden = false;
                    }, "ghost small"),
                    btn("Merge", async () => {
                      if (!(await COS.confirm({ title: "Merge " + b.branch + "?", body: "Runs the Guardian and the tests again, then fast-forwards main. Nothing is pushed.", ok: "Merge" }))) return;
                      const panel = jobPanel(); root.prepend(panel.el);
                      await job("/api/evolve/merge", { branch: b.branch }, panel.update); draw();
                    }, "primary small"),
                    btn("Discard", async () => {
                      if (!(await COS.confirm({ title: "Discard " + b.branch + "?", ok: "Discard", danger: true }))) return;
                      await job("/api/evolve/discard", { branch: b.branch }); draw();
                    }, "ghost small")),
                  diff));
              });
            });
          }
          draw();
        },
        Board(pane) {
          const root = h("div", { class: "pad" });
          pane.appendChild(root);
          const proposal = h("input", { class: "search", placeholder: "Put a proposal to the board…" });
          const convene = () => { const p = proposal.value.trim(); if (p) COS.ask("/board " + p); };
          proposal.addEventListener("keydown", (e) => { if (e.key === "Enter") convene(); });
          const SEATS = [["architect", "Architect", "fit & simplicity"], ["guardian", "Guardian", "safety · veto"],
            ["steward", "Steward", "your interests"], ["skeptic", "Skeptic", "the case against"]];
          const NOW = { Agent: "calling the seats", Read: "reading", Grep: "searching", Glob: "searching", Write: "writing", Edit: "writing" };
          const seatsBox = h("div"), sessionBox = h("div");
          let timer = null;
          const stop = () => { clearTimeout(timer); timer = null; };
          w.cleanup.push(stop);
          // While a meeting runs, each seat shows where it is; the live data is labels only.
          function paintLive(live) {
            const agents = (live && live.agents) || [];
            clear(seatsBox).appendChild(h("div", { class: "board-seats" + (live ? " in-session" : "") }, SEATS.map(([id, name, role]) => {
              const a = agents.filter((x) => x.type === id).pop();
              let state = role, cls = "";
              if (live) {
                if (!a) { state = "waiting"; cls = " waiting"; }
                else if (a.vote) { state = "voted " + a.vote; cls = " voted " + a.vote; }
                else if (a.state === "working") { state = "deliberating…"; cls = " working"; }
                else { state = "done"; cls = " voted"; }
              }
              return h("div", { class: "seat" + cls }, h("div", { class: "seat-mark" }, "◆"), h("div", { class: "seat-name" }, name), h("div", { class: "muted small" }, state));
            })));
            clear(sessionBox);
            if (live) sessionBox.appendChild(h("div", { class: "session" }, h("span", { class: "live-dot" }),
              h("span", null, "In session · " + live.minutes + " min"), live.now ? h("span", { class: "muted" }, " · " + (NOW[live.now] || "now: " + live.now)) : null,
              h("div", { class: "muted small" }, "The minutes appear here when the meeting ends.")));
          }
          async function poll() {
            if (!root.isConnected) return stop();
            if (!document.hidden) {
              try {
                const b = await api("/api/board");
                if (!b.live) return draw();
                paintLive(b.live);
              } catch (e) { /* try again on the next tick */ }
            }
            timer = setTimeout(poll, 5000);
          }
          async function draw() {
            stop();
            await loading(root, async () => {
              const b = await api("/api/board");
              clear(root);
              paintLive(b.live);
              root.appendChild(seatsBox);
              root.appendChild(sessionBox);
              root.appendChild(h("div", { class: "row gap" }, proposal, btn("Convene", convene, "primary")));
              root.appendChild(h("div", { class: "section-title" }, "Decisions"));
              b.decisions.forEach((d) => root.appendChild(h("button", { class: "list-row link", onclick: () => doc(d.name) }, d.title)));
              root.appendChild(h("div", { class: "section-title" }, "Latest minutes"));
              if (!b.latest) root.appendChild(h("div", { class: "muted" }, "The board hasn't met yet. Weekly meetings run on Sundays once the board daemon is on."));
              else {
                root.appendChild(h("div", { class: "md", html: MD.render(b.latest.text) }));
                if (b.latest.details) root.appendChild(h("details", { class: "run-details" }, h("summary", null, "How the meeting went"),
                  h("div", { class: "md muted", html: MD.render(b.latest.details) })));
              }
              if (b.live) timer = setTimeout(poll, 5000);
            });
          }
          draw();
          async function doc(name) {
            const d = await api("/api/doc?name=" + encodeURIComponent(name));
            clear(root).appendChild(h("div", null, btn("← Back", () => { clear(pane); w.body.querySelector('.tab[data-name="Board"]').click(); }, "ghost small"), h("div", { class: "md", html: MD.render(d.text) })));
          }
        },
        Roadmap(pane) {
          const root = h("div", { class: "pad md" });
          pane.appendChild(root);
          loading(root, async () => { const d = await api("/api/doc?name=roadmap"); root.innerHTML = MD.render(d.text); });
        },
      }, EVOLUTION_TABS.includes(arg) ? arg : undefined).show;
      function paintDiff(el, text) {
        clear(el);
        text.split("\n").slice(0, 3000).forEach((line) => el.appendChild(h("div", { class: line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "del" : line.startsWith("@@") ? "hunk" : "" }, line || " ")));
      }
    },
  });

  // ------------------------------------------------------------ Journal
  COS.register({
    id: "journal", title: "Journal", icon: "journal", color: "linear-gradient(140deg,#7f9fe0,#3d5ba8)", size: [600, 600],
    keywords: "log history activity",
    render(w) {
      let kind = "";
      const filters = h("div", { class: "chips" });
      const listEl = h("div", { class: "timeline" });
      w.body.appendChild(h("div", { class: "pad" }, filters, listEl));
      const KINDS = ["", "action", "approval", "ask", "music", "friction", "memory", "daemon", "evolve"];
      function paintFilters() {
        clear(filters);
        KINDS.forEach((k) => filters.appendChild(h("button", { class: "chip" + (k === kind ? " active" : ""), onclick: () => { kind = k; paintFilters(); draw(); } }, k || "everything")));
      }
      async function draw() {
        await loading(listEl, async () => {
          const rows = (await api("/api/log?days=30" + (kind ? "&kind=" + kind : ""))).slice().reverse();
          clear(listEl);
          if (!rows.length) { listEl.appendChild(empty("Nothing here yet.")); return; }
          let day = "";
          rows.forEach((e) => {
            const d = e.ts.slice(0, 10);
            if (d !== day) { day = d; listEl.appendChild(h("div", { class: "tl-day" }, new Date(d + "T12:00:00").toLocaleDateString(navigator.language, { weekday: "long", day: "numeric", month: "long" }))); }
            listEl.appendChild(h("div", { class: "tl-row" }, h("span", { class: "tl-time muted mono" }, e.ts.slice(11, 16)), pill("kind-" + e.kind, e.kind), h("span", { class: "grow" }, e.msg)));
          });
        });
      }
      paintFilters();
      draw();
    },
  });

  // ------------------------------------------------------------ Memory
  COS.register({
    id: "memory", title: "Memory", icon: "memory", color: "linear-gradient(140deg,#b18cf0,#6a43b8)", size: [520, 520],
    keywords: "remember preferences facts",
    render(w) {
      const input = h("input", { class: "search", placeholder: "Teach Claude something about you…" });
      const listEl = h("div", { class: "list" });
      w.body.appendChild(h("div", { class: "pad" },
        h("div", { class: "muted small" }, "Claude reads these at the start of every session. They live only on this Mac, in ~/.claude-os."),
        h("div", { class: "row gap pad-t" }, input, btn("Remember", add, "primary")), listEl));
      async function add() {
        const fact = input.value.trim();
        if (!fact) return;
        paint(await api("/api/memory/remember", { body: { fact } }));
        input.value = "";
      }
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
      function paint(m) {
        clear(listEl);
        if (!m.facts.length) { listEl.appendChild(empty("Nothing remembered yet.", "Tell Claude what music you like, how tidy you want things, what you care about.")); return; }
        m.facts.forEach((f) => {
          const text = f.replace(/\s*_\(\d{4}-\d{2}-\d{2}\)_\s*$/, "");
          listEl.appendChild(h("div", { class: "list-row" }, h("span", { class: "grow" }, text),
            h("button", { class: "icon-btn", title: "Forget", onclick: async () => paint(await api("/api/memory/forget", { body: { pattern: text } })) }, icon("x", 14))));
        });
      }
      loading(listEl, async () => paint(await api("/api/memory")));
    },
  });

  // ------------------------------------------------------------ Settings
  COS.register({
    id: "settings", title: "Settings", icon: "settings", color: "linear-gradient(140deg,#9a948d,#5b5650)", size: [600, 560],
    keywords: "daemons background about preferences",
    render(w) {
      const root = h("div", { class: "pad" });
      w.body.appendChild(root);
      const nativeBridge = () => window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.cos;

      function permissions(s) {
        const box = h("div");
        // Apple Music in Claude OS (decision 0003, amended): MusicKit, "Media & Apple Music".
        const m = s.music;
        const musicToggle = h("input", { type: "checkbox", class: "switch" });
        musicToggle.checked = m.apple_music;
        musicToggle.addEventListener("change", async () => {
          if (musicToggle.checked) toast("macOS may ask to let Claude OS use Apple Music", "accent");
          const r = await api("/api/settings/music", { body: { apple_music: musicToggle.checked } });
          if (r.error) toast(r.error, "bad");
          if (!musicToggle.checked) toast("Off. To fully revoke it, untick Claude OS in the Media & Apple Music list that just opened.");
          draw();
        });
        const musicState = !m.apple_music ? "Off: catalog songs open in the Music app for you to press play."
          : m.error ? m.error
          : m.authorization === "authorized" ? "On ✓ Any Apple Music song plays right here in Claude OS."
          : "Waiting for macOS: allow Claude OS under Privacy & Security › Media & Apple Music.";
        box.appendChild(h("div", { class: "daemon" },
          h("div", { class: "grow" },
            h("div", { class: "daemon-name" }, "Apple Music in Claude OS", pill("note", "permission")),
            h("div", { class: "small" }, "Play any song from Apple Music, not just your library. Claude OS becomes a small player using your subscription. macOS calls this Media & Apple Music. Turn off anytime."),
            h("div", { class: "muted small" }, musicState)),
          musicToggle));
        // Notifications from Claude OS itself (decision 0004): permission only on this click.
        const n = s.notify || {};
        const notifyToggle = h("input", { type: "checkbox", class: "switch" });
        notifyToggle.checked = n.native;
        notifyToggle.addEventListener("change", async () => {
          if (notifyToggle.checked) toast("macOS will ask to let Claude OS send notifications", "accent");
          await api("/api/settings/notify", { body: { native: notifyToggle.checked } });
          draw();
        });
        box.appendChild(h("div", { class: "daemon" },
          h("div", { class: "grow" },
            h("div", { class: "daemon-name" }, "Notifications from Claude OS", n.native && n.authorization === "authorized" ? pill("ok", "on") : pill("note", "off")),
            h("div", { class: "small" }, "Alerts and your morning brief arrive with Claude OS's own name and icon, and clicking one opens the desktop. Otherwise they come from Script Editor."),
            h("div", { class: "muted small" }, !n.native ? "Off."
              : n.authorization === "authorized" ? "On ✓"
              : n.authorization === "denied" ? "macOS says no: allow Claude OS under System Settings › Notifications."
              : "Waiting for macOS to ask you.")),
          notifyToggle));

        // Night shift (decision 0006): Claude pushes its own night/* branches while you're away.
        const nightToggle = h("input", { type: "checkbox", class: "switch" });
        nightToggle.checked = !!s.night_shift;
        nightToggle.addEventListener("change", async () => {
          // Turning it on is confirmed in Claude OS.app's own dialog, which page code can't click.
          if (nightToggle.checked) toast("Confirm in the dialog that just opened…");
          const r = await api("/api/settings/night", { body: { on: nightToggle.checked } });
          if (nightToggle.checked && !r.night_shift) toast(r.error || "Night shift stays off.", r.error ? "bad" : "");
          draw();
        });
        box.appendChild(h("div", { class: "daemon" },
          h("div", { class: "grow" },
            h("div", { class: "daemon-name" }, "Night shift", s.night_shift ? pill("ok", "on") : pill("note", "off")),
            h("div", { class: "small" }, "Let Claude push its own night/… branches, open pull requests and merge the ones that pass while you're away. Never a force push; every commit is checked for private data, and pull requests that change Claude OS's own safety checks wait for your merge."),
            h("div", { class: "muted small" }, s.night_shift ? "On: each push and merge is in your journal and tomorrow's brief." : "Off: every push and merge asks you first.")),
          nightToggle));

        // Keep Claude OS up to date (decision 0011): what's merged on GitHub comes to this Mac by itself.
        const upToggle = h("input", { type: "checkbox", class: "switch" });
        upToggle.checked = !!s.catch_up;
        upToggle.addEventListener("change", async () => {
          // Like Night shift, turning it on is confirmed in Claude OS.app's own dialog.
          if (upToggle.checked) toast("Confirm in the dialog that just opened…");
          const r = await api("/api/settings/catch-up", { body: { on: upToggle.checked } });
          if (upToggle.checked && !r.catch_up) toast(r.error || "It stays off.", r.error ? "bad" : "");
          draw();
        });
        box.appendChild(h("div", { class: "daemon" },
          h("div", { class: "grow" },
            h("div", { class: "daemon-name" }, "Keep Claude OS up to date", s.catch_up ? pill("ok", "on") : pill("note", "off")),
            h("div", { class: "small" }, "When you merge a pull request on GitHub, Claude OS brings it to this Mac by itself: when the app starts, when a terminal session starts, and while the app is closed. Only a clean main, only forward, only over GitHub's own merges."),
            h("div", { class: "muted small" }, s.catch_up ? "On: while the app is open, Update in the menu bar restarts it onto what you merged." : "Off: the boot banner says what's merged, and `cos update apply claude-os --yes` brings it in.")),
          upToggle));

        // Calendar & Reminders (decision 0002): read-only, only after the human clicks Connect.
        const calOn = s.calendar === "connected";
        box.appendChild(h("div", { class: "daemon" },
          h("div", { class: "grow" },
            h("div", { class: "daemon-name" }, "Calendar & Reminders", calOn ? pill("ok", "connected") : pill("note", "off")),
            h("div", { class: "small" }, "Show today's events and due reminders on Today and in your brief. Claude OS only reads them; it never changes your calendar."),
            h("div", { class: "muted small" }, calOn ? "Connected" + (s.calendars != null ? " · " + s.calendars + " calendar" + (s.calendars === 1 ? "" : "s") : "") + ". To disconnect, untick Claude OS under Privacy & Security › Calendars and Reminders."
              : s.calendar === "denied" ? "macOS says no: allow Claude OS under Privacy & Security › Calendars."
              : "Off until you connect it.")),
          calOn ? null : btn("Connect", async (e) => {
            e.target.disabled = true;
            toast("macOS will ask to let Claude OS see your calendar and reminders", "accent");
            try { const v = await api("/api/agenda/connect", { body: {} }); toast(v.connected ? "Calendar connected" : "Calendar not connected", v.connected ? "ok" : "bad"); }
            catch (err) { toast(err.message, "bad"); }
            draw(); COS.refreshAgenda && COS.refreshAgenda();
          }, "primary small")));

        // Weather: a city, or this Mac's location (rounded to ~1 km, stays on this Mac).
        const w = s.weather;
        const city = h("input", { class: "search", placeholder: "City for weather, e.g. Lisbon" });
        const setCity = async () => {
          const query = city.value.trim();
          if (!query) return;
          try { const r = await api("/api/weather/city", { body: { query } }); toast("Weather for " + r.name, "ok"); draw(); COS.refreshWeather && COS.refreshWeather(); }
          catch (e) { toast(e.message, "bad"); }
        };
        city.addEventListener("keydown", (e) => { if (e.key === "Enter") setCity(); });
        const locate = async () => {
          try {
            const r = await nativeBridge().postMessage({ type: "locate" });
            if (r.error) { toast(r.error, "bad"); return; }
            await api("/api/weather/coords", { body: { lat: r.lat, lon: r.lon } });
            toast("Weather follows your location", "ok");
            draw();
            COS.refreshWeather && COS.refreshWeather();
          } catch (e) { toast("Location isn't available: " + e.message, "bad"); }
        };
        box.appendChild(h("div", { class: "daemon" },
          h("div", { class: "grow" },
            h("div", { class: "daemon-name" }, "Weather", w.name ? pill("ok", w.source === "device" ? "your location" : "city") : pill("note", "off")),
            h("div", { class: "small" }, "Use my location for weather on Today and in your brief. Or type a city."),
            h("div", { class: "muted small" }, w.name ? "Showing weather for " + w.name + ". The place stays on this Mac." : "Off until you choose a place."),
            h("div", { class: "row gap" }, city, btn("Set", setCity, "ghost small"),
              nativeBridge() ? btn("Use my location", locate, "primary small") : null,
              w.name ? btn("Forget", async () => { await api("/api/weather/clear", { body: {} }); draw(); COS.refreshWeather && COS.refreshWeather(); }, "ghost small") : null))));
        return box;
      }

      async function draw() {
        await loading(root, async () => {
          const [ds, settings] = await Promise.all([api("/api/daemons"), api("/api/settings")]);
          clear(root);
          root.appendChild(h("div", { class: "section-title" }, "Permissions"));
          root.appendChild(permissions(settings));
          root.appendChild(h("div", { class: "section-title" }, "Background jobs"));
          ds.forEach((d) => {
            const toggle = h("input", { type: "checkbox", class: "switch" });
            toggle.checked = d.loaded;
            toggle.addEventListener("change", async () => {
              const action = toggle.checked ? "install" : "uninstall";
              if (toggle.checked && d.llm && !(await COS.confirm({ title: "Turn on " + d.name + "?", body: "This runs Claude on a schedule and uses your Claude plan. It can't change your Mac or push anything.", ok: "Turn on" }))) { toggle.checked = false; return; }
              const j = await job("/api/daemons/" + action, { name: d.name });
              toast(d.name + (j.rc === 0 ? (toggle.checked ? " is on" : " is off") : ": " + j.output.slice(-200)), j.rc === 0 ? "ok" : "bad");
              draw();
            });
            root.appendChild(h("div", { class: "daemon" },
              h("div", { class: "grow" }, h("div", { class: "daemon-name" }, d.name, d.llm ? pill("note", "uses Claude") : pill("ok", "free")),
                h("div", { class: "muted small" }, d.description), h("div", { class: "muted small" }, d.schedule + " · " + (d.running_minutes != null ? "running now · " + d.running_minutes + " min"
                  : "last run " + (d.last_run ? d.last_run.slice(0, 16).replace("T", " ") : "never")))),
              toggle));
          });
          root.appendChild(h("div", { class: "section-title" }, "About"));
          root.appendChild(h("div", { class: "about" },
            h("div", { class: "about-mark" }, "◆"),
            h("div", null, h("div", { class: "about-name" }, "Claude OS"), h("div", { class: "muted small" }, "An operating layer for your Mac, designed by Claude."),
              h("div", { class: "row gap pad-t" },
                h("a", { class: "btn ghost small", href: "https://github.com/markusskov/Claude-OS", target: "_blank", rel: "noopener" }, "Source on GitHub"),
                btn("Lessons learned", async () => { const d = await api("/api/doc?name=lessons"); clear(root).appendChild(h("div", null, btn("← Back", draw, "ghost small"), h("div", { class: "md", html: MD.render(d.text) }))); }, "ghost small")))));
          root.appendChild(h("div", { class: "muted small pad-t" }, "Shortcuts: ⌘K command palette · ⌃⌥Space summons Claude OS from anywhere."));
        });
      }
      draw();
    },
  });

  // ------------------------------------------------------------ desktop "Today"
  COS.onBoot = function () {
    const today = document.getElementById("today");
    const hour = new Date().getHours();
    const greet = hour < 5 ? "Up late." : hour < 12 ? "Good morning." : hour < 18 ? "Good afternoon." : "Good evening.";
    const line = h("div", { class: "today-line" });
    const wx = h("button", { class: "today-weather", onclick: () => COS.open("settings") });
    COS.refreshWeather = async () => {
      try {
        const f = await api("/api/weather");
        clear(wx);
        if (!f.configured) { wx.appendChild(h("span", { class: "muted" }, "＋ Add weather")); return; }
        if (f.error || !f.now) { wx.appendChild(h("span", { class: "muted" }, "Weather unavailable")); return; }
        const t = f.today || {};
        wx.appendChild(h("span", { class: "wx-symbol" }, f.now.symbol));
        wx.appendChild(h("span", { class: "wx-temp" }, Math.round(f.now.temp) + "°"));
        wx.appendChild(h("span", { class: "muted" }, f.now.summary + (t.max != null ? " · " + Math.round(t.max) + "° / " + Math.round(t.min) + "°" : "") +
          (t.precip_pct ? " · " + t.precip_pct + "% rain" : "")));
      } catch (e) { clear(wx); }
    };
    COS.refreshWeather();
    setInterval(COS.refreshWeather, 30 * 60 * 1000);
    const agenda = h("div", { class: "today-agenda" });
    COS.refreshAgenda = async () => {
      try {
        const v = await api("/api/agenda");
        clear(agenda);
        if (!v.connected) return;
        const upcoming = v.today.filter((e) => !e.past);
        upcoming.slice(0, 4).forEach((e) => agenda.appendChild(h("div", { class: "ag-row" },
          h("span", { class: "ag-when" }, e.when), h("span", { class: "ag-title" }, e.title))));
        if (!upcoming.length) agenda.appendChild(h("div", { class: "ag-row muted" }, v.today.length ? "Nothing more today." : "Nothing on the calendar today."));
        if (v.reminders.length) agenda.appendChild(h("div", { class: "ag-row" }, h("span", { class: "ag-when" }, "☐"),
          h("span", { class: "ag-title" }, v.reminders.length === 1 ? v.reminders[0].title : v.reminders.length + " reminders due")));
      } catch (e) { clear(agenda); }
    };
    COS.refreshAgenda();
    setInterval(COS.refreshAgenda, 5 * 60 * 1000);
    // The morning brief, once the daemon has written it: first thing on Today, until evening.
    const briefChip = h("button", { class: "chip glass brief-chip", hidden: true, onclick: () => COS.open("feeds", "brief") }, "☕ Today's brief");
    const refreshBrief = async () => {
      try {
        const b = await api("/api/brief");
        briefChip.hidden = !(b.text && Date.now() / 1000 - b.ts < 18 * 3600);
      } catch (e) { briefChip.hidden = true; }
    };
    refreshBrief();
    setInterval(refreshBrief, 15 * 60 * 1000);
    clear(today).appendChild(h("div", null,
      h("div", { class: "today-greet" }, greet),
      h("div", { class: "today-date" }, new Date().toLocaleDateString(navigator.language, { weekday: "long", day: "numeric", month: "long" })),
      wx,
      agenda,
      line,
      h("div", { class: "today-chips" }, [briefChip].concat(["Do I need to clean up my Mac?", "Play something chill", "Catch me up", "What's outdated?"]
        .map((s) => h("button", { class: "chip glass", onclick: () => COS.ask(s) }, s))))));
    COS.on("status", (s) => {
      clear(line);
      line.appendChild(h("span", null, fmt.bytes(s.disk.free) + " free"));
      s.signals.forEach((x) => line.appendChild(h("span", { class: x.level === "warn" ? "warn-text" : "" }, x.msg)));
      if (!s.signals.length) line.appendChild(h("span", null, "all quiet"));
    });
  };
})();
