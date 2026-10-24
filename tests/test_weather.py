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
        core.save_json(core.home("state", "player.json"), {"ts": time.time() - 3600, "status": "playing", "track": "Old"})
        self.assertNotEqual(music.now().get("track"), "Old", "stale player state is ignored")


if __name__ == "__main__":
    unittest.main()
