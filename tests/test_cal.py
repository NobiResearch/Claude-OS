import datetime as dt
import unittest

from helpers import TempHome

from cos import cal, weather


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


if __name__ == "__main__":
    unittest.main()
