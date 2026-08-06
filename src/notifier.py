from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

NEWS_URL = os.getenv("NEWS_URL", "https://granbluefantasy.com/ja/news/")
STATE_PATH = Path(os.getenv("STATE_PATH", "data/state.json"))
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
DEFAULT_KEYWORDS = "イベント,古戦場,決戦！星の古戦場,ドレッドバラージュ,コラボ,キャンペーン,メンテナンス,アップデート,生放送,これからの"
KEYWORDS_RAW = os.getenv("KEYWORDS", "").strip() or DEFAULT_KEYWORDS
KEYWORDS = [x.strip() for x in KEYWORDS_RAW.split(",") if x.strip()]
EXCLUDE_KEYWORDS = [x.strip() for x in os.getenv("EXCLUDE_KEYWORDS", "").split(",") if x.strip()]
NOTIFY_ALL = os.getenv("NOTIFY_ALL", "false").lower() in {"1", "true", "yes"}
SEND_TEST = os.getenv("SEND_TEST", "false").lower() in {"1", "true", "yes"}
MAX_SEEN = int(os.getenv("MAX_SEEN", "500"))
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("granblue-notifier")


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    date: str = ""
    category: str = ""

    @property
    def key(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:20]


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; GranblueDiscordNotifier/1.0; +https://github.com/)",
        "Accept-Language": "ja,en;q=0.8",
    })
    return session


def fetch_html(session: requests.Session, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"公式NEWSの取得に失敗しました: {last_error}")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_news_article(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc not in {"granbluefantasy.com", "www.granbluefantasy.com"}:
        return False
    path = parsed.path.rstrip("/") + "/"
    if not path.startswith("/ja/news/"):
        return False
    blocked = ("/archive/", "/category/")
    if any(part in path for part in blocked):
        return False
    tail = path.removeprefix("/ja/news/").strip("/")
    return bool(tail) and bool(re.fullmatch(r"(?:p)?\d+", tail))


def extract_date(text: str) -> str:
    match = re.search(r"(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})", text)
    if not match:
        return ""
    y, m, d = map(int, match.groups())
    return f"{y:04d}.{m:02d}.{d:02d}"


def extract_items(html: str, base_url: str = NEWS_URL) -> list[NewsItem]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, NewsItem] = {}

    for anchor in soup.find_all("a", href=True):
        url = urljoin(base_url, anchor["href"]).split("#", 1)[0]
        if not is_news_article(url):
            continue

        heading = anchor.find(["h1", "h2", "h3", "h4"])
        anchor_text = clean_text(heading.get_text(" ", strip=True)) if heading else clean_text(anchor.get_text(" ", strip=True))
        container = anchor
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
            text = clean_text(container.get_text(" ", strip=True))
            if len(text) >= max(20, len(anchor_text)):
                break
        else:
            text = anchor_text

        text = clean_text(container.get_text(" ", strip=True)) if container else anchor_text
        date = extract_date(text)

        title = anchor_text
        if not title or title.lower() in {"more", "read more", "詳細"}:
            candidates = []
            if container:
                for tag in container.find_all(["h1", "h2", "h3", "h4", "p", "span"]):
                    candidate = clean_text(tag.get_text(" ", strip=True))
                    if candidate and not extract_date(candidate) and 5 <= len(candidate) <= 180:
                        candidates.append(candidate)
            title = max(candidates, key=len, default="グランブルーファンタジー公式NEWS")

        title = re.sub(r"^20\d{2}[./-]\d{1,2}[./-]\d{1,2}\s*", "", title)
        title = clean_text(title).replace("New!", "").strip()
        if len(title) < 4:
            continue

        category = ""
        for candidate in ("イベント", "アップデート情報", "キャラクター", "メディア", "ニュース"):
            if candidate in text:
                category = candidate
                break

        current = NewsItem(title=title[:240], url=url, date=date, category=category)
        previous = found.get(url)
        if previous is None or len(current.title) > len(previous.title):
            found[url] = current

    return list(found.values())


def matches_filters(item: NewsItem) -> bool:
    target = f"{item.title} {item.category}"
    if EXCLUDE_KEYWORDS and any(word.lower() in target.lower() for word in EXCLUDE_KEYWORDS):
        return False
    if NOTIFY_ALL:
        return True
    return any(word.lower() in target.lower() for word in KEYWORDS)


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen_urls": [], "initialized": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data.get("seen_urls"), list):
            raise ValueError("seen_urls must be a list")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        log.warning("状態ファイルを読み込めないため初期化します: %s", exc)
        return {"seen_urls": [], "initialized": False}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def discord_color(category: str) -> int:
    return {
        "イベント": 0xE67E22,
        "アップデート情報": 0x3498DB,
        "キャラクター": 0x9B59B6,
        "メディア": 0x2ECC71,
    }.get(category, 0x4C86C6)


def send_discord(session: requests.Session, item: NewsItem) -> None:
    if not WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL が設定されていません")

    fields = []
    if item.date:
        fields.append({"name": "掲載日", "value": item.date, "inline": True})
    if item.category:
        fields.append({"name": "カテゴリ", "value": item.category, "inline": True})

    payload = {
        "username": "グラブルイベント通知",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": item.title,
            "url": item.url,
            "description": "グランブルーファンタジー公式サイトに新しい対象NEWSが掲載されました。",
            "color": discord_color(item.category),
            "fields": fields,
            "footer": {"text": "Granblue Fantasy Official News Monitor"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
    response = session.post(WEBHOOK_URL, json=payload, timeout=TIMEOUT)
    if response.status_code not in {200, 204}:
        raise RuntimeError(f"Discord通知に失敗しました: HTTP {response.status_code} {response.text[:300]}")


def send_test(session: requests.Session) -> None:
    item = NewsItem(
        title="✅ グラブルイベント通知のテストに成功しました",
        url=NEWS_URL,
        date=datetime.now().strftime("%Y.%m.%d"),
        category="テスト",
    )
    send_discord(session, item)


def main() -> int:
    session = get_session()
    if SEND_TEST:
        send_test(session)
        log.info("テスト通知を送信しました")
        return 0

    html = fetch_html(session, NEWS_URL)
    items = extract_items(html)
    if not items:
        raise RuntimeError("NEWS記事を1件も検出できませんでした。公式サイトの構造変更の可能性があります。")

    state = load_state(STATE_PATH)
    seen = set(state.get("seen_urls", []))
    current_urls = [item.url for item in items]

    if not state.get("initialized", False):
        state = {
            "seen_urls": current_urls[:MAX_SEEN],
            "initialized": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        save_state(STATE_PATH, state)
        log.info("初回起動: 現在の記事 %d 件を登録しました（通知なし）", len(items))
        return 0

    new_items = [item for item in items if item.url not in seen]
    targets = [item for item in new_items if matches_filters(item)]

    # 古い順に送ることでDiscord上の並びを自然にする
    for item in reversed(targets):
        send_discord(session, item)
        log.info("通知しました: %s", item.title)

    merged = current_urls + [url for url in state.get("seen_urls", []) if url not in current_urls]
    state = {
        "seen_urls": merged[:MAX_SEEN],
        "initialized": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_new_count": len(new_items),
        "last_notified_count": len(targets),
    }
    save_state(STATE_PATH, state)
    log.info("確認完了: 全%d件、新着%d件、通知%d件", len(items), len(new_items), len(targets))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("処理に失敗しました")
        sys.exit(1)
