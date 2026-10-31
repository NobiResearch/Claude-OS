"""cos music — Apple Music, through Ovenbird's own player plus the Music app.

With "Apple Music in Ovenbird" on (decisions 0003/0004), songs, library songs and playlists
play in the app's MusicKit player, and pause, next, shuffle and love go there while it has a
song. Otherwise the Music app is driven by AppleScript: reliable for the library, while
catalog-only songs open on their page in Music (and we say so honestly if it doesn't play).
The public iTunes Search API finds catalog songs either way.

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


_talked = False  # did this process get an answer from Music.app?


def _tell(body, timeout=10):
    global _talked
    r = core.osascript('tell application "Music"\n%s\nend tell' % body, timeout=timeout)
    _talked = _talked or r.ok
    return r


ASKED_FILE = ("state", "music-asked.flag")  # a suffix, or core.home makes it a folder


def asked():
    """Has a person's `cos music`, or a click or search in the desktop, talked to Music.app on
    this Mac? Only then do the boot banner, the status line, `cos doctor` and the desktop's own
    polling ask Music anything: the first AppleScript to it makes macOS ask whether Ovenbird may
    control Music, and that dialog should follow someone asking for music, not a session or the
    desktop starting."""
    return core.home(*ASKED_FILE).is_file()


def _note_asked():
    """After a person's command, click or search that Music.app answered, never in a background
    run."""
    if not _talked or os.environ.get("CLAUDE_OS_DAEMON") or asked():
        return
    try:
        path = core.home(*ASKED_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    except OSError:
        pass


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


def _own_now(st):
    """Ovenbird's player state, shaped like now()."""
    state = st.get("status") if st.get("status") in ("playing", "paused") else "playing"
    return {"running": True, "state": state, "track": st.get("track"), "artist": st.get("artist"),
            "album": st.get("album"), "duration": st.get("duration", 0), "position": st.get("position", 0),
            "volume": None, "shuffle": bool(st.get("shuffle")), "repeat": "off", "player": "Ovenbird",
            "playlist": st.get("playlist"), "radio": st.get("radio"), "station": st.get("station"),
            "artwork": st.get("artwork") or None}


def now(ask_music=True):
    """What's playing. ask_music False: Ovenbird's own player only (see asked)."""
    own = own_player_active()
    if own and own["status"] == "playing":
        return _own_now(own)
    app = _music_app_now() if ask_music else {"running": False}
    # Paused in Ovenbird is still the song on screen, unless Music is playing something else.
    if own and app.get("state") != "playing":
        return _own_now(own)
    return app


def _music_app_now():
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
    where = "in Ovenbird" if n.get("player") == "Ovenbird" else "vol %d" % (n.get("volume") or 0)
    print("  %s · %s · %s%s" % (n["album"] or "", pos, where, " · shuffle" if n.get("shuffle") else ""))


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
    if player_enabled():
        res = player_command("play-library", extra={"title": track["name"], "artist": track.get("artist")})
        if res.get("ok"):
            if core.app_running("Music"):
                _tell("pause", timeout=5)  # one player at a time
            st = res["state"]
            return {"ok": True, "matched": fold(st.get("track")) == fold(track["name"]), "now": _own_now(st)}
        # otherwise fall back to the Music app below
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
    if player_enabled():
        # One player (0004): the playlist plays in Ovenbird, so pause, next and love work.
        extra = {"name": match["name"]}
        if shuffle is not None:
            extra["shuffle"] = "1" if shuffle else "0"
        res = player_command("play-playlist", extra=extra)
        if res.get("ok"):
            if core.app_running("Music"):
                _tell("pause", timeout=5)
            return {"ok": True, "matched": True, "playlist": match["name"], "now": _own_now(res["state"])}
        # otherwise fall back to the Music app below
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
            "artwork": (r.get("artworkUrl100") or "").replace("100x100bb", "600x600bb") or None,
            "id": str(r["trackId"]) if r.get("trackId") else None}


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
    for attempt in range(2):
        time.sleep(2.5)
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


# ---------------------------------------------------------------- Ovenbird player (0003, amended)
#
# Catalog songs AppleScript can't reach play in Ovenbird.app itself, through MusicKit's
# ApplicationMusicPlayer and the narrow "Media & Apple Music" permission. `cos` drives it
# with claude-os://music/... URLs (handled by the app, see app/Sources/ClaudeOS/Player.swift)
# and reads what it's doing from ~/.claude-os/state/player.json.

MEDIA_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Media"


def player_state(max_age=None):
    state = core.load_json(core.home("state", "player.json"), None)
    if state and max_age is not None and time.time() - state.get("ts", 0) > max_age:
        return None
    return state


def player_enabled():
    return bool(core.config()["music"].get("apple_music"))


PLAYER_COMMANDS = ("authorize", "play", "play-library", "play-playlist", "radio", "pause", "resume", "stop",
                   "next", "previous", "shuffle", "love", "unlove")


def player_command(command, catalog_id=None, wait=12, extra=None):
    """Send a command to Ovenbird's player and wait until it answers *this* request.

    Each command carries a request id that the app echoes in player.json, so the app's
    2-second state ticks (or an earlier song) can't be mistaken for the answer; and the
    per-launch nonce (core.app_url), so only something that can read ~/.claude-os can
    drive the player."""
    import uuid
    if command not in PLAYER_COMMANDS:
        return {"ok": False, "error": "unknown player command"}
    if catalog_id is not None and not str(catalog_id).isdigit():
        return {"ok": False, "error": "bad catalog id"}
    starts_playback = command in ("authorize", "play", "play-library", "play-playlist", "radio")
    if not (core.ensure_app() if starts_playback else core.app_running("ClaudeOS")):
        return {"ok": False, "error": "Ovenbird isn't running"}
    rid = uuid.uuid4().hex[:12]
    params = {"rid": rid, "id": catalog_id}
    params.update(extra or {})
    r = core.open_app_url(core.app_url("music/%s" % command, **params), timeout=15)
    if not r.ok:
        return {"ok": False, "error": "couldn't reach Ovenbird: %s" % r.err[:200]}
    playing = lambda s: s.get("status") == "playing"
    done = {"play": playing, "play-library": playing, "play-playlist": playing, "radio": playing,
            "love": lambda s: s.get("loved"),
            "unlove": lambda s: s.get("loved") is False}.get(command)
    deadline = time.time() + wait
    state = None
    while time.time() < deadline:
        time.sleep(0.5)
        state = player_state()
        if state and state.get("rid") == rid and (done is None or done(state) or state.get("error")):
            break
    if not state or state.get("rid") != rid:
        return {"ok": False, "error": "Ovenbird didn't answer in time"}
    if state.get("error"):
        return {"ok": False, "error": state["error"], "state": state}
    if done and not done(state):
        return {"ok": False, "error": "Ovenbird answered but didn't confirm", "state": state}
    return {"ok": True, "state": state}


def play_with_player(item):
    catalog_id = item.get("id") or _id_from_url(item.get("url"))
    if not catalog_id:
        return {"ok": False, "error": "no catalog id for that song"}
    res = player_command("play", catalog_id)
    if not res.get("ok"):
        return res  # nothing changed: Music keeps playing whatever it was playing
    if core.app_running("Music"):
        _tell("pause", timeout=5)  # ours started; now make it the only thing playing
    st = res["state"]
    return {"ok": True, "matched": True, "catalog_id": str(catalog_id), "now": {
        "running": True, "state": "playing", "track": st.get("track"), "artist": st.get("artist"),
        "album": st.get("album"), "duration": st.get("duration", 0), "position": st.get("position", 0),
        "player": "Ovenbird"}}


def radio(query=None, mine=False):
    """A song, then similar music (decision 0005): Apple Music's station for it, played in
    Ovenbird's player. Seeded from the catalog: the best pick for `query`, the song playing
    now, or with `mine` the song station_seed picks from what you've been playing."""
    if not player_enabled():
        return {"ok": False, "error": "radio plays in Ovenbird's own player: turn on Apple Music in "
                                      "Settings › Permissions (cos music setup)"}
    if mine:
        s = station_seed()
        if not s:
            return {"ok": False, "error": "nothing to start your radio from yet: play a song in Ovenbird a "
                                          "couple of times, or start a radio from one"}
        seed, item = s["catalog_id"], {"name": s["label"]}
    elif query:
        cat = catalog_search(query, limit=8)
        item = best_catalog_pick(cat["results"])
        if not item:
            return {"ok": False, "error": cat["error"] and "catalog search failed: %s" % cat["error"]
                    or "nothing in the catalog for %r" % query}
        seed = item.get("id") or _id_from_url(item.get("url"))
    else:
        own = own_player_active()
        if not own:
            return {"ok": False, "error": "nothing is playing in Ovenbird to start a radio from: "
                                          "say what to start with (cos music radio \"<song> <artist>\")"}
        seed = own.get("id")
        item = {"name": own.get("track"), "artist": own.get("artist")}
    if not seed or not str(seed).isdigit():
        return {"ok": False, "error": "%s is a library song without a catalog id, so it has no station: "
                                      "name a song (cos music radio \"<song> <artist>\")" % (item.get("name") or "that")}
    res = player_command("radio", catalog_id=str(seed), wait=15)
    if not res.get("ok"):
        return res
    if core.app_running("Music"):
        _tell("pause", timeout=5)  # one player at a time
    st = res["state"]
    return {"ok": True, "matched": True, "source": "radio", "chosen": item, "station": st.get("station"),
            "note": st.get("note"), "catalog_id": str(seed), "now": _own_now(st)}


MUSIC_EVENTS = ("play", "radio", "like", "unlike")


def journal_event(event, msg, catalog_id=None, label=None, **data):
    """A music journal entry with what station_seed reads: `event` and the song's Apple Music
    catalog id. Only music code writes those fields (`cos log add` writes a message and a
    kind, nothing else), so nothing a feed or a model says can choose what the Radio chip
    plays (board, 26 Oct 2026)."""
    cid = str(catalog_id) if catalog_id and str(catalog_id).isdigit() else None
    core.journal("music", msg, event=event, catalog_id=cid, label=label if cid else None, **data)


def station_seed(days=7, entries=None):
    """The song the Radio chip on Today starts from: one you started a radio from, or played
    at least twice, in the last `days`. A like counts one more but never qualifies a song on
    its own, and a song you've unliked since is out. Most plays win, then the most recent,
    and not the last radio's own song when there's another. Read only from `event` and
    `catalog_id`, never a message. -> {"catalog_id", "label"} or None."""
    entries = core.read_journal(days=days, kind="music") if entries is None else entries
    plays, radios, loved, last, label, last_radio = {}, set(), {}, {}, {}, None
    for i, e in enumerate(entries):  # oldest first
        cid, ev = str(e.get("catalog_id") or ""), e.get("event")
        if not cid.isdigit() or ev not in MUSIC_EVENTS:
            continue
        last[cid] = i
        if e.get("label"):
            label[cid] = str(e["label"])
        if ev in ("play", "radio"):
            plays[cid] = plays.get(cid, 0) + 1
        if ev == "radio":
            radios.add(cid)
            last_radio = cid
        if ev in ("like", "unlike"):
            loved[cid] = ev == "like"
    ok = [c for c in plays if (c in radios or plays[c] >= 2) and loved.get(c) is not False]
    ranked = sorted(ok, key=lambda c: (plays[c] + (1 if loved.get(c) else 0), last[c]), reverse=True)
    if len(ranked) > 1 and ranked[0] == last_radio:
        ranked = ranked[1:] + ranked[:1]
    return {"catalog_id": ranked[0], "label": label.get(ranked[0]) or "a song you played"} if ranked else None


def _id_from_url(url):
    m = re.search(r"[?&]i=(\d+)", url or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- shortcut route

SHORTCUT = "Ovenbird Play"
SETUP_STEPS = """\
Catalog playback through Shortcuts (one-time, no new permissions):

  1. Open the Shortcuts app and make a new shortcut named exactly:  %s
  2. Add "Get Text from Input" (the input arrives as a file).
  3. Add Music's "Play" action and set its music item to the Text from step 2.
  4. Save. Then try:  cos music play "weightless marconi union" --source shortcut

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
    """Hand the request to the human's "Ovenbird Play" shortcut, then verify."""
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
    if expect and not (fold(expect) in fold(n.get("track")) or fold(n.get("track")) in fold(expect)):
        return {"ok": False, "error": "the shortcut ran, but Music is playing %s, not %s" % (n.get("track"), expect)}
    return {"ok": True, "now": n, "matched": True}


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
    if source in ("auto", "catalog") and player_enabled():
        cat = catalog_search(query, limit=8)
        if cat["results"]:
            item = cat["results"][min(pick, len(cat["results"]) - 1)] if pick else best_catalog_pick(cat["results"])
            res = play_with_player(item)
            res.update(source="claude-os", chosen=item)
            if res.get("ok") or source == "catalog":
                return res
            tried.append("claude-os player: %s" % res.get("error"))
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
        journal_event("play", "played %s — %s" % (name, artist), catalog_id=res.get("catalog_id"),
                      label="%s — %s" % (name, artist), query=query, source=res.get("source"),
                      track=name, artist=artist, playlist=res.get("playlist"))
        return 0
    print("✗ %s" % res.get("error"))
    if res.get("opened"):
        core.journal("music", "opened %s — %s" % (chosen.get("name"), chosen.get("artist")), query=query,
                     source="catalog", track=chosen.get("name"), artist=chosen.get("artist"), opened_only=True)
    return 1


def own_player_active():
    """Ovenbird's player has a song, playing or paused: transport goes there, not to Music.
    While it plays, the app rewrites player.json every 2 seconds; paused, it goes quiet, so a
    paused song counts for as long as the app that paused it is running: written since this
    launch (each launch rewrites app.nonce), not left over from one before."""
    own = player_state()
    if not own or not own.get("track"):
        return None
    if own.get("status") == "playing":
        return own if time.time() - own.get("ts", 0) <= 30 else None
    if own.get("status") == "paused" and core.app_running("ClaudeOS"):
        launch = core.home("state", "app.nonce")
        return own if not launch.exists() or own.get("ts", 0) >= launch.stat().st_mtime else None
    return None


def transport(cmd):
    own = own_player_active()
    if own:
        if cmd == "toggle":
            cmd = "pause" if own["status"] == "playing" else "resume"
        asked = cmd
        if cmd == "next" and not (own.get("playlist") or own.get("station")):
            cmd = "stop"  # a single song has nothing after it
        res = player_command({"prev": "previous"}.get(cmd, cmd), wait=4)
        if not res.get("ok"):
            print("✗ %s" % res.get("error"))
            return 1
        st = res["state"]
        if cmd in ("next", "prev") and st.get("track"):
            print("▶ %s — %s (Ovenbird player)" % (st["track"], st.get("artist") or ""))
        elif asked == "next":
            print("stopped (nothing was queued after it in Ovenbird)")
        else:
            print("%s (Ovenbird player)" % cmd)
        return 0
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
    # Love what's actually playing: Ovenbird's own player first, the Music app otherwise.
    own = own_player_active()
    if own:
        res = player_command("love", wait=10)
        if not res.get("ok") or not res["state"].get("loved"):
            print("✗ couldn't love it: %s" % (res.get("error") or "Apple Music didn't confirm"))
            return 1
        st = res["state"]  # what the player rated, not what was on a moment ago
        name = "%s — %s" % (st.get("track") or own["track"], st.get("artist") or own.get("artist") or "?")
        journal_event("like", "liked %s" % name, catalog_id=st.get("id") or own.get("id"), label=name,
                      liked=True, track=name, player="Ovenbird")
        print("♥ %s" % name)
        return 0
    if not core.app_running("Music") or now().get("state") not in ("playing", "paused"):
        print("✗ nothing is playing to love")
        return 1
    r = _tell("try\nset favorited of current track to true\non error\nset loved of current track to true\nend try\n"
              "return (name of current track) & \" — \" & (artist of current track)")
    if not r.ok:
        print("✗ couldn't favorite: %s" % r.err[:200])
        return 1
    journal_event("like", "liked %s" % r.out, liked=True, track=r.out)  # a library song: no catalog id
    print("♥ %s" % r.out)
    return 0


def unlike():
    own = own_player_active()
    if not own:
        print("✗ unlike works on what's playing in Ovenbird")
        return 1
    res = player_command("unlove", wait=10)
    if not res.get("ok"):
        print("✗ couldn't unlike it: %s" % res.get("error"))
        return 1
    st = res["state"]
    name = "%s — %s" % (st.get("track") or own["track"], st.get("artist") or own.get("artist") or "?")
    journal_event("unlike", "unliked %s" % name, catalog_id=st.get("id") or own.get("id"), label=name,
                  track=name, player="Ovenbird")
    print("♡ %s" % name)
    return 0


def history(days):
    rows = core.read_journal(days=days, kind="music")
    for e in rows[-40:]:
        print("%s  %s" % (e["ts"][:16].replace("T", " "), e["msg"]))
    if not rows:
        print("No music in the last %d days." % days)
    return 0


def main(args):
    try:
        return _main(args)
    finally:
        _note_asked()


def _main(args):
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
    if c == "radio":
        q = " ".join(args.query)
        res = radio(q or None, mine=args.mine)
        if args.json:
            core.emit(res, True, None)
            return 0 if res.get("ok") else 1
        if not res.get("ok"):
            print("✗ %s" % res.get("error"))
            return 1
        n = res["now"]
        seed = "%s — %s" % (n.get("track") or res["chosen"].get("name"), n.get("artist") or res["chosen"].get("artist") or "?")
        if res.get("station"):
            print("▶ %s, then similar music (%s)" % (seed, res["station"]))
        else:
            print("▶ %s (%s)" % (seed, res.get("note") or "no station; the song plays alone"))
        journal_event("radio", "radio from %s" % seed, catalog_id=res.get("catalog_id"), label=seed,
                      track=seed, station=res.get("station"), query=q or None, mine=args.mine or None)
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
        if own_player_active():
            res = player_command("shuffle", wait=4, extra={"on": "1" if args.state == "on" else "0"})
            print(("shuffle %s (Ovenbird player)" % args.state) if res.get("ok") else "✗ %s" % res.get("error"))
            return 0 if res.get("ok") else 1
        _tell("set shuffle enabled to %s" % ("true" if args.state == "on" else "false"))
        print("shuffle %s" % args.state)
        return 0
    if c == "like":
        return like()
    if c == "unlike":
        return unlike()
    if c == "history":
        return history(args.days)
    if c == "setup":
        st = player_state() or {}
        print("Apple Music in Ovenbird: %s" % ("on" if player_enabled() else "off"))
        print("  Media & Apple Music access: %s" % st.get("authorization", "not asked yet"))
        if st.get("error"):
            print("  last error: %s" % st["error"])
        print("  turn it on in Ovenbird › Settings › Permissions")
        if not os.path.exists(os.path.expanduser("~/.claude-os/ClaudeOS.provisionprofile")):
            print("  one-time developer setup (MusicKit needs it):")
            print("    1. developer.apple.com › Identifiers: App ID %s with the MusicKit service" % "local.claude-os.desktop")
            print("    2. Devices: add this Mac (System Information › Hardware › Provisioning UDID)")
            print("    3. Profiles: macOS App Development for that App ID and this Mac; save it as")
            print("       ~/.claude-os/ClaudeOS.provisionprofile, then: cos app install")
        print()
        print(SETUP_STEPS)
        print("Shortcut: %s" % ("installed ✓" if shortcut_installed() else "not installed"))
        return 0
    core.die("unknown music command %r" % c)
