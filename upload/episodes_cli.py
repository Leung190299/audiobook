"""Stage 8 (bản chia tập): đăng cả bộ 3 tập hẹn giờ mỗi ngày một tập, rồi trích đoạn.

    uv run python -m upload.episodes_cli <metadata_index_json> [--shorts-prefix <prefix>] \\
        [--first-air 2026-09-23T20:00] [--publish-hour 20] [--privacy private|public]
    # Tập 1/3: <tiêu đề> — https://youtu.be/xxx (lên sóng 2026-09-23 20:00)
    # Tập 2/3: ... (lên sóng 2026-09-24 20:00)
    # ...
    # Trích đoạn 1: ... — https://youtu.be/yyy

`metadata_index_json` là `output/metadata/<stem>-episodes.json` (hoặc
`<stem>-full.json` từ 24/09/2026) mà stage 6 ghi.

Bản FULL (1 video/ngày): private + publishAt 20h, thêm vào playlist của CHỦ ĐỀ
(biến .env ghi trong scripts/topics.py: YOUTUBE_PLAYLIST_HO_HANG / _NGHE_LA /
_BO_ME -- link playlist hoặc id), bình luận câu hỏi chọn phe, 3 Shorts trỏ về
video full. Hạn mức: 1 video + 3 Shorts + playlist ≈ 6.450/10.000 đơn vị.
Mỗi video dài đăng xong được ghi một dòng vào output/metadata/index.jsonl
(topic, format, video_id, publishAt) để báo cáo KPI theo chủ đề.

Lịch: tập 1 lên sóng vào `--first-air` (mặc định: 20h hôm nay nếu còn cách ít
nhất 30 phút, không thì 20h mai), các tập sau cách nhau đúng 24h. Cả ba tập
được tải lên NGAY trong lượt chạy, ở trạng thái private + publishAt, YouTube tự
mở công khai đúng giờ -- pipeline chạy sáng, kênh vẫn lên sóng tối, ba ngày
liền không cần mở máy. Mô tả tập N được cập nhật link tập N+1 ngay sau khi tập
N+1 có id, nên đến lúc công chiếu mọi link đã đúng. Bình luận hỏi ý kiến được
đăng dưới mỗi tập (ghim vẫn làm tay -- API không ghim được).

Trích đoạn (shorts) trỏ về TẬP 1 và đăng ngay (không hẹn giờ) -- mồi phải ra
trước hoặc cùng lúc với tập 1. Hạn mức API: 3 tập + 3 trích đoạn = 6 x 1.600 =
9.600 đơn vị, vừa dưới trần 10.000/ngày; vì thế stage 7 chỉ dựng 3 trích đoạn.

Có nhớ trạng thái trong `<index>-upload-state.json`: chạy lại sau lỗi giữa chừng
không đăng trùng tập nào.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from metadata.episodes import NEXT_EPISODE_PLACEHOLDER, PLAYLIST_PLACEHOLDER
from metadata.full import TOPIC_PLAYLIST_PLACEHOLDER
from scripts.topics import TOPICS
from upload import series_cli
from upload.auth import YouTubeAuthError, load_credentials
from upload.series_cli import SeriesUploadError
from upload.uploader import add_to_playlist, post_comment, update_description, upload_video

load_dotenv()

LOCAL_TZ = ZoneInfo(os.getenv("AUDIOBOOK_TZ", "Asia/Ho_Chi_Minh"))
DEFAULT_PUBLISH_HOUR = 20
# Cách giờ công chiếu ít nhất chừng này thì mới hẹn vào hôm nay; YouTube cần
# thời gian xử lý video 15-20 phút và từ chối publishAt trong quá khứ.
MIN_LEAD = timedelta(minutes=30)
INDEX_JSONL = Path(__file__).resolve().parent.parent / "output" / "metadata" / "index.jsonl"


class EpisodesUploadError(Exception):
    pass


def default_first_air(now: datetime, publish_hour: int = DEFAULT_PUBLISH_HOUR) -> datetime:
    now = now.astimezone(LOCAL_TZ)
    candidate = now.replace(hour=publish_hour, minute=0, second=0, microsecond=0)
    if candidate - now < MIN_LEAD:
        candidate += timedelta(days=1)
    return candidate


def air_times(first_air: datetime, count: int) -> list[datetime]:
    return [first_air + timedelta(days=i) for i in range(count)]


def playlist_ref(value: str | None) -> tuple[str | None, str | None]:
    """Giá trị biến .env của playlist chủ đề -> (id, url). Nhận cả link
    (…?list=PLxxx) lẫn id trần (PLxxx)."""
    if not value or not value.strip():
        return None, None
    value = value.strip()
    if "list=" in value:
        playlist_id = value.split("list=", 1)[1].split("&", 1)[0]
        return playlist_id, value
    if value.startswith("http"):
        return None, value
    return value, f"https://www.youtube.com/playlist?list={value}"


def fill_topic_playlist(description: str, playlist_url: str | None) -> str:
    if playlist_url:
        return description.replace(
            TOPIC_PLAYLIST_PLACEHOLDER, f"📚 Nghe thêm truyện cùng chủ đề: {playlist_url}"
        )
    return description.replace(TOPIC_PLAYLIST_PLACEHOLDER + "\n\n", "").replace(
        TOPIC_PLAYLIST_PLACEHOLDER, ""
    )


def append_index_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def fill_links(description: str, next_url: str | None, playlist_url: str | None) -> str:
    if next_url:
        description = description.replace(NEXT_EPISODE_PLACEHOLDER, f"▶️ Tập tiếp theo: {next_url}")
    if playlist_url:
        description = description.replace(PLAYLIST_PLACEHOLDER, f"📚 Nghe trọn bộ theo thứ tự: {playlist_url}")
    else:
        description = description.replace(PLAYLIST_PLACEHOLDER + "\n", "").replace(PLAYLIST_PLACEHOLDER, "")
    return description


def _state_path(index_path: Path) -> Path:
    return index_path.with_name(index_path.name.removesuffix(".json") + "-upload-state.json")


def run(
    index_path: Path,
    *,
    shorts_prefix: Path | None = None,
    first_air: datetime | None = None,
    publish_hour: int = DEFAULT_PUBLISH_HOUR,
    privacy_status: str = "private",
    category_id: str = "24",
    playlist_url: str | None = None,
    schedule: bool = True,
    uploader=upload_video,
    commenter=post_comment,
    description_updater=update_description,
    credentials_loader=load_credentials,
    playlist_adder=add_to_playlist,
    index_jsonl: Path | None = None,
    now: datetime | None = None,
) -> dict:
    index_path = Path(index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    episodes = sorted(index["episodes"], key=lambda e: e["number"])
    if not episodes:
        raise EpisodesUploadError(f"{index_path} không có tập nào.")

    state_path = _state_path(index_path)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"uploaded": {}}

    def save_state() -> None:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    credentials = credentials_loader()
    now = now or datetime.now(tz=LOCAL_TZ)
    first_air = (first_air or default_first_air(now, publish_hour)).astimezone(LOCAL_TZ)
    times = air_times(first_air, len(episodes))

    playlist_url = playlist_url or os.getenv("YOUTUBE_PLAYLIST_URL") or None
    fmt = index.get("format") or "episodes"
    topic = TOPICS.get(index.get("topic") or "")
    topic_playlist_id, topic_playlist_url = playlist_ref(
        os.getenv(topic.playlist_env) if topic else None
    )
    if topic and not topic_playlist_id:
        print(f"CẢNH BÁO: chưa đặt {topic.playlist_env} trong .env -- không thêm vào playlist chủ đề.")
    index_jsonl = index_jsonl or INDEX_JSONL

    # 1) Tải từng tập lên (bỏ qua tập đã có trong state).
    for ep, air_at in zip(episodes, times):
        key = str(ep["number"])
        if key in state["uploaded"]:
            print(f"Tập {ep['number']}/{ep['total']} đã đăng trước đó: {state['uploaded'][key]['url']}")
            continue
        metadata = json.loads(Path(ep["metadata_path"]).read_text(encoding="utf-8"))
        description = fill_topic_playlist(
            fill_links(metadata["description"], None, playlist_url), topic_playlist_url
        )
        thumbnail = Path(ep["thumbnail_path"]) if ep.get("thumbnail_path") else None
        if thumbnail is not None and not thumbnail.exists():
            print(f"CẢNH BÁO: tập {ep['number']} không có thumbnail {thumbnail.name}, đăng không kèm ảnh.")
            thumbnail = None
        kwargs = dict(
            video_path=Path(ep["video_path"]),
            title=metadata["title"],
            description=description,
            tags=metadata.get("tags", []),
            category_id=category_id,
            privacy_status=privacy_status,
            thumbnail_path=thumbnail,
        )
        if schedule:
            kwargs["publish_at"] = air_at
        try:
            result = uploader(credentials, **kwargs)
        except Exception as exc:
            save_state()
            raise EpisodesUploadError(
                f"Lỗi khi đăng tập {ep['number']}: {exc}. Các tập đã đăng được ghi trong {state_path}; "
                "chạy lại lệnh này để đăng tiếp."
            ) from exc
        state["uploaded"][key] = {
            "video_id": result.video_id,
            "url": result.url,
            "publish_at": air_at.isoformat() if schedule else None,
            "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "comment_posted": False,
            "next_link_set": False,
        }
        save_state()
        append_index_jsonl(
            index_jsonl,
            {
                "date": datetime.now(tz=LOCAL_TZ).date().isoformat(),
                "index": str(index_path),
                "topic": index.get("topic") or "",
                "format": fmt,
                "episode": ep["number"],
                "title": metadata["title"],
                "story_title": index.get("story_title") or "",
                "video_id": result.video_id,
                "url": result.url,
                "publishAt": air_at.isoformat() if schedule else None,
            },
        )
        when = f" (lên sóng {air_at.strftime('%Y-%m-%d %H:%M')})" if schedule else ""
        label = "Full" if fmt == "full" else f"Tập {ep['number']}/{ep['total']}"
        print(f"{label}: {metadata['title']} — {result.url}{when}")

    # 2) Gắn link tập sau vào mô tả tập trước; đăng bình luận câu hỏi.
    for i, ep in enumerate(episodes):
        key = str(ep["number"])
        entry = state["uploaded"][key]
        metadata = json.loads(Path(ep["metadata_path"]).read_text(encoding="utf-8"))
        nxt = episodes[i + 1] if i + 1 < len(episodes) else None
        if topic_playlist_id and not entry.get("playlist_added"):
            if playlist_adder(credentials, topic_playlist_id, entry["video_id"]):
                entry["playlist_added"] = True
                save_state()
        if nxt and not entry.get("next_link_set"):
            next_url = state["uploaded"][str(nxt["number"])]["url"]
            description = fill_topic_playlist(
                fill_links(metadata["description"], next_url, playlist_url), topic_playlist_url
            )
            if description_updater(credentials, entry["video_id"], description):
                entry["next_link_set"] = True
                save_state()
        if not entry.get("comment_posted") and metadata.get("pinned_comment"):
            comment_id = commenter(credentials, entry["video_id"], metadata["pinned_comment"])
            if comment_id:
                entry["comment_posted"] = True
                entry["comment_id"] = comment_id
                save_state()

    first_url = state["uploaded"][str(episodes[0]["number"])]["url"]

    # 3) Trích đoạn trỏ về tập 1.
    if shorts_prefix is not None:
        series_cli.run(
            Path(shorts_prefix),
            limit=99,
            privacy_status=privacy_status,
            category_id=category_id,
            long_video_url=first_url,
            uploader=uploader,
            credentials_loader=lambda: credentials,
        )

    print(f"Đã upload: {first_url}")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Đăng cả bộ tập hẹn giờ mỗi ngày một tập, rồi trích đoạn.")
    parser.add_argument("index_path", type=Path, help="output/metadata/<stem>-episodes.json")
    parser.add_argument("--shorts-prefix", type=Path, default=None, help="vd output/shorts/<slug>-<ts>")
    parser.add_argument("--first-air", default=None, help="Giờ lên sóng tập 1, ISO local, vd 2026-09-23T20:00")
    parser.add_argument("--publish-hour", type=int, default=int(os.getenv("YOUTUBE_PUBLISH_HOUR", DEFAULT_PUBLISH_HOUR)))
    parser.add_argument("--no-schedule", action="store_true", help="Đăng ngay theo --privacy, không hẹn giờ")
    parser.add_argument("--privacy", default=os.getenv("YOUTUBE_PRIVACY_STATUS", "private"),
                        choices=["private", "unlisted", "public"])
    parser.add_argument("--category-id", default=os.getenv("YOUTUBE_CATEGORY_ID", "24"))
    parser.add_argument("--playlist-url", default=None)
    args = parser.parse_args()
    first_air = None
    if args.first_air:
        first_air = datetime.fromisoformat(args.first_air)
        if first_air.tzinfo is None:
            first_air = first_air.replace(tzinfo=LOCAL_TZ)
    try:
        run(
            args.index_path,
            shorts_prefix=args.shorts_prefix,
            first_air=first_air,
            publish_hour=args.publish_hour,
            privacy_status=args.privacy,
            category_id=args.category_id,
            playlist_url=args.playlist_url,
            schedule=not args.no_schedule,
        )
    except (EpisodesUploadError, SeriesUploadError, YouTubeAuthError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
