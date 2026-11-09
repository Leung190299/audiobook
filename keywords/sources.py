"""Nguồn dữ liệu cho stage 0: gợi ý tìm kiếm YouTube và video gần nhất của đối thủ.

Gợi ý tìm kiếm (suggestqueries) không tốn hạn mức API và phản ánh đúng thứ người
Việt đang gõ vào ô tìm kiếm YouTube. Video đối thủ cần YouTube Data API
(~2 đơn vị/kênh) nên cache 7 ngày trong output/keywords/.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "keywords.yaml"
DEFAULT_CACHE_DIR = ROOT / "output" / "keywords"
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
_USER_AGENT = "Mozilla/5.0"
_TIMEOUT = 10


@dataclass
class KeywordConfig:
    seeds: list[str]
    letters: str
    competitors: list[str]
    competitor_cache_days: int = 7
    voice_blocklist: list[str] = field(default_factory=list)
    voice_allowlist: list[str] = field(default_factory=list)
    min_score: int = 7
    used_window_days: int = 30

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "KeywordConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(
            seeds=[str(s) for s in data.get("seeds") or []],
            letters=str(data.get("letters") or ""),
            competitors=[str(c) for c in data.get("competitors") or []],
            competitor_cache_days=int(data.get("competitor_cache_days", 7)),
            voice_blocklist=[str(w).lower() for w in data.get("voice_blocklist") or []],
            voice_allowlist=[str(w).lower() for w in data.get("voice_allowlist") or []],
            min_score=int(data.get("min_score", 7)),
            used_window_days=int(data.get("used_window_days", 30)),
        )


@dataclass
class CompetitorVideo:
    channel: str
    title: str
    views: int
    age_days: float
    # view/ngày của video chia cho trung vị view/ngày của chính kênh đó: >1 là
    # video nổi hơn mặt bằng kênh. So trong kênh để kênh 357K sub không át kênh 5K.
    ratio: float


def fetch_suggestions(query: str, fetch=None) -> list[str]:
    """Danh sách gợi ý YouTube VN cho một chuỗi đang gõ (tối đa 10, theo thứ tự)."""
    url = SUGGEST_URL + "?" + urllib.parse.urlencode(
        {"client": "firefox", "ds": "yt", "hl": "vi", "gl": "vn", "q": query}
    )
    fetch = fetch or _fetch_json
    for attempt in range(3):
        try:
            data = fetch(url)
            return [str(s) for s in data[1]] if isinstance(data, list) and len(data) > 1 else []
        except Exception:
            if attempt == 2:
                return []
            time.sleep(1)
    return []


def _fetch_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.load(response)


def collect_suggestions(
    seeds: list[str], letters: str, fetch=None, pause: float = 0.12
) -> dict[str, float]:
    """Điểm cầu cho từng cụm gợi ý: cộng (10 - vị trí) qua mọi tiền tố đã thử.

    Một cụm hiện sớm và ở nhiều tiền tố là cụm được gõ nhiều. Trả về
    {cụm: điểm} đã bỏ chính các seed (seed là thứ mình gõ, không phải tín hiệu).
    """
    score: dict[str, float] = defaultdict(float)
    seed_set = {s.lower() for s in seeds}
    for seed in seeds:
        for suffix in [""] + [" " + ch for ch in letters]:
            for pos, phrase in enumerate(fetch_suggestions(seed + suffix, fetch=fetch)):
                key = " ".join(phrase.lower().split())
                if key in seed_set:
                    continue
                score[key] += 10 - pos
            if pause:
                time.sleep(pause)
    return dict(score)


# --- đối thủ ------------------------------------------------------------------------


def load_competitor_cache(cache_dir: Path, max_age_days: int) -> list[CompetitorVideo] | None:
    """Cache gần nhất còn hạn, hoặc None khi phải gọi API lại."""
    path = cache_dir / "competitors.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(data["fetched_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
    if (datetime.now(timezone.utc) - fetched).total_seconds() > max_age_days * 86400:
        return None
    return [CompetitorVideo(**row) for row in data.get("videos", [])]


def save_competitor_cache(cache_dir: Path, videos: list[CompetitorVideo]) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "competitors.json"
    path.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "videos": [v.__dict__ for v in videos]},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return path


def fetch_competitor_videos(credentials, handles: list[str], cache_dir: Path) -> list[CompetitorVideo]:
    """50 video gần nhất của mỗi kênh đối thủ qua YouTube Data API.

    Id kênh giải từ handle một lần rồi cache (output/keywords/channels.json).
    Hạn mức: ~1 đơn vị/kênh cho channels.list + 1 playlistItems + 1 videos.
    """
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    cache_dir.mkdir(parents=True, exist_ok=True)
    id_path = cache_dir / "channels.json"
    known: dict[str, dict] = {}
    if id_path.exists():
        try:
            known = json.loads(id_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            known = {}
    now = datetime.now(timezone.utc)
    videos: list[CompetitorVideo] = []
    for handle in handles:
        info = known.get(handle)
        if not info:
            resp = yt.channels().list(part="snippet,contentDetails", forHandle=handle.lstrip("@")).execute()
            items = resp.get("items") or []
            if not items:
                print(f"CẢNH BÁO: không tìm thấy kênh {handle}")
                continue
            ch = items[0]
            info = {
                "id": ch["id"],
                "title": ch["snippet"]["title"],
                "uploads": ch["contentDetails"]["relatedPlaylists"]["uploads"],
            }
            known[handle] = info
        try:
            items = yt.playlistItems().list(
                part="contentDetails", playlistId=info["uploads"], maxResults=50
            ).execute().get("items") or []
        except Exception as exc:  # kênh đóng/đổi: bỏ kênh đó, không bỏ cả lượt
            print(f"CẢNH BÁO: không đọc được video của {handle}: {exc}")
            continue
        ids = [i["contentDetails"]["videoId"] for i in items]
        if not ids:
            continue
        rows = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute().get("items") or []
        vpds = []
        parsed = []
        for v in rows:
            published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
            age = max((now - published).total_seconds() / 86400, 0.1)
            views = int(v["statistics"].get("viewCount", 0))
            vpds.append(views / age)
            parsed.append((v["snippet"]["title"], views, age, views / age))
        median = sorted(vpds)[len(vpds) // 2] if vpds else 0
        for title, views, age, vpd in parsed:
            videos.append(
                CompetitorVideo(
                    channel=info["title"],
                    title=title,
                    views=views,
                    age_days=round(age, 1),
                    ratio=round(vpd / median, 2) if median else 0.0,
                )
            )
    id_path.write_text(json.dumps(known, ensure_ascii=False, indent=1), encoding="utf-8")
    return videos
