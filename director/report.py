"""Số liệu Analytics hai kênh cho phiên sáng của giám đốc kênh.

    python -m director.report [--date YYYY-MM-DD] [--out DIR]
Ghi so-lieu.json (danh sách ChannelData theo thứ tự main, xomque) và so-lieu.md vào output/director/<ngày>/.
Một kênh lỗi (token hết hạn, thiếu quyền Analytics) chỉ làm mục "loi" của kênh đó có dòng; lệnh vẫn thoát 0.
Mỗi video: views/phút xem/xem trung bình/% xem/nguồn xem 7 ngày, view và đăng ký 28 ngày.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from director import paths
from upload.auth import ANALYTICS_SCOPE, has_scope, load_credentials
from upload.release import load_index

STICK_KIT = Path(os.environ.get("STICK_KIT") or paths.ROOT.parent / "lemo" / "stickman" / "kit").resolve()
METRICS_7D = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"
METRICS_28D = "views,subscribersGained"
BATCH = 50
ChannelData = dict


class ReportError(RuntimeError):
    """Không lấy được credential của một kênh; thông điệp nói rõ người dùng phải làm gì."""


def _kit_module(name: str):
    if str(STICK_KIT) not in sys.path:
        sys.path.insert(0, str(STICK_KIT))
    return __import__(name)


def credentials_for(channel: str, *, need_analytics: bool = True):
    """Credential của kênh; `need_analytics=False` cho Data API v3 (videos.list chỉ cần force-ssl).
    Raise ReportError kèm cách sửa; không bao giờ mở trình duyệt."""
    if channel == "main":
        from upload.auth import TOKEN_PATH
        if not Path(TOKEN_PATH).exists():
            raise ReportError("kênh chính chưa có token: chạy `uv run python -m upload.auth`")
        if need_analytics and not has_scope(ANALYTICS_SCOPE):
            raise ReportError("token kênh chính chưa có quyền Analytics: chạy `uv run python -m upload.auth --force` và đồng ý cả quyền xem báo cáo")
        try:
            return load_credentials()
        except Exception as exc:  # invalid_grant, thiếu tệp...
            raise ReportError(f"token kênh chính hỏng: chạy `uv run python -m upload.auth` ({str(exc)[:200]})") from exc
    if channel == "xomque":
        try:
            login = _kit_module("login")
        except ImportError as exc:
            raise ReportError(f"không thấy kit/login.py ở {STICK_KIT} (đặt STICK_KIT)") from exc
        path = login.token_path("xomque")
        granted = []
        try:
            granted = json.loads(Path(path).read_text(encoding="utf-8")).get("scopes") or []
        except (OSError, json.JSONDecodeError):
            raise ReportError("kênh Xóm Que chưa có token: chạy `cd /Users/lee/Project/Apps/lemo/stickman && kit/stick login xomque`")
        if need_analytics and ANALYTICS_SCOPE not in granted:
            raise ReportError("xomque chưa có quyền yt-analytics.readonly: chạy `kit/stick login xomque --force` và đồng ý cả quyền xem báo cáo")
        try:
            return login.credentials("xomque")
        except SystemExit as exc:
            raise ReportError(f"token Xóm Que hỏng: {exc}") from exc
    raise ReportError(f"không có kênh {channel!r}")


def build_analytics(credentials):
    from googleapiclient.discovery import build

    return build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)


def video_ids_for(channel: str) -> list[tuple[str, str, str]]:
    """(video_id, tiêu đề, ngày đăng/phát ISO hoặc "") của kênh: kênh chính từ output/metadata/index.jsonl,
    kênh phụ từ các da-dang.json của bộ người que."""
    if channel == "main":
        return [(r["video_id"], r.get("title") or r.get("story_title") or "", str(r.get("publish_at") or r.get("publishAt") or r.get("date") or ""))
                for r in load_index()]
    out = []
    for f in sorted(STICK_KIT.parent.glob(f"*/upload/{channel}/da-dang.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("video_id"):
            out.append((d["video_id"], d.get("title") or f.parent.parent.parent.name, str(d.get("publish_at") or d.get("uploaded_at") or "")))
    return out


TRAFFIC_BATCH = 10            # mỗi video nhiều nguồn xem; lô nhỏ để không vượt maxResults mà mất hàng


def _query(analytics, start: date, end: date, metrics: str, ids: list[str], dimensions: str = "video", batch: int = BATCH) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for i in range(0, len(ids), batch):
        resp = analytics.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(), metrics=metrics,
            dimensions=dimensions, filters="video==" + ",".join(ids[i:i + batch]), maxResults=200,
        ).execute()
        rows.extend(resp.get("rows") or [])
    return rows


def _blank(vid: str, titles: dict[str, str], published: dict[str, str]) -> dict:
    return {"video_id": vid, "title": titles.get(vid, ""), "published_at": published.get(vid, ""), "views_7d": 0, "minutes_7d": 0.0,
            "avg_view_seconds_7d": 0.0, "avg_view_pct_7d": 0.0, "subs_7d": 0, "views_28d": 0, "subs_28d": 0, "traffic_7d": {}}


def fetch_channel(analytics, channel: str, video_ids: list[str], end: date, *, days7: int = 7, days28: int = 28,
                  titles: dict[str, str] | None = None, published: dict[str, str] | None = None) -> ChannelData:
    titles, published = titles or {}, published or {}
    data: ChannelData = {"channel": channel, "ten": paths.CHANNELS.get(channel, {}).get("name", channel), "den_ngay": end.isoformat(),
                         "videos": [], "totals_7d": {"views": 0, "minutes": 0.0, "subs": 0}, "totals_28d": {"views": 0, "subs": 0}, "loi": []}
    by_id: dict[str, dict] = {v: _blank(v, titles, published) for v in video_ids}
    if not video_ids or analytics is None:                  # không có video, hoặc không có quyền Analytics: vẫn liệt kê video với số 0
        data["videos"] = sorted(by_id.values(), key=lambda v: v.get("published_at", ""), reverse=True)
        return data
    s7, s28 = end - timedelta(days=days7 - 1), end - timedelta(days=days28 - 1)
    for vid, views, minutes, avg_s, avg_pct, subs in _query(analytics, s7, end, METRICS_7D, video_ids):
        v = by_id.setdefault(vid, _blank(vid, titles, published))
        v.update(views_7d=int(views), minutes_7d=float(minutes), avg_view_seconds_7d=float(avg_s), avg_view_pct_7d=float(avg_pct), subs_7d=int(subs))
    for vid, views, subs in _query(analytics, s28, end, METRICS_28D, video_ids):
        by_id.setdefault(vid, _blank(vid, titles, published)).update(views_28d=int(views), subs_28d=int(subs))
    for vid, source, views in _query(analytics, s7, end, "views", video_ids, dimensions="video,insightTrafficSourceType", batch=TRAFFIC_BATCH):
        by_id.setdefault(vid, _blank(vid, titles, published))["traffic_7d"][source] = int(views)
    data["videos"] = sorted(by_id.values(), key=lambda v: v.get("published_at", ""), reverse=True)
    data["totals_7d"] = {"views": sum(v.get("views_7d", 0) for v in by_id.values()), "minutes": round(sum(v.get("minutes_7d", 0.0) for v in by_id.values()), 1),
                         "subs": sum(v.get("subs_7d", 0) for v in by_id.values())}
    data["totals_28d"] = {"views": sum(v.get("views_28d", 0) for v in by_id.values()), "subs": sum(v.get("subs_28d", 0) for v in by_id.values())}
    return data


def _clock(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def render_markdown(data: list[ChannelData], end: date) -> str:
    out = [f"# Số liệu hai kênh tới hết {end:%d/%m/%Y}", "",
           "Analytics có thể chưa cập nhật 1–2 ngày gần nhất: số 0 của video mới chưa chắc là 0 thật.", ""]
    for d in data:
        out.append(f"## {d.get('ten', d['channel'])} (`{d['channel']}`)")
        t7, t28 = d.get("totals_7d", {}), d.get("totals_28d", {})
        out.append(f"7 ngày: {t7.get('views', 0)} view, {t7.get('minutes', 0)} phút xem, {t7.get('subs', 0)} đăng ký · "
                   f"28 ngày: {t28.get('views', 0)} view, {t28.get('subs', 0)} đăng ký")
        if d.get("loi"):
            out.append("")
            out.append("Lỗi: " + " | ".join(d["loi"]))
        vids = d.get("videos", [])
        if vids:
            newest = sorted(vids, key=lambda v: v.get("published_at", ""), reverse=True)[:12]
            out += ["", "12 video mới nhất:", "", "| Đăng/phát | Video | View 7n | Xem TB | % xem | Nguồn chính | View 28n |", "|---|---|---|---|---|---|---|"]
            for v in newest:
                src = max(v.get("traffic_7d", {}).items(), key=lambda kv: kv[1], default=("", 0))
                out.append(f"| {str(v.get('published_at', ''))[:10]} | {v.get('title', '')[:48]} ({v['video_id']}) | {v.get('views_7d', 0)} | "
                           f"{_clock(v.get('avg_view_seconds_7d', 0.0))} | {v.get('avg_view_pct_7d', 0.0):.0f}% | {src[0]} {src[1] if src[0] else ''} | {v.get('views_28d', 0)} |")
            top = sorted(vids, key=lambda v: -v.get("views_7d", 0))[:5]
            out += ["", "Nhiều view nhất 7 ngày: " + "; ".join(f"{v.get('title', '')[:30]} ({v.get('views_7d', 0)})" for v in top)]
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kéo số liệu Analytics hai kênh cho giám đốc kênh.")
    ap.add_argument("--date", type=date.fromisoformat, default=None, help="ngày làm việc (mặc định hôm nay giờ VN); số liệu tới hết hôm qua")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    day = a.date or paths.today()
    out = a.out or paths.day_dir(day)
    out.mkdir(parents=True, exist_ok=True)
    end = day - timedelta(days=1)
    data: list[ChannelData] = []
    for channel in ("main", "xomque"):
        ids = video_ids_for(channel)
        vid_list = [row[0] for row in ids]
        titles = {row[0]: row[1] for row in ids}
        published = {row[0]: row[2] for row in ids}
        try:
            analytics = build_analytics(credentials_for(channel))
            d = fetch_channel(analytics, channel, vid_list, end, titles=titles, published=published)
        except ReportError as exc:
            d = fetch_channel(None, channel, vid_list, end, titles=titles, published=published)
            d["loi"].append(str(exc))
        except Exception as exc:  # lỗi API khác: ghi lại, không chết
            d = fetch_channel(None, channel, vid_list, end, titles=titles, published=published)
            d["loi"].append(f"lỗi Analytics {type(exc).__name__}: {str(exc)[:300]}")
        d["so_video_biet"] = len(ids)
        data.append(d)
    try:
        (out / "so-lieu.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "so-lieu.md").write_text(render_markdown(data, end), encoding="utf-8")
    except OSError as exc:
        print(f"Không ghi được số liệu: {exc}", file=sys.stderr)
        return 1
    print(f"Số liệu: {out / 'so-lieu.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
