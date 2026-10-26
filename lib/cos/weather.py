"""cos weather — the forecast for a place the human chose (Open-Meteo, no API key).

Off until the human sets a city or turns on "Use my location" in the app (decision
0003). Coordinates are rounded to ~1 km and live only in ~/.claude-os/config.json; the
place name is added to the Guardian's private terms so it can never be committed.
"""

import calendar
import json
import time
import urllib.parse

from . import core

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search?"
FORECAST = "https://api.open-meteo.com/v1/forecast?"
CACHE_SECONDS = 30 * 60

# WMO weather interpretation codes → (description, symbol)
WMO = {
    0: ("Clear", "☀︎"), 1: ("Mostly clear", "🌤"), 2: ("Partly cloudy", "⛅︎"), 3: ("Overcast", "☁︎"),
    45: ("Fog", "🌫"), 48: ("Icy fog", "🌫"),
    51: ("Light drizzle", "🌦"), 53: ("Drizzle", "🌦"), 55: ("Heavy drizzle", "🌧"),
    56: ("Freezing drizzle", "🌧"), 57: ("Freezing drizzle", "🌧"),
    61: ("Light rain", "🌦"), 63: ("Rain", "🌧"), 65: ("Heavy rain", "🌧"),
    66: ("Freezing rain", "🌧"), 67: ("Freezing rain", "🌧"),
    71: ("Light snow", "🌨"), 73: ("Snow", "🌨"), 75: ("Heavy snow", "❄︎"), 77: ("Snow grains", "🌨"),
    80: ("Showers", "🌦"), 81: ("Showers", "🌧"), 82: ("Violent showers", "⛈"),
    85: ("Snow showers", "🌨"), 86: ("Snow showers", "🌨"),
    95: ("Thunderstorm", "⛈"), 96: ("Thunderstorm, hail", "⛈"), 99: ("Thunderstorm, hail", "⛈"),
}


def describe(code):
    return WMO.get(int(code) if code is not None else -1, ("Unknown", "·"))


def location():
    w = core.config().get("weather") or {}
    if w.get("lat") is None or w.get("lon") is None:
        return None
    return w


def _guard_term(name, lat=None, lon=None):
    """Make the Guardian refuse commits that mention the human's place or its coordinates."""
    terms = [(name or "").split(",")[0].strip()]
    terms += ["%.2f" % v for v in (lat, lon) if v is not None]
    terms = [t for t in terms if len(t) >= 3]
    if not terms:
        return
    path = core.home("guard.json")
    data = core.load_json(path, {}) or {}
    extra = data.get("extra", [])
    new = [t for t in terms if t not in extra]
    if new:
        data["extra"] = extra + new
        core.save_json(path, data)


def _save(name, lat, lon, source):
    place = {"name": name, "lat": round(float(lat), 2), "lon": round(float(lon), 2), "source": source}
    core.config_set("weather", place)
    _guard_term(name if source == "city" else None, place["lat"], place["lon"])
    core.run(["rm", "-f", str(core.home("cache", "weather.json"))])
    core.journal("action", "weather location updated (%s)" % source)
    return place


def geocode(query, count=5):
    params = urllib.parse.urlencode({"name": query, "count": count, "language": "en", "format": "json"})
    with core.http_get(GEOCODE + params, timeout=10) as resp:
        data = json.load(resp)
    out = []
    for r in data.get("results") or []:
        label = ", ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country")) if x)
        out.append({"name": label, "lat": r.get("latitude"), "lon": r.get("longitude")})
    return out


def set_city(query):
    hits = geocode(query)
    if not hits:
        return None
    best = hits[0]
    return _save(best["name"], best["lat"], best["lon"], "city")


def set_coords(lat, lon):
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("coordinates out of range")
    return _save("Your location", lat, lon, "device")


def clear():
    core.config_set("weather", {})
    core.run(["rm", "-f", str(core.home("cache", "weather.json"))])
    core.journal("action", "weather location cleared")


RAIN = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
SNOW = {71, 73, 75, 77, 85, 86}
STORM = {95, 96, 99}


def outlook(hours, current_code):
    """One alert for the next six hours, or None: storms beat snow beat rain."""
    hours = hours[:6]
    for h in hours:
        if h["code"] in STORM:
            return {"level": "warn", "msg": "thunderstorm likely around %s" % h["time"]}
    for h in hours:
        if h["code"] in SNOW:
            return {"level": "note", "msg": "snow likely around %s" % h["time"]}
    if current_code in RAIN:
        for h in hours:
            if (h["pp"] or 0) < 30 and h["code"] not in RAIN:
                return {"level": "note", "msg": "rain easing around %s" % h["time"]}
        return {"level": "note", "msg": "rain for the next few hours"}
    for h in hours:
        if (h["pp"] or 0) >= 70 or h["code"] in RAIN and (h["pp"] or 0) >= 50:
            return {"level": "note", "msg": "rain likely around %s (%d%%)" % (h["time"], h["pp"] or 0)}
    return None


def as_of(f, now=None):
    """The forecast as of now. A cached one can be hours old, so hours that are over are
    dropped and the alert is worked out again from the rest: it never warns about rain at
    an hour that's already gone. An hour counts until the next one starts, as Open-Meteo's
    own forecast_hours do."""
    hours = f.get("hours") or []
    now = time.time() if now is None else now
    left = [h for h in hours if h.get("ts") is None or h["ts"] + 3600 > now]
    if len(left) == len(hours):
        return f
    return dict(f, hours=left, alert=outlook(left, left[0]["code"] if left else None))


def _epoch(stamp, offset):
    """'2026-10-26T14:00' in the place's time -> seconds since the epoch, or None. On the
    night the clocks change, hours after the change are an hour off; that's all."""
    try:
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M")) - int(offset)
    except (TypeError, ValueError):
        return None


def parse_forecast(data, place):
    cur = data.get("current") or {}
    daily = data.get("daily") or {}

    def day(i):
        try:
            code = daily["weather_code"][i]
            return {"max": daily["temperature_2m_max"][i], "min": daily["temperature_2m_min"][i],
                    "precip_pct": (daily.get("precipitation_probability_max") or [None] * 3)[i],
                    "summary": describe(code)[0], "symbol": describe(code)[1]}
        except (KeyError, IndexError, TypeError):
            return None

    hourly = data.get("hourly") or {}
    offset = data.get("utc_offset_seconds")
    hours = []
    for t, pp, code in zip(hourly.get("time") or [], hourly.get("precipitation_probability") or [],
                           hourly.get("weather_code") or []):
        hours.append({"time": t[-5:], "ts": _epoch(t, offset), "pp": pp, "code": code})
    desc, symbol = describe(cur.get("weather_code"))
    return {"place": place.get("name"), "source": place.get("source"),
            "alert": outlook(hours, cur.get("weather_code")), "hours": hours[:12],
            "now": {"temp": cur.get("temperature_2m"), "feels": cur.get("apparent_temperature"),
                    "wind": cur.get("wind_speed_10m"), "summary": desc, "symbol": symbol},
            "today": day(0), "tomorrow": day(1), "units": "°C, km/h"}


def forecast(force=False):
    place = location()
    if not place:
        return {"configured": False}
    cached = core.cache_get("weather", max_age=CACHE_SECONDS)
    if cached and not force and cached["data"].get("place") == place.get("name"):
        return as_of(cached["data"])
    params = urllib.parse.urlencode({
        "latitude": place["lat"], "longitude": place["lon"], "timezone": "auto", "forecast_days": 2,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "hourly": "precipitation_probability,weather_code", "forecast_hours": 12,
    })
    with core.http_get(FORECAST + params, timeout=10) as resp:
        data = parse_forecast(json.load(resp), place)
    data["configured"] = True
    data["fetched"] = time.time()
    core.cache_put("weather", data)
    return data


def line(f):
    """One human line, e.g. '☀︎ 12° Clear · today 14°/6°, 10% rain'."""
    if not f.get("configured"):
        return "Weather is off. Set a city: cos weather set \"<city>\""
    n, t = f["now"], f.get("today") or {}
    out = "%s %s° %s" % (n["symbol"], _r(n["temp"]), n["summary"])
    if t:
        out += " · today %s°/%s°" % (_r(t["max"]), _r(t["min"]))
        if t.get("precip_pct"):
            out += ", %d%% rain" % t["precip_pct"]
    if f.get("alert"):
        out += " · " + f["alert"]["msg"]
    return out + "  (%s)" % f["place"]


def _r(x):
    return "?" if x is None else "%d" % round(x)


def main(args):
    c = args.weather_cmd
    if c == "set":
        place = set_city(" ".join(args.place))
        if not place:
            core.die("couldn't find %r" % " ".join(args.place))
        print("weather location: %s" % place["name"])
        return 0
    if c == "clear":
        clear()
        print("weather is off")
        return 0
    try:
        f = forecast(force=args.refresh)
    except Exception as e:
        core.die("couldn't fetch the weather: %s" % e)
    core.emit(f, args.json, lambda d: print(line(d)))
    return 0
