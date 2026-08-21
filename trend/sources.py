"""Thu thập tín hiệu trend từ các nguồn RSS công khai — không cần API key nào.

Hai loại nguồn:

1. **RSS báo** — mục tâm sự/đời sống/pháp luật của báo Việt. Đây là tín hiệu chính:
   tiêu đề ở những mục này chính là dạng xung đột mà khán giả truyện audio quan tâm
   ("Vô tình thấy vợ nhận 50 triệu đồng, tôi cay đắng phát hiện sự thật"), sát với
   thể loại hơn hẳn từ khoá thịnh hành chung chung.
2. **Google Trends** — bối cảnh xã hội chung. Yếu cho mục đích này (phần lớn là bóng
   đá và tin quốc tế) nên chỉ dùng làm chất liệu phụ.

Có thể thêm kênh YouTube đối thủ qua feed công khai của YouTube — cũng không cần key.

Mọi nguồn đều best-effort: nguồn nào lỗi thì bỏ qua nguồn đó, miễn còn ít nhất một
nguồn sống thì vẫn sinh được ý tưởng.
"""

from __future__ import annotations

import gzip
import io
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import yaml

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo={region}"
YOUTUBE_CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) audiobook-pipeline/1.0"
_HT_NS = "{https://trends.google.com/trending/rss}"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_TIMEOUT = 20


@dataclass
class Feed:
    name: str
    url: str


@dataclass
class TrendConfig:
    region: str = "VN"
    max_items_per_feed: int = 25
    use_google_trends: bool = True
    feeds: list[Feed] = field(default_factory=list)
    youtube_channels: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "TrendConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        feeds = [
            Feed(name=str(f.get("name") or f["url"]), url=str(f["url"]))
            for f in (data.get("feeds") or [])
            if isinstance(f, dict) and f.get("url")
        ]
        return cls(
            region=data.get("region", "VN"),
            max_items_per_feed=int(data.get("max_items_per_feed", 25)),
            use_google_trends=bool(data.get("use_google_trends", True)),
            feeds=feeds,
            youtube_channels=[str(c) for c in (data.get("youtube_channels") or [])],
        )


@dataclass
class TrendSignals:
    """Tiêu đề gom theo từng nguồn, giữ tên nguồn để prompt biết cái nào đáng tin hơn."""

    feeds: dict[str, list[str]] = field(default_factory=dict)
    google_trends: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any(self.feeds.values()) and not self.google_trends

    @property
    def total_items(self) -> int:
        return sum(len(v) for v in self.feeds.values()) + len(self.google_trends)


def _fetch(url: str) -> bytes:
    """Tải một URL, tự giải nén nếu máy chủ trả gzip.

    VnExpress trả gzip kể cả khi không xin — không xử lý là ET.fromstring vỡ với
    lỗi khó hiểu thay vì báo rõ.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "gzip, identity"}
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        raw = response.read()
        encoding = (response.headers.get("Content-Encoding") or "").lower()

    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return raw


def _parse_titles(raw: bytes, limit: int) -> list[str]:
    """Lấy tiêu đề từ RSS 2.0 hoặc Atom (feed YouTube dùng Atom)."""
    root = ET.fromstring(raw)

    items = root.findall("./channel/item")
    if items:
        nodes = [item.findtext("title") for item in items]
    else:
        nodes = [entry.findtext(f"{_ATOM_NS}title") for entry in root.findall(f"{_ATOM_NS}entry")]

    titles = []
    for title in nodes:
        cleaned = (title or "").strip()
        if cleaned:
            titles.append(cleaned)
        if len(titles) >= limit:
            break
    return titles


def fetch_feed(url: str, limit: int = 25) -> list[str]:
    return _parse_titles(_fetch(url), limit)


def fetch_google_trends(region: str, limit: int = 20) -> list[str]:
    root = ET.fromstring(_fetch(GOOGLE_TRENDS_RSS.format(region=region)))

    titles: list[str] = []
    for item in root.iterfind("./channel/item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        # news_item_title cho biết vì sao từ khoá lên trend — hữu ích hơn từ khoá trần.
        context = [
            (news.findtext(f"{_HT_NS}news_item_title") or "").strip()
            for news in item.iterfind(f"{_HT_NS}news_item")
        ]
        context = [c for c in context if c][:2]
        titles.append(f"{title} — {' | '.join(context)}" if context else title)
        if len(titles) >= limit:
            break
    return titles


def collect_signals(config: TrendConfig) -> TrendSignals:
    signals = TrendSignals()

    for feed in config.feeds:
        try:
            titles = fetch_feed(feed.url, config.max_items_per_feed)
        except (urllib.error.URLError, ET.ParseError, OSError, EOFError) as exc:
            signals.errors.append(f"{feed.name} lỗi: {exc}")
            continue
        if titles:
            signals.feeds[feed.name] = titles
        else:
            signals.errors.append(f"{feed.name}: tải được nhưng không có mục nào")

    for channel_id in config.youtube_channels:
        try:
            titles = fetch_feed(
                YOUTUBE_CHANNEL_FEED.format(channel_id=channel_id), config.max_items_per_feed
            )
        except (urllib.error.URLError, ET.ParseError, OSError, EOFError) as exc:
            signals.errors.append(f"Kênh YouTube {channel_id} lỗi: {exc}")
            continue
        if titles:
            signals.feeds[f"Kênh YouTube {channel_id}"] = titles

    if config.use_google_trends:
        try:
            signals.google_trends = fetch_google_trends(config.region)
        except (urllib.error.URLError, ET.ParseError, OSError, EOFError) as exc:
            signals.errors.append(f"Google Trends lỗi: {exc}")

    return signals
