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
                                                            "track": "Awake", "artist": "Tycho"})
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
        self.assertIn("Awake — Tycho", out.getvalue())

    def _fake_player(self, state, music):
        sent, told = [], []
        orig = music.player_command, music._tell, music.player_enabled, music.playlists, core.app_running
        music.player_command = lambda cmd, **k: sent.append((cmd, k.get("extra"))) or {"ok": True, "state": dict(state)}
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
        sent, told = self._fake_player({"status": "playing", "track": "Awake", "playlist": "Deep Work"}, music)
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
                                                            "track": "Awake", "playlist": "Deep Work"})
        sent, told = self._fake_player({"status": "playing", "track": "Montana", "artist": "Tycho"}, music)
        with redirect_stdout(io.StringIO()) as out:
            music.transport("next")
            music.transport("prev")
        self.assertEqual([c for c, _ in sent], ["next", "previous"])
        self.assertIn("Montana — Tycho", out.getvalue())
        self.assertEqual(told, [], "the Music app must not be touched")

    def test_next_on_a_single_song_stops_it(self):
        import io, time
        from contextlib import redirect_stdout
        from cos import music
        core.save_json(core.home("state", "player.json"), {"ts": time.time(), "status": "playing", "track": "Awake"})
        sent, _ = self._fake_player({"status": "stopped"}, music)
        with redirect_stdout(io.StringIO()):
            music.transport("next")
        self.assertEqual([c for c, _ in sent], ["stop"])

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


if __name__ == "__main__":
    unittest.main()
