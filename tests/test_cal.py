import calendar
import datetime as dt
import unittest
from unittest import mock

from helpers import TempHome

from cos import cal, core, weather


def at(day, hour, minute=0):
    return dt.datetime(2026, 10, day, hour, minute).timestamp()


AGENDA = {"calendar": "connected", "reminders": "connected", "ts": at(25, 8), "events": [
    {"title": "Standup", "start": at(25, 9), "end": at(25, 9, 15), "all_day": False, "calendar": "Work"},
    {"title": "Review", "start": at(25, 14), "end": at(25, 15), "all_day": False, "calendar": "Work"},
    {"title": "Birthday", "start": at(25, 0), "end": at(26, 0), "all_day": True, "calendar": "Home"},
    {"title": "Dentist", "start": at(26, 9), "end": at(26, 10), "all_day": False, "calendar": "Home"},
], "reminders_due": [
    {"title": "Pay rent", "due": at(24, 12), "list": "Home"},
    {"title": "Call Sam", "due": at(25, 18), "list": "Home"},
    {"title": "Later", "due": at(26, 18), "list": "Home"},
]}


class TestAgenda(TempHome):
    def test_not_connected_until_the_app_says_so(self):
        self.assertFalse(cal.connected())
        self.assertFalse(cal.day_view({})["connected"])

    def test_day_view(self):
        v = cal.day_view(AGENDA, now=at(25, 10))
        self.assertEqual([e["title"] for e in v["today"]], ["Standup", "Review", "Birthday"])
        self.assertTrue(v["today"][0]["past"])
        self.assertEqual(v["today"][1]["when"], "14:00–15:00")
        self.assertEqual(v["today"][2]["when"], "all day")
        self.assertEqual([e["title"] for e in v["tomorrow"]], ["Dentist"])
        self.assertEqual([(r["title"], r["overdue"]) for r in v["reminders"]], [("Pay rent", True), ("Call Sam", False)])


class TestWeatherOutlook(unittest.TestCase):
    def hours(self, *spec):
        return [{"time": "%02d:00" % (12 + i), "pp": pp, "code": code} for i, (pp, code) in enumerate(spec)]

    def test_storm_beats_rain(self):
        a = weather.outlook(self.hours((80, 63), (90, 95)), current_code=2)
        self.assertEqual(a, {"level": "warn", "msg": "thunderstorm likely around 13:00"})

    def test_rain_coming_and_rain_easing(self):
        self.assertEqual(weather.outlook(self.hours((10, 2), (75, 61)), current_code=2)["msg"], "rain likely around 13:00 (75%)")
        self.assertEqual(weather.outlook(self.hours((90, 63), (20, 3)), current_code=63)["msg"], "rain easing around 13:00")

    def test_quiet_weather_has_no_alert(self):
        self.assertIsNone(weather.outlook(self.hours((5, 1), (10, 2)), current_code=1))


def utc(hour, minute=0):
    return calendar.timegm((2026, 10, 26, hour, minute, 0))


# What Open-Meteo answers at 02:51 for a place two hours ahead of UTC.
ANSWER = {"utc_offset_seconds": 7200, "current": {"weather_code": 3},
          "hourly": {"time": ["2026-10-26T02:00", "2026-10-26T03:00", "2026-10-26T04:00"],
                     "precipitation_probability": [93, 10, 5], "weather_code": [61, 3, 3]}}
PLACE = {"name": "Somewhere", "lat": 1.0, "lon": 2.0, "source": "city"}


class TestWeatherAsOf(TempHome):
    def test_hours_know_when_they_are(self):
        f = weather.parse_forecast(ANSWER, PLACE)
        self.assertEqual([h["ts"] for h in f["hours"]], [utc(0), utc(1), utc(2)], "02:00 at UTC+2 is 00:00 UTC")
        self.assertIsNone(weather.parse_forecast(dict(ANSWER, utc_offset_seconds=None), PLACE)["hours"][0]["ts"])

    def test_an_hour_that_is_over_no_longer_warns(self):
        f = weather.parse_forecast(ANSWER, PLACE)
        self.assertEqual(f["alert"]["msg"], "rain likely around 02:00 (93%)")
        self.assertIs(weather.as_of(f, now=utc(0, 40)), f, "at 02:40 the 02:00 hour still counts")
        later = weather.as_of(f, now=utc(1, 30))
        self.assertIsNone(later["alert"], "at 03:30 rain at 02:00 is old news")
        self.assertEqual([h["time"] for h in later["hours"]], ["03:00", "04:00"])
        self.assertEqual(f["alert"]["msg"], "rain likely around 02:00 (93%)", "the cached forecast is left alone")

    def test_rain_later_still_warns(self):
        answer = dict(ANSWER, hourly=dict(ANSWER["hourly"], precipitation_probability=[93, 10, 80], weather_code=[61, 3, 63]))
        later = weather.as_of(weather.parse_forecast(answer, PLACE), now=utc(1, 30))
        self.assertEqual(later["alert"]["msg"], "rain likely around 04:00 (80%)")

    def test_a_cache_without_times_stays_as_it_was(self):
        f = {"alert": {"level": "note", "msg": "rain likely around 02:00 (93%)"},
             "hours": [{"time": "02:00", "pp": 93, "code": 61}]}
        self.assertIs(weather.as_of(f, now=utc(12)), f)

    def test_the_cached_forecast_is_as_of_now(self):
        core.config_set("weather", PLACE)
        with mock.patch("time.time", return_value=utc(0, 51)):
            core.cache_put("weather", dict(weather.parse_forecast(ANSWER, PLACE), configured=True))
        with mock.patch("time.time", return_value=utc(1, 15)), mock.patch.object(weather.core, "http_get") as get:
            f = weather.forecast()
        get.assert_not_called()
        self.assertIsNone(f["alert"])
        self.assertNotIn("rain", weather.line(f))


if __name__ == "__main__":
    unittest.main()
