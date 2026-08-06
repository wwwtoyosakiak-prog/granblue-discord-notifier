from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.notifier import Article, load_seen, matches, parse_api_articles, parse_articles, save_seen


HTML = """
<ul><li><time>2026-08-01</time><span>イベント</span>
<a href="/pages/?p=123">イベント「蒼海を征く者」開催のお知らせ</a></li>
<li><a href="https://granbluefantasy.jp/pages/?p=124">メンテナンスのお知らせ</a></li></ul>
"""


class NotifierTests(unittest.TestCase):
    def test_parse_articles(self):
        items = parse_articles(HTML)
        self.assertEqual([(x.id, x.title) for x in items], [
            ("p:123", "イベント「蒼海を征く者」開催のお知らせ"),
            ("p:124", "メンテナンスのお知らせ"),
        ])
        self.assertEqual(items[0].date, "2026-08-01")

    def test_keyword_filter(self):
        item = Article("p:1", "コラボイベント開催", "https://example.test")
        self.assertTrue(matches(item, ["イベント"]))
        self.assertFalse(matches(item, ["古戦場"]))
        self.assertTrue(matches(item, []))

    def test_parse_official_api(self):
        items = parse_api_articles({"list": [{
            "topics_id": 9747, "ymd": "2026-08-04",
            "subject": "イベント開催のお知らせ",
            "categories": [{"slug": "event"}],
        }]})
        self.assertEqual(items[0], Article(
            "p:9747", "イベント開催のお知らせ",
            "https://granbluefantasy.com/ja/news/p9747/",
            "2026-08-04", "イベント",
        ))

    def test_state_round_trip(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "data" / "seen.json"
            save_seen({"p:2", "p:1"}, path)
            self.assertEqual(load_seen(path), {"p:1", "p:2"})


if __name__ == "__main__":
    unittest.main()
