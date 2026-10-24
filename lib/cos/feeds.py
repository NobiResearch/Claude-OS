"""cos feeds — a tiny RSS/Atom reader with read-tracking.

Feed lists: etc/feeds.txt (curated, public) + ~/.claude-os/feeds.txt (yours).
Mute a curated feed with `cos feeds mute <url>`; that list is private too.
"""

import datetime as dt
import email.utils
import hashlib
import html
import re
import time
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from . import core

FRESH_SECONDS = 30 * 60


# ---------------------------------------------------------------- feed lists

def parse_feed_list(text):
    """Lines of `url  [# name]`; `## Category` headers group what follows."""
    feeds, category = [], "misc"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            category = line.lstrip("#").strip().lower()
            continue
        if line.startswith("#"):
            continue
        url, _, name = line.partition("#")
        feeds.append({"url": url.strip(), "name": name.strip() or None, "category": category})
    return feeds


def _read(path):
    try:
        return path.read_text()
    except OSError:
        return ""


def feed_list():
    curated = parse_feed_list(_read(core.ROOT / "etc" / "feeds.txt"))
    mine = parse_feed_list(_read(core.home("feeds.txt")))
    for f in mine:
        f["personal"] = True
    muted = {f["url"] for f in parse_feed_list(_read(core.home("feeds-muted.txt")))}
    seen, out = set(), []
    for f in curated + mine:
        if f["url"] in seen or f["url"] in muted:
            continue
        seen.add(f["url"])
        out.append(f)
    return out


# ---------------------------------------------------------------- parsing

def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _text(el, *names):
    for name in names:
        c = _child(el, name)
        if c is not None and (c.text or "").strip():
            return c.text.strip()
    return ""


def parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        if d is not None:
            return d.timestamp() if d.tzinfo else d.replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError, IndexError):
        pass
    iso = s.strip().replace("Z", "+00:00")
    iso = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), iso)
    iso = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", iso)  # Python 3.9 wants +02:00, not +0200
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.timestamp() if d.tzinfo else d.replace(tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return None


def strip_html(s, limit=280):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[:limit - 1].rsplit(" ", 1)[0] + "…"


def parse_feed(xml_bytes):
    """Return (title, items) for RSS 2.0, RSS 1.0/RDF, or Atom."""
    root = ET.fromstring(xml_bytes)
    kind = _local(root.tag)
    items = []
    if kind == "feed":  # Atom
        title = _text(root, "title")
        for e in root:
            if _local(e.tag) != "entry":
                continue
            link = ""
            for l in e:
                if _local(l.tag) == "link" and l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            items.append({"title": strip_html(_text(e, "title"), 200), "link": link,
                          "id": _text(e, "id") or link,
                          "ts": parse_date(_text(e, "published", "updated")),
                          "summary": strip_html(_text(e, "summary", "content"))})
        return title, items
    channel = _child(root, "channel")
    title = _text(channel, "title") if channel is not None else ""
    containers = [root] + ([channel] if channel is not None else [])
    for container in containers:
        for e in container:
            if _local(e.tag) != "item":
                continue
            link = _text(e, "link")
            items.append({"title": strip_html(_text(e, "title"), 200), "link": link,
                          "id": _text(e, "guid") or link or _text(e, "title"),
                          "ts": parse_date(_text(e, "pubDate", "date", "published")),
                          "summary": strip_html(_text(e, "description", "encoded"))})
    return title, items


# ---------------------------------------------------------------- fetching

def fetch(feed, http_cache):
    url = feed["url"]
    headers = {}
    prev = http_cache.get(url, {})
    if prev.get("etag"):
        headers["If-None-Match"] = prev["etag"]
    if prev.get("modified"):
        headers["If-Modified-Since"] = prev["modified"]
    try:
        with core.http_get(url, headers=headers, timeout=12) as resp:
            body = resp.read()
            meta = {"etag": resp.headers.get("ETag"), "modified": resp.headers.get("Last-Modified")}
        title, items = parse_feed(body)
        return {"url": url, "ok": True, "title": title, "items": items[:40], "meta": meta}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return {"url": url, "ok": True, "not_modified": True}
        body = core.curl_get(url) if e.code in (403, 429, 503) else None
        if body:
            try:
                title, items = parse_feed(body)
                return {"url": url, "ok": True, "title": title, "items": items[:40], "meta": {}}
            except ET.ParseError:
                pass
        return {"url": url, "ok": False, "error": "HTTP %d" % e.code}
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)[:120]}


def refresh(force=False):
    store = core.load_json(core.home("cache", "feeds.json"), {}) or {}
    if not force and time.time() - store.get("ts", 0) < FRESH_SECONDS:
        return store
    feeds = feed_list()
    http_cache = store.get("http", {})
    old = store.get("feeds", {})
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda f: fetch(f, http_cache), feeds))
    new_feeds = {}
    for f, r in zip(feeds, results):
        prev = old.get(f["url"], {})
        entry = {"name": f["name"] or prev.get("title") or f["url"], "category": f["category"],
                 "ok": r["ok"], "error": r.get("error"), "items": prev.get("items", []),
                 "title": prev.get("title")}
        if r["ok"] and not r.get("not_modified"):
            entry["items"] = r["items"]
            entry["title"] = r["title"]
            entry["name"] = f["name"] or r["title"] or f["url"]
            http_cache[f["url"]] = r["meta"]
        new_feeds[f["url"]] = entry
    store = {"ts": time.time(), "feeds": new_feeds, "http": http_cache}
    core.save_json(core.home("cache", "feeds.json"), store)
    return store


def item_key(url, item):
    return hashlib.sha1(("%s|%s" % (url, item.get("id") or item.get("link"))).encode()).hexdigest()[:16]


def unread(store, since_hours=None, category=None, include_read=False):
    seen = set(core.load_json(core.home("state", "feeds-seen.json"), []) or [])
    cutoff = time.time() - since_hours * 3600 if since_hours else 0
    out = []
    for url, f in store.get("feeds", {}).items():
        if category and f["category"] != category:
            continue
        for it in f["items"]:
            key = item_key(url, it)
            if not include_read and key in seen:
                continue
            if cutoff and (it.get("ts") or 0) < cutoff:
                continue
            out.append(dict(it, feed=f["name"], category=f["category"], key=key))
    out.sort(key=lambda i: -(i.get("ts") or 0))
    return out


def mark_read(keys):
    path = core.home("state", "feeds-seen.json")
    seen = list(dict.fromkeys((core.load_json(path, []) or []) + list(keys)))
    core.save_json(path, seen[-20000:])


def render_items(items):
    if not items:
        print("Nothing unread. (cos feeds --all to see everything)")
        return
    for it in items:
        when = core.ago(it["ts"]) if it.get("ts") else ""
        print("· %s\n  %s · %s · %s" % (it["title"], it["feed"], when, it["link"]))


# ---------------------------------------------------------------- commands

def _append(path, line):
    with open(path, "a") as f:
        f.write(line + "\n")


def main(args):
    c = args.feeds_cmd or "read"
    if c == "list":
        store = core.load_json(core.home("cache", "feeds.json"), {}) or {}
        for f in feed_list():
            s = store.get("feeds", {}).get(f["url"])
            status = "–" if not s else ("ok %d" % len(s["items"]) if s["ok"] else "✗ " + (s["error"] or ""))
            print("%-10s %-8s %-38s %s" % (f["category"], status, (f["name"] or (s or {}).get("name") or "")[:38], f["url"]))
        return 0
    if c == "add":
        r = fetch({"url": args.url}, {})
        if not r["ok"]:
            core.die("couldn't read that feed: %s" % r["error"])
        _append(core.home("feeds.txt"), "%s  # %s" % (args.url, args.name or r["title"]))
        print("added: %s (%d items)" % (args.name or r["title"], len(r["items"])))
        return 0
    if c == "mute":
        _append(core.home("feeds-muted.txt"), args.url)
        print("muted %s" % args.url)
        return 0
    if c == "mark-read":
        store = refresh(force=False)
        items = unread(store)
        mark_read(i["key"] for i in items)
        print("marked %d items read" % len(items))
        return 0
    store = refresh(force=args.refresh)
    items = unread(store, since_hours=args.since, category=args.category, include_read=args.all)[:args.limit]
    if args.mark_read:
        mark_read(i["key"] for i in items)
    core.emit(items, args.json, render_items)
    return 0
