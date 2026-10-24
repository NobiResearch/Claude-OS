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
