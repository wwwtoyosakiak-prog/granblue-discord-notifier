from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

NEWS_URL = "https://granbluefantasy.com/ja/news/"
NEWS_API_URL = "https://granbluefantasy.com/rcms-api/1/news"
STATE_PATH = Path("data/seen.json")
DEFAULT_KEYWORDS = ""
HEADERS = {"User-Agent": "granblue-news-discord-notifier/2.0 (+GitHub Actions)"}


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    url: str
    date: str = ""
    category: str = ""


def article_id(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    if query.get("p"):
        return f"p:{query['p'][0]}"
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def parse_articles(html: str, base_url: str = NEWS_URL) -> list[Article]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[Article] = []
    used: set[str] = set()
    for link in soup.select('a[href*="?p="]'):
        href = urljoin(base_url, link.get("href", ""))
        if not parse_qs(urlparse(href).query).get("p"):
            continue
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title or title.upper() in {"READ MORE", "MORE"}:
            continue
        aid = article_id(href)
        if aid in used:
            continue
        container = link.find_parent(["article", "li", "div"])
        text = " ".join(container.get_text(" ", strip=True).split()) if container else title
        date_match = re.search(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", text)
        category = ""
        for name in ("イベント", "ニュース", "アップデート情報", "ブックス", "グッズ"):
            if name in text:
                category = name
                break
        found.append(Article(aid, title, href, date_match.group(0) if date_match else "", category))
        used.add(aid)
    return found


def parse_api_articles(payload: dict) -> list[Article]:
    labels = {
        "event": "イベント", "update": "アップデート情報",
        "news": "ニュース", "goods": "グッズ", "books": "ブックス",
    }
    found: list[Article] = []
    for item in payload.get("list", []):
        topic_id = str(item.get("topics_id", "")).strip()
        title = " ".join(str(item.get("subject", "")).split())
        if not topic_id or not title:
            continue
        slugs = [str(x.get("slug", "")) for x in item.get("categories", [])]
        category = next((labels[x] for x in slugs if x in labels), "")
        found.append(Article(
            id=f"p:{topic_id}", title=title,
            url=f"https://granbluefantasy.com/ja/news/{topic_id}/",
            date=str(item.get("ymd", "")), category=category,
        ))
    return found


def fetch_articles(session=requests) -> list[Article]:
    response = session.get(
        NEWS_API_URL,
        params={"cnt": 20, "pageID": 1, "_lang": "ja"},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    articles = parse_api_articles(response.json())
    if not articles:
        raise RuntimeError("公式NEWSから記事を取得できませんでした（ページ構造が変わった可能性があります）")
    return articles


def keywords() -> list[str]:
    raw = os.getenv("KEYWORDS", "").strip() or DEFAULT_KEYWORDS
    return [word.strip().casefold() for word in raw.split(",") if word.strip()]


def matches(article: Article, words: list[str]) -> bool:
    if not words:
        return True
    target = f"{article.title} {article.category}".casefold()
    return any(word in target for word in words)


def load_seen(path: Path = STATE_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return set(value.get("seen_ids", []))
    except (json.JSONDecodeError, OSError, AttributeError):
        raise RuntimeError(f"既読データ {path} を読み込めません")


def save_seen(ids: set[str], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seen_ids": sorted(ids)[-1000:]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def send_discord(webhook: str, article: Article | None = None, test: bool = False) -> None:
    if test:
        payload = {"content": "✅ グラブル公式NEWS通知のテストに成功しました。"}
    else:
        assert article is not None
        payload = {"embeds": [{
            "title": article.title[:256], "url": article.url,
            "description": " / ".join(x for x in (article.date, article.category) if x) or "グランブルーファンタジー公式NEWS",
            "color": 0x3B82F6,
            "footer": {"text": "グラブル公式NEWS"},
        }]}
    response = requests.post(webhook, json=payload, timeout=30)
    response.raise_for_status()


def main() -> int:
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        print("DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        return 2
    if os.getenv("TEST_NOTIFICATION", "false").lower() == "true":
        send_discord(webhook, test=True)
        print("テスト通知を送信しました")
        return 0

    articles = fetch_articles()
    seen = load_seen()
    current = {article.id for article in articles}
    if not seen:
        save_seen(current)
        print(f"初回実行: {len(current)}件を既読として登録しました（通知なし）")
        return 0

    candidates = [a for a in reversed(articles) if a.id not in seen and matches(a, keywords())]
    for article in candidates:
        send_discord(webhook, article)
        print(f"通知: {article.title}")
    # キーワード非該当も既読にし、後から設定変更した際の大量通知を防ぐ。
    save_seen(seen | current)
    print(f"新着 {len(current - seen)}件、通知 {len(candidates)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
