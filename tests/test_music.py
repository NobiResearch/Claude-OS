import unittest

import helpers  # noqa: F401  (puts lib/ on sys.path)

from cos import music

API_ROW = {
    "trackName": "Weightless", "artistName": "Marconi Union", "collectionName": "Weightless",
    "primaryGenreName": "Ambient", "releaseDate": "2011-01-01T08:00:00Z", "trackNumber": 1,
    "trackCount": 1, "trackTimeMillis": 480000,
    "trackViewUrl": "https://music.apple.com/no/album/weightless/1?i=2&uo=4",
}


class TestMusic(unittest.TestCase):
    def test_parse_catalog_item_strips_tracking(self):
        item = music.parse_catalog_item(API_ROW)
        self.assertEqual(item["url"], "https://music.apple.com/no/album/weightless/1?i=2")
        self.assertEqual(item["year"], "2011")
        self.assertEqual(item["duration"], 480.0)

    def test_best_pick_prefers_single_of_same_song(self):
        compilation = dict(music.parse_catalog_item(API_ROW), track_number=7, album="Ambient Hits")
        single = music.parse_catalog_item(API_ROW)
        other = dict(single, name="Something Else", track_number=1)
        self.assertIs(music.best_catalog_pick([compilation, other, single]), single)
        self.assertIs(music.best_catalog_pick([other]), other)
        self.assertIsNone(music.best_catalog_pick([]))

    def test_fold(self):
        self.assertEqual(music.fold("Café  del Mar!"), "cafe del mar")
        self.assertEqual(music.fold(None), "")

    def test_records(self):
        text = "a" + music.US + "b" + music.RS + "c" + music.US + "d" + music.RS
        self.assertEqual(music._records(text), [["a", "b"], ["c", "d"]])

    def test_volume_zero_pauses_instead(self):
        calls = []
        original = music._tell
        music._tell = lambda body, timeout=10: calls.append(body)
        try:
            music.volume(0)
        finally:
            music._tell = original
        self.assertEqual(calls, ["pause"])


if __name__ == "__main__":
    unittest.main()


class TestStationSeed(helpers.TempHome):
    """Today's Radio chip (the board, 26 Oct 2026): picked mechanically from the fields music
    code writes, never from a message, so nothing a feed or a model says can choose it."""

    def e(self, event, cid, label=None):
        return {"kind": "music", "msg": "x", "event": event, "catalog_id": cid, "label": label or "Song %s — Artist" % cid}

    def test_a_radio_seed_or_two_plays_qualify_and_a_like_only_counts_one_more(self):
        S = music.station_seed
        self.assertIsNone(S(entries=[]))
        self.assertIsNone(S(entries=[self.e("play", "11")]), "one play isn't enough")
        self.assertIsNone(S(entries=[self.e("like", "11"), self.e("like", "11")]), "likes alone never qualify")
        self.assertEqual(S(entries=[self.e("radio", "11")])["catalog_id"], "11")
        self.assertEqual(S(entries=[self.e("play", "11"), self.e("play", "11")])["label"], "Song 11 — Artist")
        two = [self.e("play", "11"), self.e("play", "11"), self.e("play", "22"), self.e("play", "22"), self.e("like", "22")]
        self.assertEqual(S(entries=two)["catalog_id"], "22", "a like counts one more")

    def test_unliked_songs_are_out_and_the_last_radio_makes_way(self):
        S = music.station_seed
        unliked = [self.e("play", "11"), self.e("play", "11"), self.e("like", "11"), self.e("unlike", "11")]
        self.assertIsNone(S(entries=unliked))
        self.assertEqual(S(entries=unliked + [self.e("like", "11")])["catalog_id"], "11", "liked again counts again")
        varied = [self.e("play", "22"), self.e("play", "22"), self.e("play", "11"), self.e("play", "11"), self.e("radio", "11")]
        self.assertEqual(S(entries=varied)["catalog_id"], "22", "not the song the last radio came from")
        self.assertEqual(S(entries=[self.e("radio", "11")])["catalog_id"], "11", "unless it's the only one")

    def test_only_what_music_code_wrote_counts(self):
        from cos import cli, core
        for argv in (["log", "add", "--kind", "music", "radio from Planted — Feed"],
                     ["log", "add", "--kind", "music", "liked", "Planted", "catalog_id=123"]):
            cli.main(argv)
        self.assertIsNone(music.station_seed(), "`cos log add` can't write event or catalog_id")
        core.journal("music", "radio from x", event="radio", catalog_id="12a3")
        core.journal("music", "radio from x", event="seed", catalog_id="123")
        self.assertIsNone(music.station_seed(), "only a numeric id and a known event")
        music.journal_event("radio", "radio from Song — Artist", catalog_id="456", label="Song — Artist")
        self.assertEqual(music.station_seed(), {"catalog_id": "456", "label": "Song — Artist"})

    def test_older_than_a_week_is_out(self):
        import json
        from cos import core
        music.journal_event("radio", "radio from Old — Artist", catalog_id="789", label="Old — Artist")
        path = next(core.home("journal").glob("*.jsonl"))
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        rows[-1]["ts"] = "2020-01-01T00:00:00+00:00"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.assertIsNone(music.station_seed(days=7))

    def test_a_background_job_can_never_start_it(self):
        from cos import cli
        args = cli.build_parser().parse_args(["music", "radio", "--mine"])
        self.assertTrue(args.mine)
        self.assertEqual(cli.daemon_refused(args), ("music", "radio"))

    def test_with_the_player_off_there_is_no_radio(self):
        from unittest import mock
        with mock.patch.object(music, "player_enabled", return_value=False):
            self.assertFalse(music.radio(mine=True)["ok"])
        with mock.patch.object(music, "player_enabled", return_value=True), \
                mock.patch.object(music, "player_command") as player:
            res = music.radio(mine=True)
        self.assertFalse(res["ok"])
        self.assertIn("nothing to start your radio from", res["error"])
        player.assert_not_called()


class TestMusicOnlyAfterYouAsk(helpers.TempHome):
    """Fable's F3 (29 October): the first AppleScript to Music makes macOS ask whether Ovenbird
    may control it. A session starting (the boot banner) or the status line must never be what
    asks; a person's `cos music` is."""

    NOW = music.US.join(["playing", "Weightless", "Marconi Union", "Weightless", "480", "12", "40", "false", "off"])

    def setUp(self):
        super().setUp()
        music._talked = False
        self.addCleanup(setattr, music, "_talked", False)

    def args(self, cmd="now"):
        import types
        return types.SimpleNamespace(music_cmd=cmd, json=True)

    def test_the_banner_and_the_status_line_never_ask_first(self):
        import io
        import sys
        from contextlib import redirect_stdout
        from unittest import mock
        from cos import core, shell
        asked = mock.Mock(side_effect=AssertionError("asked Music before anyone asked for music"))
        # Where git keeps it: in a worktree, .git is a file and FETCH_HEAD is elsewhere.
        fetch_head = core.ROOT / core.run(["git", "-C", str(core.ROOT), "rev-parse", "--git-path", "FETCH_HEAD"]).out.strip()
        before = fetch_head.stat().st_mtime if fetch_head.exists() else None
        # The banner's catch-up line fetches from GitHub: never from a test.
        with mock.patch.object(shell, "_catch_up_line", return_value=None), \
                mock.patch.object(core, "app_running", return_value=True), mock.patch.object(core, "osascript", asked), \
                mock.patch.object(sys, "stdin", io.StringIO("{}")), redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(shell._music_now())
            shell.statusline()
            shell.boot()
        asked.assert_not_called()
        self.assertEqual(fetch_head.stat().st_mtime if fetch_head.exists() else None, before, "no git fetch")
        self.assertNotIn("music:", out.getvalue())

    def test_an_odd_state_means_no_music_line_never_a_broken_banner(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        from cos import core, shell
        state = core.home("state", "player.json")
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text('["x"]')
        never = mock.Mock(side_effect=AssertionError("asked Music"))
        with mock.patch.object(shell, "_catch_up_line", return_value=None), mock.patch.object(core, "osascript", never):
            self.assertIsNone(shell._music_now())
            with mock.patch.object(music, "asked", side_effect=RuntimeError("odd")):
                self.assertIsNone(shell._music_now())
                with redirect_stdout(io.StringIO()) as out:
                    shell.boot()
            # After the marker too: the odd state file costs the music line, not the banner.
            with mock.patch.object(music, "asked", return_value=True), \
                    mock.patch.object(core, "app_running", return_value=True):
                self.assertIsNone(shell._music_now())
        never.assert_not_called()  # _music_now swallows errors, so check it never got that far
        self.assertIn("Ovenbird", out.getvalue())
        self.assertNotIn("music:", out.getvalue())

    def test_ovenbird_s_own_player_shows_without_asking(self):
        import json
        import time
        from unittest import mock
        from cos import core, shell
        state = core.home("state", "player.json")
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"status": "playing", "track": "Dayvan Cowboy", "artist": "Boards of Canada",
                                     "ts": time.time()}))
        asked = mock.Mock(side_effect=AssertionError("asked Music"))
        with mock.patch.object(core, "osascript", asked):
            n = shell._music_now()
        self.assertEqual((n["track"], n["player"]), ("Dayvan Cowboy", "Ovenbird"))

    def test_a_person_s_cos_music_that_music_answers_unlocks_it(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        from cos import core, shell
        answered = core.Result(0, self.NOW, "")
        with mock.patch.object(core, "app_running", return_value=True), \
                mock.patch.object(core, "osascript", return_value=answered) as osa, redirect_stdout(io.StringIO()):
            self.assertEqual(music.main(self.args()), 0)
            self.assertTrue(music.asked())
            osa.reset_mock()
            self.assertEqual(shell._music_now()["track"], "Weightless")
        osa.assert_called()

    def test_not_from_a_background_run_or_when_music_didn_t_answer(self):
        import io
        import os
        from contextlib import redirect_stdout
        from unittest import mock
        from cos import core
        with mock.patch.object(core, "app_running", return_value=True), redirect_stdout(io.StringIO()):
            with mock.patch.object(core, "osascript", return_value=core.Result(1, "", "not allowed")):
                music.main(self.args())
            self.assertFalse(music.asked(), "Music didn't answer")
            with mock.patch.object(core, "osascript", return_value=core.Result(0, self.NOW, "")), \
                    mock.patch.dict(os.environ, {"CLAUDE_OS_DAEMON": "pulse"}):
                music.main(self.args())
            self.assertFalse(music.asked(), "a background run")
