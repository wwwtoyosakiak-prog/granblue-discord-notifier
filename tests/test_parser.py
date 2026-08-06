from src.notifier import NewsItem, extract_items, matches_filters


def test_extract_items():
    html = """
    <ul>
      <li><a href="/ja/news/9999/"><span>2026.08.06</span><span>イベント</span><h3>イベント「テスト島」開催のお知らせ</h3></a></li>
      <li><a href="/ja/news/category/">カテゴリ</a></li>
    </ul>
    """
    items = extract_items(html)
    assert len(items) == 1
    assert items[0].url == "https://granbluefantasy.com/ja/news/9999/"
    assert "テスト島" in items[0].title


def test_keyword_filter():
    assert matches_filters(NewsItem("古戦場開催のお知らせ", "https://granbluefantasy.com/ja/news/1/"))
