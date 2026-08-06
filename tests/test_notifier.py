from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.notifier import (
    Article, extract_periods, load_seen, matches, notify_due_reminders,
    parse_api_articles, parse_articles, save_seen, update_schedule,
)


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
            "https://granbluefantasy.com/ja/news/9747/",
            "2026-08-04", "イベント",
        ))

    def test_state_round_trip(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "data" / "seen.json"
            save_seen({"p:2", "p:1"}, path)
            self.assertEqual(load_seen(path), {"p:1", "p:2"})

    def test_extract_japanese_event_period(self):
        article = Article(
            "p:1", "イベント開催", "https://example.test", "2026-12-20", "イベント",
            "開催期間 12月31日(木) 19:00 ～ 1月7日(木) 20:59",
        )
        periods = extract_periods(article)
        self.assertEqual(periods[0][0].isoformat(), "2026-12-31T19:00:00+09:00")
        self.assertEqual(periods[0][1].isoformat(), "2027-01-07T20:59:00+09:00")

    @patch("src.notifier.send_reminder")
    def test_due_reminders_are_sent_once(self, send):
        article = Article(
            "p:1", "イベント開催", "https://example.test", "2026-08-01", "イベント",
            "2026年8月6日(木) 20:00 ～ 2026年8月10日(月) 20:59",
        )
        schedule = {"events": {}}
        update_schedule(schedule, [article])
        now = datetime(2026, 8, 6, 19, 35, tzinfo=ZoneInfo("Asia/Tokyo"))
        self.assertEqual(notify_due_reminders("https://webhook.test", schedule, now), 1)
        self.assertEqual(notify_due_reminders("https://webhook.test", schedule, now), 0)
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
