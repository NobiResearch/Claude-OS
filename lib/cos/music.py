"""cos music — Apple Music, driven by AppleScript plus the public iTunes Search API.

What's reliable: everything in the user's library (search, play, playlists,
transport, volume). What's best-effort: songs that are only in the Apple Music
catalog. AppleScript cannot address catalog items directly, so we open the
item's page in Music and press play; if Music doesn't start it, the page is
left open on the right song and we say so honestly.

Hard-won rules (see docs/lessons.md):
  * Never play at volume 0: Music shows a modal warning that blocks all
    further Apple Events until a human dismisses it. `vol 0` pauses instead.
  * Never use System Events UI scripting: it triggers a permission prompt.
  * Every osascript call has a timeout.
"""

import json
import os
import re
import time
import unicodedata
import urllib.parse

from . import core

US, RS = "\x1f", "\x1e"   # unit / record separators keep AppleScript output parseable
AS_US, AS_RS = "(character id 31)", "(character id 30)"


def _tell(body, timeout=10):
    return core.osascript('tell application "Music"\n%s\nend tell' % body, timeout=timeout)


def _records(text):
    return [r.split(US) for r in text.split(RS) if r.strip()]


# ---------------------------------------------------------------- state

NOW_SCRIPT = """
set out to (player state as text)
try
  set t to current track
  set out to out & %(us)s & (name of t) & %(us)s & (artist of t) & %(us)s & (album of t) & %(us)s & (duration of t) & %(us)s & (player position)
on error
  try
    set out to out & %(us)s & (current stream title) & %(us)s & "" & %(us)s & "" & %(us)s & "0" & %(us)s & "0"
  on error
    set out to out & %(us)s & "" & %(us)s & "" & %(us)s & "" & %(us)s & "0" & %(us)s & "0"
  end try
end try
set out to out & %(us)s & (sound volume) & %(us)s & (shuffle enabled) & %(us)s & (song repeat as text)
return out
""" % {"us": AS_US}


def now():
    if not core.app_running("Music"):
        return {"running": False}
    r = _tell(NOW_SCRIPT, timeout=6)
    if not r.ok:
        return {"running": True, "error": r.err[:200]}
    parts = (r.out.split(US) + [""] * 9)[:9]
    state, name, artist, album, duration, position, volume, shuffle, repeat = parts

    def num(x):
        try:
            return float(x.replace(",", "."))
        except ValueError:
            return 0.0

    return {"running": True, "state": state, "track": name or None, "artist": artist or None,
            "album": album or None, "duration": num(duration), "position": num(position),
            "volume": int(num(volume)), "shuffle": shuffle == "true", "repeat": repeat}


def render_now(n):
    if not n.get("running"):
        print("Music isn't running.")
        return
    if n.get("error"):
        print("Music didn't answer: %s" % n["error"])
        return
    if not n.get("track"):
        print("Music is %s, nothing loaded. (volume %s)" % (n["state"], n.get("volume")))
        return
    pos = "%d:%02d / %d:%02d" % (n["position"] // 60, n["position"] % 60, n["duration"] // 60, n["duration"] % 60)
    print("%s %s — %s" % ("▶" if n["state"] == "playing" else "❚❚", n["track"], n["artist"] or "?"))
    print("  %s · %s · vol %d%s" % (n["album"] or "", pos, n["volume"], " · shuffle" if n["shuffle"] else ""))


# ---------------------------------------------------------------- library

def library_search(query, limit=20):
    body = """
set res to search library playlist 1 for %s
set out to ""
set n to count of res
if n > %d then set n to %d
repeat with i from 1 to n
  set t to item i of res
  set out to out & (persistent ID of t) & %s & (name of t) & %s & (artist of t) & %s & (album of t) & %s & (genre of t) & %s & (duration of t) & %s
end repeat
return out
""" % (core.applescript_str(query), limit, limit, AS_US, AS_US, AS_US, AS_US, AS_US, AS_RS)
    r = _tell(body, timeout=20)
    if not r.ok:
        return []
    out = []
    for rec in _records(r.out):
        if len(rec) >= 6:
            out.append({"id": rec[0], "name": rec[1], "artist": rec[2], "album": rec[3],
                        "genre": rec[4], "duration": rec[5], "source": "library"})
    return out


def play_library(track):
    body = 'play (first track of library playlist 1 whose persistent ID is %s)' % core.applescript_str(track["id"])
    r = _tell(body, timeout=10)
    if not r.ok:
        return {"ok": False, "error": r.err[:200]}
    return _confirm(track["name"])


def playlists():
    body = """
set out to ""
repeat with p in user playlists
  set out to out & (name of p) & %s & (count of tracks of p) & %s
end repeat
return out
""" % (AS_US, AS_RS)
    r = _tell(body, timeout=30)
    return [{"name": rec[0], "tracks": int(rec[1]) if rec[1].isdigit() else 0}
            for rec in _records(r.out) if len(rec) >= 2]


def play_playlist(name, shuffle=None):
    lists = playlists()
    wanted = fold(name)
    match = next((p for p in lists if fold(p["name"]) == wanted), None) \
        or next((p for p in lists if wanted in fold(p["name"])), None)
    if not match:
        return {"ok": False, "error": "no playlist matching %r" % name,
                "playlists": [p["name"] for p in lists]}
    body = ""
    if shuffle is not None:
        body += "set shuffle enabled to %s\n" % ("true" if shuffle else "false")
    body += "play user playlist %s" % core.applescript_str(match["name"])
    r = _tell(body, timeout=10)
    if not r.ok:
        return {"ok": False, "error": r.err[:200]}
    res = _confirm(None)
    res["playlist"] = match["name"]
    return res


# ---------------------------------------------------------------- catalog

def storefront():
    return core.config()["music"].get("storefront") or core.locale_country()


def catalog_search(query, limit=10, entity="song"):
    params = urllib.parse.urlencode({"term": query, "media": "music", "entity": entity,
                                     "limit": limit, "country": storefront()})
    try:
        with core.http_get("https://itunes.apple.com/search?" + params, timeout=10) as resp:
            data = json.load(resp)
    except Exception as e:
        return {"error": str(e), "results": []}
    return {"error": None, "results": [parse_catalog_item(r) for r in data.get("results", [])]}


def parse_catalog_item(r):
    url = r.get("trackViewUrl") or r.get("collectionViewUrl") or ""
    url = re.sub(r"[?&]uo=\d+", "", url).replace("?&", "?")
    return {"name": r.get("trackName") or r.get("collectionName"), "artist": r.get("artistName"),
            "album": r.get("collectionName"), "genre": r.get("primaryGenreName"),
            "year": (r.get("releaseDate") or "")[:4], "url": url,
            "track_number": r.get("trackNumber"), "track_count": r.get("trackCount"),
            "duration": (r.get("trackTimeMillis") or 0) / 1000.0, "source": "catalog",
            "artwork": (r.get("artworkUrl100") or "").replace("100x100bb", "600x600bb") or None}


def best_catalog_pick(results):
    """Among versions of the top hit, prefer one that is track 1 (a single), since
    pressing play on an album page starts at track 1."""
    if not results:
        return None
    top = results[0]
    same = [r for r in results if fold(r["name"]) == fold(top["name"]) and fold(r["artist"]) == fold(top["artist"])]
    for r in same:
        if r.get("track_number") == 1:
            return r
    return top


def play_catalog(item):
    url = item["url"].replace("https://", "music://", 1)
    if now().get("state") == "playing":
        _tell("pause", timeout=5)  # otherwise "play" below is a no-op
    r = _tell("open location %s" % core.applescript_str(url), timeout=15)
    if not r.ok:
        return {"ok": False, "error": r.err[:200]}
    # Give the page time to load, press play once, then be patient: streams
    # can take several seconds to start, and re-pressing play restarts them.
    n = {}
    pressed = None
    for attempt in range(2):
        time.sleep(2.5)
        if full_control():
            pressed = helper("press-play")
        if not (pressed and pressed.get("ok")):
            _tell("play", timeout=6)
        n = _wait_playing(10)
        if n.get("state") == "playing":
            break
    else:
        return {"ok": False, "opened": True,
                "error": "Opened %s — %s in Music, but Music didn't start it. Press ▶ there "
                         "(catalog playback isn't fully scriptable)." % (item["name"], item["artist"])}
    target = fold(item["name"])
    same_album = bool(n.get("album")) and fold(n["album"]) == fold(item.get("album"))
    if n.get("track") and fold(n["track"]) != target and same_album and (item.get("track_number") or 1) > 1:
        # Album pages start at track 1; step forward to the song we wanted.
        for _ in range(item["track_number"] - 1):
            _tell("next track", timeout=5)
        n = _wait_playing(6)
    if n.get("track") and fold(n["track"]) != target:
        # Music resumed its old queue instead of the page we opened. Don't leave the
        # wrong song playing and call it a success.
        wrong = "%s — %s" % (n["track"], n.get("artist") or "?")
        _tell("pause", timeout=5)
        return {"ok": False, "opened": True,
                "error": "Music started %s instead, so I paused it. %s — %s is open in Music; press ▶ there "
                         "(catalog playback isn't fully scriptable)." % (wrong, item["name"], item["artist"])}
    return {"ok": True, "now": n, "matched": bool(n.get("track"))}


# ---------------------------------------------------------------- the helper (decision 0003)
#
# "Full Music control" is a tiny separate app, Claude OS Music Helper, that holds its own
# Accessibility grant. It's started with `open`, so macOS charges the permission to the
# helper alone: Claude OS.app and the Claude sessions it spawns never get it. The helper
# only knows fixed commands and presses Music's own controls through the accessibility
# API; it never types keys.

HELPER = "Claude OS Music Helper.app"
ACCESSIBILITY_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


def helper_path():
    for base in (os.path.expanduser("~/Applications/Claude OS.app"), str(core.ROOT / "build" / "Claude OS.app")):
        path = os.path.join(base, "Contents", "Helpers", HELPER)
        if os.path.isdir(path):
            return path
    return None


def helper(command, timeout=20):
    if command not in ("status", "request", "inspect", "press-play"):
        return {"ok": False, "error": "unknown helper command"}
    if os.environ.get("CLAUDE_OS_DAEMON"):
        return {"ok": False, "error": "the music helper never runs from background jobs"}
    path = helper_path()
    if not path:
        return {"ok": False, "error": "the music helper isn't installed (cos app install)"}
    import tempfile
    with tempfile.TemporaryDirectory(prefix="cos-helper-") as tmp:
        out, err = os.path.join(tmp, "out"), os.path.join(tmp, "err")
        r = core.run(["open", "-n", "-g", "-W", "--stdout", out, "--stderr", err, path, "--args", command],
                     timeout=timeout)
        text = _read(out).strip().splitlines()
        if not text:
            return {"ok": False, "error": (r.err or _read(err) or "no answer from the helper")[:300]}
        try:
            res = json.loads(text[-1])
        except ValueError:
            return {"ok": False, "error": "unreadable answer from the helper"}
    res.setdefault("ok", r.ok)
    return res


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def full_control():
    """On only when the human turned it on *and* macOS has granted the helper."""
    if not core.config()["music"].get("full_control"):
        return False
    cached = core.cache_get("music-helper", max_age=60)
    if cached is None:
        cached = core.cache_put("music-helper", bool(helper("status").get("trusted")))
    return bool(cached["data"])


# ---------------------------------------------------------------- shortcut route

SHORTCUT = "Claude OS Play"
SETUP_STEPS = """\
Catalog playback through Shortcuts (one-time, no new permissions):

  1. Open the Shortcuts app and make a new shortcut named exactly:  %s
  2. Add "Get Text from Input" (the input arrives as a file).
  3. Add Music's "Play" action and set its music item to the Text from step 2.
  4. Save. Then try:  cos music play "sunset lover petit biscuit" --source shortcut

Siri's music search resolves the text, so it reaches the whole Apple Music catalog.
""" % SHORTCUT


def shortcut_installed():
    cached = core.cache_get("music-shortcut", max_age=300)
    if cached is not None:
        return cached["data"]
    r = core.run(["shortcuts", "list"], timeout=15)
    found = r.ok and any(line.strip() == SHORTCUT for line in r.out.splitlines())
    core.cache_put("music-shortcut", found)
    return found


def play_via_shortcut(query, expect=None):
    """Hand the request to the human's "Claude OS Play" shortcut, then verify."""
    import tempfile
    before = now()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(query)
        path = f.name
    try:
        r = core.run(["shortcuts", "run", SHORTCUT, "--input-path", path], timeout=45)
    finally:
        os.unlink(path)
    if not r.ok:
        return {"ok": False, "error": "the %s shortcut failed: %s" % (SHORTCUT, (r.err or r.out)[:200])}
    n = _wait_playing(10)
    changed = n.get("track") != before.get("track") or before.get("state") != "playing"
    if n.get("state") != "playing" or not changed:
        return {"ok": False, "error": "the shortcut ran, but Music isn't playing anything new"}
    matched = None
    if expect:
        matched = fold(expect) in fold(n.get("track")) or fold(n.get("track")) in fold(expect)
    return {"ok": True, "now": n, "matched": matched if matched is not None else True}


# ---------------------------------------------------------------- helpers

def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def _wait_playing(seconds):
    deadline = time.time() + seconds
    n = now()
    while n.get("state") != "playing" and time.time() < deadline:
        time.sleep(0.7)
        n = now()
    return n


def _confirm(name):
    n = _wait_playing(10)
    if n.get("state") == "playing":
        return {"ok": True, "now": n, "matched": name is None or fold(n.get("track")) == fold(name)}
    return {"ok": False, "now": n, "error": "Music accepted the command but isn't playing (yet). "
                                            "If a dialog is open in Music, it needs a human click."}


def play(query, source="auto", pick=0):
    tried = []
    if source in ("auto", "library"):
        hits = library_search(query)
        tried.append("library (%d hits)" % len(hits))
        if hits:
            track = hits[min(pick, len(hits) - 1)]
            res = play_library(track)
            res.update(source="library", chosen=track)
            return res
    if source in ("auto", "shortcut") and (source == "shortcut" or shortcut_installed()):
        tried.append("shortcut")
        cat = catalog_search(query, limit=3)
        pick_ = best_catalog_pick(cat["results"]) if cat["results"] else None
        spoken = "%s %s" % (pick_["name"], pick_["artist"]) if pick_ else query
        res = play_via_shortcut(spoken, expect=pick_["name"] if pick_ else None)
        if res.get("ok") or source == "shortcut":
            res.update(source="shortcut", chosen=pick_ or {"name": query})
            return res
    if source in ("auto", "catalog"):
        cat = catalog_search(query, limit=8)
        tried.append("catalog (%d hits)" % len(cat["results"]))
        if cat["results"]:
            item = cat["results"][min(pick, len(cat["results"]) - 1)] if pick else best_catalog_pick(cat["results"])
            res = play_catalog(item)
            res.update(source="catalog", chosen=item)
            return res
        if cat["error"]:
            return {"ok": False, "error": "catalog search failed: %s" % cat["error"], "tried": tried}
    return {"ok": False, "error": "nothing found for %r" % query, "tried": tried}


def report(res, query=None):
    chosen = res.get("chosen") or {}
    if res.get("ok"):
        n = res.get("now") or {}
        name = n.get("track") or chosen.get("name")
        artist = n.get("artist") or chosen.get("artist")
        print("▶ %s — %s%s" % (name, artist, "  [%s]" % res["source"] if res.get("source") else ""))
        if res.get("playlist"):
            print("  playlist: %s" % res["playlist"])
        if res.get("matched") is False:
            print("  note: Music is playing something, but I couldn't confirm it's %r." % chosen.get("name"))
        core.journal("music", "played %s — %s" % (name, artist), query=query, source=res.get("source"),
                     track=name, artist=artist, playlist=res.get("playlist"))
        return 0
    print("✗ %s" % res.get("error"))
    if res.get("opened"):
        core.journal("music", "opened %s — %s" % (chosen.get("name"), chosen.get("artist")), query=query,
                     source="catalog", track=chosen.get("name"), artist=chosen.get("artist"), opened_only=True)
    return 1


def transport(cmd):
    scripts = {"pause": "pause", "resume": "play", "toggle": "playpause", "next": "next track",
               "prev": "back track", "stop": "stop"}
    r = _tell(scripts[cmd], timeout=6)
    if not r.ok:
        print("✗ %s" % r.err[:200])
        return 1
    time.sleep(0.3)
    render_now(now())
    return 0


def volume(level):
    if level is None:
        print(now().get("volume"))
        return 0
    level = max(0, min(100, level))
    if level == 0:
        _tell("pause")
        print("Paused instead of muting (Music blocks on a dialog when it plays at volume 0).")
        return 0
    _tell("set sound volume to %d" % level)
    print("volume %d" % level)
    return 0


def like():
    r = _tell("try\nset favorited of current track to true\non error\nset loved of current track to true\nend try\n"
              "return (name of current track) & \" — \" & (artist of current track)")
    if not r.ok:
        print("✗ couldn't favorite: %s" % r.err[:200])
        return 1
    core.journal("music", "liked %s" % r.out, liked=True, track=r.out)
    print("♥ %s" % r.out)
    return 0


def history(days):
    rows = core.read_journal(days=days, kind="music")
    for e in rows[-40:]:
        print("%s  %s" % (e["ts"][:16].replace("T", " "), e["msg"]))
    if not rows:
        print("No music in the last %d days." % days)
    return 0


def main(args):
    c = args.music_cmd or "now"
    if c == "now":
        core.emit(now(), args.json, render_now)
        return 0
    if c == "play":
        if not args.query:
            return transport("resume")
        q = " ".join(args.query)
        res = play(q, source=args.source, pick=args.pick)
        if args.json:
            core.emit(res, True, None)
            return 0 if res.get("ok") else 1
        return report(res, q)
    if c in ("pause", "resume", "toggle", "next", "prev", "stop"):
        return transport(c)
    if c == "vol":
        return volume(args.level)
    if c == "find":
        hits = library_search(" ".join(args.query))
        core.emit(hits, args.json, lambda h: [print("%2d. %s — %s  (%s · %s)" % (i, t["name"], t["artist"], t["album"], t["genre"]))
                                           for i, t in enumerate(h)] or print("no library matches"))
        return 0
    if c == "catalog":
        res = catalog_search(" ".join(args.query), limit=args.limit)
        core.emit(res, args.json, lambda d: [print("%2d. %s — %s  (%s, %s · %s)" % (i, t["name"], t["artist"], t["album"], t["year"], t["genre"]))
                                          for i, t in enumerate(d["results"])] or print(d["error"] or "no catalog matches"))
        return 0
    if c == "playlists":
        core.emit(playlists(), args.json, lambda ps: [print("%-40s %d" % (p["name"], p["tracks"])) for p in ps])
        return 0
    if c == "playlist":
        shuffle = True if args.shuffle else None
        res = play_playlist(" ".join(args.name), shuffle=shuffle)
        if not res.get("ok") and res.get("playlists"):
            print("✗ %s. Playlists: %s" % (res["error"], ", ".join(res["playlists"])))
            return 1
        return report(res, " ".join(args.name))
    if c == "shuffle":
        _tell("set shuffle enabled to %s" % ("true" if args.state == "on" else "false"))
        print("shuffle %s" % args.state)
        return 0
    if c == "like":
        return like()
    if c == "history":
        return history(args.days)
    if c == "setup":
        on = core.config()["music"].get("full_control")
        trusted = helper("status").get("trusted") if helper_path() else None
        print("Full Music control: %s" % ("on" if on else "off"))
        print("  helper: %s" % ("not installed (cos app install)" if trusted is None else
                                "allowed in Accessibility ✓" if trusted else "not yet allowed in Accessibility"))
        print("  turn it on in Claude OS › Settings, or: cos config music.full_control true\n")
        print(SETUP_STEPS)
        print("Shortcut: %s" % ("installed ✓" if shortcut_installed() else "not installed"))
        return 0
    core.die("unknown music command %r" % c)
