import unittest

from helpers import TempHome

from cos import feeds

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Example RSS</title>
<item><title>First &amp; best</title><link>https://example.com/1</link>
<guid>id-1</guid><pubDate>Sat, 24 Oct 2026 08:00:00 +0000</pubDate>
<description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description></item>
<item><title>Second</title><link>https://example.com/2</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Example Atom</title>
<entry><title>Atom one</title><id>tag:1</id>
<link rel="alternate" href="https://example.org/a"/><link rel="self" href="https://example.org/self"/>
<updated>2026-10-23T10:00:00.123Z</updated><summary>Short</summary></entry>
</feed>"""

RDF = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>Example RDF</title></channel>
<item><title>RDF item</title><link>https://example.net/x</link><dc:date>2026-10-22T09:00:00+02:00</dc:date></item>
</rdf:RDF>"""


class TestParsing(unittest.TestCase):
    def test_rss(self):
        title, items = feeds.parse_feed(RSS)
        self.assertEqual(title, "Example RSS")
        self.assertEqual(items[0]["title"], "First & best")
        self.assertEqual(items[0]["summary"], "Hello world")
        self.assertEqual(items[0]["id"], "id-1")
        self.assertIsNotNone(items[0]["ts"])
        self.assertIsNone(items[1]["ts"])

    def test_atom_picks_alternate_link_and_fractional_dates(self):
        title, items = feeds.parse_feed(ATOM)
        self.assertEqual(title, "Example Atom")
        self.assertEqual(items[0]["link"], "https://example.org/a")
        self.assertIsNotNone(items[0]["ts"])

    def test_rdf(self):
        title, items = feeds.parse_feed(RDF)
        self.assertEqual(items[0]["link"], "https://example.net/x")
        self.assertIsNotNone(items[0]["ts"])

    def test_compact_timezone_offsets(self):
        self.assertEqual(feeds.parse_date("2026-10-22T09:00:00+0200"), feeds.parse_date("2026-10-22T07:00:00Z"))

    def test_strip_html_truncates_on_word(self):
        out = feeds.strip_html("<p>" + "word " * 100 + "</p>", limit=30)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 30)

    def test_feed_list_parsing(self):
        parsed = feeds.parse_feed_list("# comment\n## Tech\nhttps://a.example/feed  # A\n\nhttps://b.example/rss\n")
        self.assertEqual(parsed, [
            {"url": "https://a.example/feed", "name": "A", "category": "tech"},
            {"url": "https://b.example/rss", "name": None, "category": "tech"},
        ])


class TestReadTracking(TempHome):
    def test_unread_and_mark_read(self):
        store = {"feeds": {"https://x": {"name": "X", "category": "tech", "items": [
            {"id": "1", "title": "old", "ts": 100.0}, {"id": "2", "title": "new", "ts": 200.0}]}}}
        items = feeds.unread(store)
        self.assertEqual([i["title"] for i in items], ["new", "old"])
        feeds.mark_read([items[0]["key"]])
        self.assertEqual([i["title"] for i in feeds.unread(store)], ["old"])
        self.assertEqual(len(feeds.unread(store, include_read=True)), 2)
        self.assertEqual(feeds.unread(store, category="science"), [])

    def test_curated_list_is_valid(self):
        curated = feeds.feed_list()
        self.assertGreater(len(curated), 10)
        self.assertTrue(all(f["url"].startswith("https://") for f in curated))


if __name__ == "__main__":
    unittest.main()
