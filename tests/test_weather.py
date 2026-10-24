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


class TestMusicHelperGuards(TempHome):
    def test_helper_refuses_unknown_commands_and_daemons(self):
        import os
        from cos import music
        self.assertFalse(music.helper("keystroke").get("ok"))
        os.environ["CLAUDE_OS_DAEMON"] = "evolve"
        try:
            self.assertIn("background", music.helper("press-play")["error"])
        finally:
            del os.environ["CLAUDE_OS_DAEMON"]

    def test_full_control_is_off_by_default(self):
        from cos import music
        self.assertFalse(music.full_control())


if __name__ == "__main__":
    unittest.main()
