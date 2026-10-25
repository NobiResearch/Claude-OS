import unittest

from helpers import TempHome

from cos import core, weather

FORECAST = {
    "current": {"temperature_2m": 12.6, "apparent_temperature": 10.1, "weather_code": 2, "wind_speed_10m": 14.0},
    "daily": {"weather_code": [61, 0], "temperature_2m_max": [14.2, 16.0], "temperature_2m_min": [6.4, 7.0],
              "precipitation_probability_max": [70, 5]},
}


class TestWeather(TempHome):
    def test_off_until_a_place_is_chosen(self):
        self.assertIsNone(weather.location())
        self.assertEqual(weather.forecast(), {"configured": False})
        self.assertIn("off", weather.line({"configured": False}))

    def test_device_location_is_rounded_and_private(self):
        weather.set_coords(48.856613, 2.352222)
        place = weather.location()
        self.assertEqual((place["lat"], place["lon"], place["source"]), (48.86, 2.35, "device"))
        self.assertNotIn("48.86", "".join(str(e) for e in core.read_journal()), "coordinates never go in the journal")
        with self.assertRaises(ValueError):
            weather.set_coords(123, 0)

    def test_coordinates_become_guard_terms(self):
        weather.set_coords(48.856613, 2.352222)
        self.assertEqual(core.load_json(core.home("guard.json"))["extra"], ["48.86", "2.35"])

    def test_city_names_become_guard_terms(self):
        weather._guard_term("Springfield, Somewhere")
        weather._guard_term("Springfield, Somewhere")
        self.assertEqual(core.load_json(core.home("guard.json"))["extra"], ["Springfield"])

    def test_parse_and_line(self):
        f = weather.parse_forecast(FORECAST, {"name": "Testville", "source": "city"})
        f["configured"] = True
        self.assertEqual(f["now"]["summary"], "Partly cloudy")
        self.assertEqual(f["today"]["summary"], "Light rain")
        self.assertEqual(f["tomorrow"]["precip_pct"], 5)
        self.assertEqual(weather.line(f), "⛅︎ 13° Partly cloudy · today 14°/6°, 70% rain  (Testville)")

    def test_clear(self):
        weather.set_coords(1, 2)
        weather.clear()
        self.assertIsNone(weather.location())


class TestClaudeOSPlayer(TempHome):
    def test_off_by_default_and_rejects_bad_commands(self):
        from cos import music
        self.assertFalse(music.player_enabled())
        self.assertFalse(music.player_command("keystroke")["ok"])
        self.assertFalse(music.player_command("play", catalog_id="1; rm -rf ~")["ok"])

    def test_failed_player_leaves_music_alone(self):
        from cos import music
        calls = []
        orig_cmd, orig_tell = music.player_command, music._tell
        music.player_command = lambda *a, **k: {"ok": False, "error": "token"}
        music._tell = lambda body, timeout=10: calls.append(body)
        try:
            res = music.play_with_player({"id": "123", "url": ""})
        finally:
            music.player_command, music._tell = orig_cmd, orig_tell
        self.assertFalse(res["ok"])
        self.assertEqual(calls, [], "Music must not be paused when our player didn't start")

    def test_like_loves_the_song_in_our_player_not_musics(self):
        import io, time
        from contextlib import redirect_stdout
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Paper Lanterns", "artist": "The Quiet Hours"})
        sent, told = [], []
        orig_cmd, orig_tell = music.player_command, music._tell
        music.player_command = lambda cmd, **k: sent.append(cmd) or {"ok": True, "state": {"loved": True}}
        music._tell = lambda body, timeout=10: told.append(body)
        try:
            with redirect_stdout(io.StringIO()) as out:
                rc = music.like()
        finally:
            music.player_command, music._tell = orig_cmd, orig_tell
        self.assertEqual((rc, sent, told), (0, ["love"], []), "the Music app must not be touched")
        self.assertIn("Paper Lanterns — The Quiet Hours", out.getvalue())

    def _fake_player(self, state, music):
        sent, told = [], []
        orig = music.player_command, music._tell, music.player_enabled, music.playlists, core.app_running
        music.player_command = lambda cmd, **k: sent.append((cmd, k.get("extra") or k.get("catalog_id"))) or {"ok": True, "state": dict(state)}
        music._tell = lambda body, timeout=10: told.append(body)
        music.player_enabled = lambda: True
        music.playlists = lambda: [{"name": "Deep Work", "tracks": 12}, {"name": "Rock", "tracks": 3}]
        core.app_running = lambda name: False

        def restore():
            music.player_command, music._tell, music.player_enabled, music.playlists, core.app_running = orig
        self.addCleanup(restore)
        return sent, told

    def test_playlists_play_in_our_player(self):
        from cos import music
        sent, told = self._fake_player({"status": "playing", "track": "Paper Lanterns", "playlist": "Deep Work"}, music)
        res = music.play_playlist("deep work", shuffle=True)
        self.assertTrue(res["ok"])
        self.assertEqual(sent, [("play-playlist", {"name": "Deep Work", "shuffle": "1"})])
        self.assertEqual((res["now"]["player"], res["now"]["playlist"], told), ("Claude OS", "Deep Work", []))

    def test_playlist_falls_back_to_music_when_our_player_fails(self):
        from cos import music
        sent, told = self._fake_player({}, music)
        music.player_command = lambda cmd, **k: {"ok": False, "error": "no playlist called Rock in the library"}
        music._tell = lambda body, timeout=10: told.append(body) or core.Result(0, "", "")
        orig_confirm = music._confirm
        music._confirm = lambda name: {"ok": True}
        self.addCleanup(setattr, music, "_confirm", orig_confirm)
        self.assertTrue(music.play_playlist("rock")["ok"])
        self.assertIn('play user playlist "Rock"', told[-1])

    def test_next_and_shuffle_go_to_our_player(self):
        import io, time
        from contextlib import redirect_stdout
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Paper Lanterns", "playlist": "Deep Work"})
        sent, told = self._fake_player({"status": "playing", "track": "Glass Harbor", "artist": "The Quiet Hours"}, music)
        with redirect_stdout(io.StringIO()) as out:
            music.transport("next")
            music.transport("prev")
        self.assertEqual([c for c, _ in sent], ["next", "previous"])
        self.assertIn("Glass Harbor — The Quiet Hours", out.getvalue())
        self.assertEqual(told, [], "the Music app must not be touched")

    def test_next_on_a_single_song_stops_it(self):
        import io, time
        from contextlib import redirect_stdout
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing", "track": "Paper Lanterns"})
        sent, _ = self._fake_player({"status": "stopped"}, music)
        with redirect_stdout(io.StringIO()):
            music.transport("next")
        self.assertEqual([c for c, _ in sent], ["stop"])

    def test_radio_starts_from_the_best_catalog_pick(self):
        from cos import music
        sent, told = self._fake_player({"status": "playing", "track": "Paper Lanterns", "station": "Paper Lanterns Station",
                                        "radio": "Paper Lanterns — The Quiet Hours"}, music)
        orig = music.catalog_search
        music.catalog_search = lambda q, limit=10: {"error": None, "results": [
            {"name": "Paper Lanterns", "artist": "The Quiet Hours", "id": "1234", "url": "", "track_number": 1}]}
        self.addCleanup(setattr, music, "catalog_search", orig)
        res = music.radio("something calm")
        self.assertTrue(res["ok"])
        self.assertEqual(sent, [("radio", "1234")])
        self.assertEqual((res["station"], res["now"]["station"], told), ("Paper Lanterns Station",) * 2 + ([],))

    def test_radio_from_what_plays_needs_a_catalog_song(self):
        import time
        from cos import music
        sent, _ = self._fake_player({"status": "playing"}, music)
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Paper Lanterns", "id": "i.LibraryOnly1"})
        res = music.radio()
        self.assertFalse(res["ok"])
        self.assertIn("no station", res["error"])
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Paper Lanterns", "id": "1234"})
        self.assertTrue(music.radio()["ok"])
        self.assertEqual([c for c, _ in sent], ["radio"], "only the catalog song starts a radio")

    def test_radio_needs_our_player(self):
        from cos import music
        self._fake_player({}, music)
        music.player_enabled = lambda: False
        self.assertIn("Apple Music", music.radio("anything")["error"])

    def test_next_on_a_station_skips_instead_of_stopping(self):
        import io, time
        from contextlib import redirect_stdout
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Paper Lanterns", "station": "Paper Lanterns Station"})
        sent, _ = self._fake_player({"status": "playing", "track": "Glass Harbor", "artist": "The Quiet Hours"}, music)
        with redirect_stdout(io.StringIO()):
            music.transport("next")
        self.assertEqual([c for c, _ in sent], ["next"])

    def test_like_journals_the_song_the_player_rated(self):
        import io, time
        from contextlib import redirect_stdout
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Paper Lanterns", "station": "Paper Lanterns Station"})
        self._fake_player({"loved": True, "track": "Glass Harbor", "artist": "The Quiet Hours"}, music)
        with redirect_stdout(io.StringIO()):
            music.like()
        self.assertIn("Glass Harbor", core.read_journal(days=1, kind="music")[-1]["msg"])

    def test_catalog_id_from_song_links(self):
        from cos import music
        self.assertEqual(music._id_from_url("https://music.apple.com/us/album/x/123?i=456"), "456")
        self.assertIsNone(music._id_from_url("https://music.apple.com/us/album/x/123"))

    def test_now_reports_our_player_while_it_plays(self):
        import time
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing",
                                                            "track": "Weightless", "artist": "Marconi Union"})
        n = music.now()
        self.assertEqual((n["track"], n["player"]), ("Weightless", "Claude OS"))
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as out:
            music.render_now(n)
        self.assertIn("in Claude OS", out.getvalue())
        core.save_json(core.home("state", "player.json"), {"ts": time.time() - 3600, "status": "playing", "track": "Old"})
        self.assertNotEqual(music.now().get("track"), "Old", "stale player state is ignored")

    def test_a_paused_song_stays_on_screen(self):
        # Paused, the app stops rewriting player.json; the song is still the one it holds.
        import time
        from unittest import mock
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time() - 600, "status": "paused",
                                                            "track": "A Moment Apart", "artist": "ODESZA"})
        music_app = {"running": True, "state": "paused", "track": "You Get What You Give", "artist": "New Radicals"}
        with mock.patch.object(music.core, "app_running", lambda name: name == "ClaudeOS"), \
                mock.patch.object(music, "_music_app_now", lambda: dict(music_app)):
            n = music.now()
            self.assertEqual((n["track"], n["state"], n["player"]), ("A Moment Apart", "paused", "Claude OS"))
            self.assertEqual(music.own_player_active()["track"], "A Moment Apart", "play resumes it, not Music")
        with mock.patch.object(music.core, "app_running", lambda name: name == "ClaudeOS"), \
                mock.patch.object(music, "_music_app_now", lambda: dict(music_app, state="playing")):
            self.assertEqual(music.now()["track"], "You Get What You Give", "unless Music is playing something else")
        with mock.patch.object(music.core, "app_running", lambda name: False), \
                mock.patch.object(music, "_music_app_now", lambda: {"running": False}):
            self.assertEqual(music.now(), {"running": False}, "the app that held it is gone")
            self.assertIsNone(music.own_player_active())


if __name__ == "__main__":
    unittest.main()
