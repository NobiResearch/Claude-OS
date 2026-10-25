// Claude OS desktop: API client, window manager, dock, menu bar, palette, boot.
"use strict";

(function () {
  // ------------------------------------------------------------ token & api
  const TOKEN_KEY = "cos-token";
  let token = "";
  const m = location.hash.match(/token=([\w-]+)/);
  if (m) {
    token = m[1];
    try { sessionStorage.setItem(TOKEN_KEY, token); } catch (e) {}
    history.replaceState(null, "", location.pathname);
  } else {
    try { token = sessionStorage.getItem(TOKEN_KEY) || ""; } catch (e) {}
  }

  async function api(path, opts) {
    opts = opts || {};
    const res = await fetch(path, {
      method: opts.body ? "POST" : (opts.method || "GET"),
      headers: Object.assign({ "X-COS-Token": token }, opts.body ? { "Content-Type": "application/json" } : {}),
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error((data && data.error) || ("HTTP " + res.status));
    return data;
  }

  // Server-sent events over fetch, so the token stays in a header.
  function stream(path, onEvent) {
    const ctrl = new AbortController();
    (async () => {
      try {
        const res = await fetch(path, { headers: { "X-COS-Token": token }, signal: ctrl.signal });
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const chunk = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            const data = chunk.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
            if (data) { try { onEvent(JSON.parse(data)); } catch (e) { console.error(e); } }
          }
        }
        onEvent({ type: "stream_end" });
      } catch (e) {
        if (e.name !== "AbortError") onEvent({ type: "stream_end", error: String(e) });
      }
    })();
    return () => ctrl.abort();
  }

  async function job(path, body, onUpdate) {
    let j = await api(path, { body });
    onUpdate && onUpdate(j);
    while (!j.done) {
      await new Promise((r) => setTimeout(r, 700));
      j = await api("/api/jobs/" + j.id);
      onUpdate && onUpdate(j);
    }
    return j;
  }

  // ------------------------------------------------------------ dom helpers
  function h(tag, attrs) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "html") el.innerHTML = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "style" && typeof v === "object") {
        for (const [prop, val] of Object.entries(v)) {
          if (prop.startsWith("--")) el.style.setProperty(prop, val); else el.style[prop] = val;
        }
      }
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (let i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function append(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) c.forEach((x) => append(el, x));
    else el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }

  const store = {
    get(k, d) { try { const v = localStorage.getItem("cos:" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("cos:" + k, JSON.stringify(v)); } catch (e) {} },
  };

  // ------------------------------------------------------------ formatting
  const fmt = {
    bytes(n) {
      n = +n || 0;
      const u = ["B", "KB", "MB", "GB", "TB"];
      let i = 0;
      while (Math.abs(n) >= 1024 && i < u.length - 1) { n /= 1024; i++; }
      return (i === 0 ? n.toFixed(0) : n >= 100 ? n.toFixed(0) : n.toFixed(1)) + " " + u[i];
    },
    ago(ts) {
      if (!ts) return "never";
      const s = Math.max(0, Date.now() / 1000 - ts);
      if (s < 60) return "just now";
      if (s < 3600) return Math.floor(s / 60) + "m ago";
      if (s < 86400) return Math.floor(s / 3600) + "h ago";
      return Math.floor(s / 86400) + "d ago";
    },
    duration(sec) {
      sec = Math.max(0, Math.round(sec || 0));
      return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0");
    },
    uptime(sec) {
      if (sec == null) return "?";
      const d = Math.floor(sec / 86400), hh = Math.floor((sec % 86400) / 3600);
      return d ? d + "d " + hh + "h" : hh + "h " + Math.floor((sec % 3600) / 60) + "m";
    },
  };

  // ------------------------------------------------------------ icons
  const ICONS = {
    claude: '<path d="M12 3 21 12 12 21 3 12Z" fill="currentColor" stroke="none"/>',
    vitals: '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
    storage: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    updates: '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/>',
    music: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    feeds: '<path d="M5 11a8 8 0 0 1 8 8"/><path d="M5 5a14 14 0 0 1 14 14"/><circle cx="6" cy="18" r="1.4" fill="currentColor"/>',
    evolution: '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 7v10"/><path d="M18 10c0 4-6 3-11.5 7.5"/>',
    journal: '<path d="M6 3h11a2 2 0 0 1 2 2v16H7a2 2 0 0 1-2-2V4a1 1 0 0 1 1-1Z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    memory: '<path d="M12 3l2.4 5.6L20 11l-5.6 2.4L12 19l-2.4-5.6L4 11l5.6-2.4Z"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    play: '<path d="M7 4v16l13-8Z" fill="currentColor" stroke="none"/>',
    pause: '<path d="M7 4h4v16H7zM13 4h4v16h-4z" fill="currentColor" stroke="none"/>',
    next: '<path d="M5 4v16l10-8Z" fill="currentColor" stroke="none"/><path d="M18 4v16"/>',
    prev: '<path d="M19 4v16L9 12Z" fill="currentColor" stroke="none"/><path d="M6 4v16"/>',
    radio: '<circle cx="12" cy="12" r="1.8"/><path d="M8.5 15.5a5 5 0 0 1 0-7M15.5 8.5a5 5 0 0 1 0 7M5.6 18.4a9 9 0 0 1 0-12.8M18.4 5.6a9 9 0 0 1 0 12.8"/>',
    heart: '<path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10Z"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/>',
    send: '<path d="M4 12 20 4l-6 16-3-7Z"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    check: '<path d="m5 12 5 5 9-10"/>',
    terminal: '<path d="m5 8 4 4-4 4"/><path d="M12 17h7"/>',
    file: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>',
    spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  };
  function icon(name, size) {
    const s = size || 18;
    const span = document.createElement("span");
    span.className = "ico";
    span.innerHTML = '<svg width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + (ICONS[name] || "") + "</svg>";
    return span;
  }

  // ------------------------------------------------------------ toasts & dialogs
  function toast(msg, kind) {
    const el = h("div", { class: "toast " + (kind || "") }, msg);
    document.getElementById("toasts").appendChild(el);
    setTimeout(() => el.classList.add("out"), 4200);
    setTimeout(() => el.remove(), 4700);
  }

  function confirmDialog(opts) {
    return new Promise((resolve) => {
      const close = (v) => { overlay.remove(); resolve(v); };
      const overlay = h("div", { class: "modal-overlay", onclick: (e) => { if (e.target === overlay) close(false); } },
        h("div", { class: "modal" },
          h("div", { class: "modal-title" }, opts.title),
          opts.body ? h("div", { class: "modal-body" }, opts.body) : null,
          h("div", { class: "modal-actions" },
            h("button", { class: "btn ghost", onclick: () => close(false) }, opts.cancel || "Cancel"),
            h("button", { class: "btn " + (opts.danger ? "danger" : "primary"), onclick: () => close(true), autofocus: true }, opts.ok || "OK"))));
      document.body.appendChild(overlay);
      overlay.querySelector(".btn:last-child").focus();
      overlay.addEventListener("keydown", (e) => { if (e.key === "Escape") close(false); });
    });
  }

  // ------------------------------------------------------------ apps & windows
  const apps = {};
  const order = [];
  const wins = {};
  let z = 10;
  let focused = null;

  function register(app) { apps[app.id] = app; order.push(app.id); }

  function desktopRect() { return document.getElementById("desktop").getBoundingClientRect(); }

  const DOCK_SPACE = 88; // keep window bottoms clear of the dock

  function fit(p) {
    const d = desktopRect();
    const w = Math.max(340, Math.min(p.w, d.width - 24));
    const hgt = Math.max(240, Math.min(p.h, d.height - DOCK_SPACE - 12));
    const x = Math.max(8, Math.min(p.x, d.width - w - 8));
    const y = Math.max(8, Math.min(p.y, d.height - DOCK_SPACE - hgt));
    return { x, y, w, h: hgt };
  }

  function placement(app) {
    const saved = store.get("win:" + app.id);
    const d = desktopRect();
    const w = (saved && saved.w) || app.size[0];
    const hgt = (saved && saved.h) || app.size[1];
    if (saved && saved.x != null) return fit({ x: saved.x, y: saved.y, w, h: hgt });
    const n = Object.keys(wins).length;
    const today = document.getElementById("today").getBoundingClientRect();
    const clearOfToday = d.width - w > today.right + 40 ? today.right + 32 : 0; // don't cover the greeting if there's room
    return fit({ x: Math.max(clearOfToday, (d.width - w) / 2) + n * 28 + (app.offset || 0), y: (d.height - DOCK_SPACE - hgt) / 2 + n * 24, w, h: hgt });
  }

  function open(id, arg) {
    const app = apps[id];
    if (!app) return null;
    if (wins[id]) {
      const w = wins[id];
      w.el.classList.remove("minimized");
      focus(id);
      if (app.onReopen) app.onReopen(w, arg);
      return w;
    }
    const p = placement(app);
    const titleEl = h("div", { class: "win-title" }, app.title);
    const actions = h("div", { class: "win-actions" });
    const body = h("div", { class: "win-body " + (app.bodyClass || "") });
    const lights = h("div", { class: "lights" },
      h("button", { class: "light close", title: "Close", onclick: (e) => { e.stopPropagation(); close(id); } }),
      h("button", { class: "light min", title: "Minimize", onclick: (e) => { e.stopPropagation(); minimize(id); } }),
      h("button", { class: "light zoom", title: "Zoom", onclick: (e) => { e.stopPropagation(); zoom(id); } }));
    const bar = h("div", { class: "win-bar" }, lights, titleEl, actions);
    const grip = h("div", { class: "win-resize" });
    const el = h("section", { class: "win opening", "data-app": id, style: { left: p.x + "px", top: p.y + "px", width: p.w + "px", height: p.h + "px" } }, bar, body, grip);
    document.getElementById("windows").appendChild(el);
    requestAnimationFrame(() => el.classList.remove("opening"));
    const w = { id, app, el, body, actions, titleEl, setTitle: (t) => { titleEl.textContent = t; }, cleanup: [] };
    wins[id] = w;
    el.addEventListener("pointerdown", () => focus(id), true);
    drag(bar, el, id);
    resize(grip, el, id);
    bar.addEventListener("dblclick", (e) => { if (!e.target.closest("button")) zoom(id); });
    focus(id);
    try { app.render(w, arg); } catch (e) { console.error(e); body.appendChild(h("div", { class: "empty" }, "This app crashed: " + e.message)); }
    saveOpen();
    renderDock();
    return w;
  }

  function close(id) {
    const w = wins[id];
    if (!w) return;
    w.cleanup.forEach((fn) => { try { fn(); } catch (e) {} });
    w.el.classList.add("closing");
    setTimeout(() => w.el.remove(), 140);
    delete wins[id];
    if (focused === id) { focused = null; updateMenuTitle(); }
    saveOpen();
    renderDock();
  }

  function minimize(id) {
    const w = wins[id];
    if (!w) return;
    w.el.classList.add("minimized");
    if (focused === id) { focused = null; updateMenuTitle(); }
  }

  function zoom(id) {
    const w = wins[id];
    if (!w) return;
    const el = w.el;
    if (el.dataset.restore) {
      const r = JSON.parse(el.dataset.restore);
      Object.assign(el.style, r);
      delete el.dataset.restore;
    } else {
      el.dataset.restore = JSON.stringify({ left: el.style.left, top: el.style.top, width: el.style.width, height: el.style.height });
      const d = desktopRect();
      Object.assign(el.style, { left: "12px", top: "10px", width: d.width - 24 + "px", height: d.height - DOCK_SPACE - 10 + "px" });
    }
  }

  function focus(id) {
    const w = wins[id];
    if (!w) return;
    if (focused && wins[focused]) wins[focused].el.classList.remove("focused");
    w.el.style.zIndex = ++z;
    w.el.classList.add("focused");
    focused = id;
    updateMenuTitle();
  }

  function remember(id, el) {
    store.set("win:" + id, { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight });
  }

  function drag(handle, el, id) {
    handle.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || e.target.closest("button, input, select, a")) return;
      const sx = e.clientX, sy = e.clientY, ox = el.offsetLeft, oy = el.offsetTop;
      const d = desktopRect();
      handle.setPointerCapture(e.pointerId);
      const move = (ev) => {
        el.style.left = Math.max(-el.offsetWidth + 120, Math.min(d.width - 120, ox + ev.clientX - sx)) + "px";
        el.style.top = Math.max(0, Math.min(d.height - 60, oy + ev.clientY - sy)) + "px";
      };
      const up = () => { handle.removeEventListener("pointermove", move); handle.removeEventListener("pointerup", up); delete el.dataset.restore; remember(id, el); };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
    });
  }

  function resize(grip, el, id) {
    grip.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      const sx = e.clientX, sy = e.clientY, ow = el.offsetWidth, oh = el.offsetHeight;
      grip.setPointerCapture(e.pointerId);
      const move = (ev) => {
        el.style.width = Math.max(340, ow + ev.clientX - sx) + "px";
        el.style.height = Math.max(240, oh + ev.clientY - sy) + "px";
      };
      const up = () => { grip.removeEventListener("pointermove", move); grip.removeEventListener("pointerup", up); remember(id, el); };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
    });
  }

  function saveOpen() { store.set("open", Object.keys(wins)); }

  // ------------------------------------------------------------ dock
  const badges = {};
  function badge(id, n) { badges[id] = n; renderDock(); }

  function renderDock() {
    const dock = clear(document.getElementById("dock"));
    order.forEach((id, i) => {
      const app = apps[id];
      if (app.hidden) return;
      if (i > 0 && app.dockGap) dock.appendChild(h("div", { class: "dock-sep" }));
      const tile = h("div", { class: "dock-tile", style: { background: app.color } }, icon(app.icon || id, 22));
      const b = badges[id] ? h("span", { class: "dock-badge" }, String(badges[id])) : null;
      dock.appendChild(h("button", {
        class: "dock-item" + (wins[id] ? " running" : ""), title: app.title, "aria-label": app.title,
        onclick: () => (wins[id] && focused === id && !wins[id].el.classList.contains("minimized")) ? minimize(id) : open(id),
      }, tile, b, h("span", { class: "dock-label" }, app.title), h("span", { class: "dock-dot" })));
    });
  }

  // ------------------------------------------------------------ menu bar
  function updateMenuTitle() {
    document.getElementById("mb-app").textContent = focused && wins[focused] ? wins[focused].app.title : "Desktop";
  }

  function clock() {
    const now = new Date();
    document.getElementById("mb-clock").textContent = now.toLocaleDateString(navigator.language, { weekday: "short", day: "numeric", month: "short" }) +
      "  " + now.toLocaleTimeString(navigator.language, { hour: "2-digit", minute: "2-digit" });
  }

  const state = { status: null, music: null };
  const listeners = { status: [], music: [] };
  function on(kind, fn) { listeners[kind].push(fn); if (state[kind]) fn(state[kind]); }

  async function pollStatus() {
    try {
      state.status = await api("/api/status");
      listeners.status.forEach((fn) => fn(state.status));
      const s = state.status;
      document.getElementById("mb-disk").textContent = fmt.bytes(s.disk.free).replace(".0 ", " ") + " free";
      const batt = s.battery;
      document.getElementById("mb-batt").textContent = batt ? batt.percent + "%" + (batt.state === "charging" ? " ⚡︎" : "") : "";
      const sig = document.getElementById("mb-signals");
      sig.className = "mb-item signals " + (s.signals.some((x) => x.level === "warn") ? "warn" : s.signals.length ? "note" : "ok");
      sig.title = s.signals.map((x) => x.msg).join("\n") || "All quiet";
      const up = document.getElementById("mb-update"), co = s.claude_os;
      up.hidden = !(co && co.restart);
      if (co && co.restart) {
        up.title = co.waiting ? co.waiting + " merged on GitHub:\n" + co.subjects.join("\n")
          : "Claude OS's code changed since this window started";
      }
      document.body.classList.remove("offline");
    } catch (e) {
      document.body.classList.add("offline");
      const sig = document.getElementById("mb-signals");
      sig.className = "mb-item signals offline";
      sig.title = "Can't reach the Claude OS server: " + e.message;
    }
  }

  // Decision 0011: restart only the server, onto what's merged (it catches up as it starts).
  async function updateNow() {
    const co = (state.status || {}).claude_os || {};
    const ok = await confirmDialog({
      title: "Restart to update Claude OS?",
      body: (co.waiting ? "Brings in what you merged on GitHub, then restarts Claude OS's server. "
        : "Restarts Claude OS's server on the code that's on disk now. ")
        + "Music keeps playing; a reply that's still being written stops.",
      ok: "Restart",
    });
    if (!ok) return;
    toast("Restarting…");
    try { await api("/api/restart", { body: {} }); } catch (e) {}
  }

  async function pollMusic() {
    try {
      state.music = await api("/api/music/now");
      listeners.music.forEach((fn) => fn(state.music));
      const n = state.music;
      const el = document.getElementById("mb-music");
      if (n.running && n.track && n.state === "playing") {
        el.textContent = "♫ " + n.track + " — " + (n.artist || "");
        el.hidden = false;
      } else el.hidden = true;
    } catch (e) {}
  }

  // ------------------------------------------------------------ palette
  let paletteIndex = 0;
  function summon(prefill) {
    const pal = document.getElementById("palette");
    const input = document.getElementById("palette-input");
    pal.classList.remove("hidden");
    input.value = prefill || "";
    renderPalette();
    setTimeout(() => input.focus({ preventScroll: true }), 10);
  }
  function hidePalette() { document.getElementById("palette").classList.add("hidden"); }

  function paletteItems() {
    const q = document.getElementById("palette-input").value.trim();
    const ql = q.toLowerCase();
    const matches = order.filter((id) => !apps[id].hidden && (!ql || apps[id].title.toLowerCase().includes(ql) || (apps[id].keywords || "").includes(ql)))
      .map((id) => ({ label: "Open " + apps[id].title, icon: apps[id].icon || id, color: apps[id].color, run: () => open(id) }));
    const ask = q ? [{ label: "Ask Claude: " + q, icon: "claude", color: "var(--accent)", run: () => COS.ask(q) }] : [];
    const exact = matches.length && apps[order.find((id) => apps[id].title.toLowerCase() === ql)];
    return exact ? matches.concat(ask) : ask.concat(matches);
  }

  function renderPalette() {
    const list = clear(document.getElementById("palette-list"));
    const items = paletteItems();
    paletteIndex = Math.min(paletteIndex, Math.max(0, items.length - 1));
    items.forEach((it, i) => {
      list.appendChild(h("div", { class: "pal-item" + (i === paletteIndex ? " active" : ""), onmousedown: (e) => { e.preventDefault(); hidePalette(); it.run(); } },
        h("span", { class: "pal-ico", style: { background: it.color } }, icon(it.icon, 14)), h("span", null, it.label)));
    });
  }

  function wirePalette() {
    const input = document.getElementById("palette-input");
    input.addEventListener("input", () => { paletteIndex = 0; renderPalette(); });
    input.addEventListener("keydown", (e) => {
      const items = paletteItems();
      if (e.key === "ArrowDown") { paletteIndex = Math.min(items.length - 1, paletteIndex + 1); renderPalette(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { paletteIndex = Math.max(0, paletteIndex - 1); renderPalette(); e.preventDefault(); }
      else if (e.key === "Enter") { const it = items[paletteIndex]; hidePalette(); if (it) it.run(); }
      else if (e.key === "Escape") hidePalette();
    });
    document.getElementById("palette").addEventListener("mousedown", (e) => { if (e.target.id === "palette") hidePalette(); });
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); summon(); }
    });
  }

  // ------------------------------------------------------------ boot
  async function boot() {
    const overlay = document.getElementById("boot");
    let lines = [];
    let booted = false;
    try { booted = sessionStorage.getItem("cos-booted") === "1"; } catch (e) {}
    if (!token) {
      overlay.querySelector(".boot-log").textContent = "No session token. Open Claude OS from the app, or run `cos serve --open`.";
      return;
    }
    try { lines = (await api("/api/boot")).lines; } catch (e) { lines = ["◆ Claude OS", "  couldn't reach the server: " + e.message]; }
    if (!booted) {
      const log = overlay.querySelector(".boot-log");
      for (const line of lines.slice(0, 9)) {
        log.appendChild(h("div", { class: "boot-line" }, line));
        await new Promise((r) => setTimeout(r, 90));
      }
      await new Promise((r) => setTimeout(r, 350));
      try { sessionStorage.setItem("cos-booted", "1"); } catch (e) {}
    }
    overlay.classList.add("done");
    setTimeout(() => overlay.remove(), 600);
  }

  // ------------------------------------------------------------ start
  function start() {
    renderDock();
    wirePalette();
    clock();
    setInterval(clock, 15000);
    document.getElementById("mb-logo").addEventListener("click", () => summon());
    document.getElementById("mb-music").addEventListener("click", () => open("music"));
    document.getElementById("mb-signals").addEventListener("click", () => open("vitals"));
    document.getElementById("mb-update").addEventListener("click", updateNow);
    boot().then(() => {
      if (!token) return;
      const statusLoop = async () => {
        await pollStatus();
        setTimeout(statusLoop, document.body.classList.contains("offline") ? 5000 : 60000);
      };
      statusLoop();
      pollMusic();
      setInterval(pollMusic, 8000);
      if (COS.onBoot) COS.onBoot();  // draw the desktop first, so windows can be placed around it
      const reopen = store.get("open", ["claude"]);
      (reopen.length ? reopen : ["claude"]).forEach((id) => open(id));
    });
    window.addEventListener("resize", () => {
      document.getElementById("desktop").scrollTop = 0;
      Object.values(wins).forEach((w) => {
        if (w.el.dataset.restore) return;
        const p = fit({ x: w.el.offsetLeft, y: w.el.offsetTop, w: w.el.offsetWidth, h: w.el.offsetHeight });
        Object.assign(w.el.style, { left: p.x + "px", top: p.y + "px", width: p.w + "px", height: p.h + "px" });
      });
    });
    // Focusing a field inside an overflow:hidden container can still scroll it; never let the desktop move.
    document.getElementById("desktop").addEventListener("scroll", (e) => { e.target.scrollTop = 0; e.target.scrollLeft = 0; });
  }

  // Where a notification's click lands (Notifier.swift, decision 0007): a fixed view per
  // target. Anything else does nothing.
  const VIEWS = { board: ["evolution", "Board"], evolve: ["evolution", "Branches"], brief: ["feeds", "brief"], daemons: ["settings"] };
  function show(target) {
    const view = Object.prototype.hasOwnProperty.call(VIEWS, target) ? VIEWS[target] : null;
    return view ? open(view[0], view[1]) : null;
  }

  const COS = window.cos = window.COS = {
    api, stream, job, h, clear, icon, fmt, store, toast, confirm: confirmDialog,
    register, open, close, focus, wins, badge, on, state, summon, show,
    refreshStatus: pollStatus, refreshMusic: pollMusic,
    ask: (text) => { const w = open("claude"); if (w && w.ask) w.ask(text); },
  };
  document.addEventListener("DOMContentLoaded", start);
})();
