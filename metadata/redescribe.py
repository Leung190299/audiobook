# metadata/redescribe.py
"""Viết lại mô tả video đã đăng theo mẫu đầy đủ (đánh giá kênh 05/11/2026).

    uv run python -m metadata.redescribe --dry-run
    uv run python -m metadata.redescribe             # video chưa công khai (kho + đã hẹn)
    uv run python -m metadata.redescribe --all       # cả video đã công khai
    uv run python -m metadata.redescribe --shorts    # kèm mô tả short của các video đó

Từ 05/10 mô tả video dài là bản tối giản "tiêu đề / cảnh báo AI / Hashtags /
Keywords: 10 từ khoá" -- đánh giá 05/11 gọi đó là nhồi từ khoá và mất hook,
câu hỏi, playlist. Dựng lại mô tả đầy đủ (metadata.full.build_full_description)
từ file đã có trên máy: hook + câu hỏi trong manifest stage 4, mốc chương trong
manifest, hashtag trong metadata stage 6, series trong chỉ mục. Không có bản
tóm tắt 2 câu (stage 6 không lưu description_draft) nên bỏ đoạn đó.

Short: mô tả "Tên truyện. / Nghe trọn tập tại: <link> / ❓ câu hỏi CỦA TRUYỆN"
thay cho câu chung "Bạn đoán cô ấy làm gì tiếp?".

Mỗi video sửa tốn 51 đơn vị hạn mức (list 1 + update 50); mô tả đã đúng thì
không gọi update. Hỏng 3 lần liên tiếp (thường là hết hạn mức) thì dừng, chạy
lại hôm sau -- video đã sửa không sửa lại.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from metadata.full import build_full_description, youtube_chapter_lines
from metadata.seo_generator import SeoCopy
from scripts.topics import TOPICS
from shorts.storage import short_comment_line
from upload.auth import YouTubeAuthError, load_credentials
from upload.episodes_cli import fill_topic_playlist, playlist_ref
from upload.release import load_index, shorts_of
from upload.series_cli import FULL_EPISODE_LINE
from upload.uploader import list_status, update_description

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "output" / "episodes"
MAX_CONSECUTIVE_FAILURES = 3


class RedescribeError(Exception):
    pass


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RedescribeError(f"Không đọc được {path}: {exc}") from exc


def _manifest_for(index_path: Path, episodes_dir: Path = EPISODES_DIR) -> Path:
    # Chỉ mục stage 6 và manifest stage 4 cùng stem: <trope>-<ts>-full.json.
    return episodes_dir / index_path.name


def full_description_for(row: dict, episodes_dir: Path = EPISODES_DIR) -> tuple[str, Path]:
    """-> (mô tả đầy đủ đã điền link playlist, đường dẫn metadata stage 6 của video)."""
    index_path = Path(row.get("index") or "")
    if not row.get("index") or not index_path.is_file():
        raise RedescribeError(f"Không thấy chỉ mục {index_path} của video {row.get('video_id')}.")
    index = _read_json(index_path)
    manifest = _read_json(_manifest_for(index_path, episodes_dir))
    episodes = index.get("episodes") or []
    if not episodes:
        raise RedescribeError(f"{index_path} không có tập nào.")
    meta_path = Path(episodes[0]["metadata_path"])
    meta = _read_json(meta_path)
    chapters = (manifest.get("episodes") or [{}])[0].get("chapters") or []
    topic = TOPICS.get(index.get("topic") or "")
    _, playlist_url = playlist_ref(os.getenv(topic.playlist_env) if topic else None)
    description = build_full_description(
        SeoCopy(title=meta.get("title", ""), description_draft="", tags=[], hashtags=[]),
        hook=manifest.get("hook") or "",
        comment_question=manifest.get("comment_question") or "",
        chapter_lines=youtube_chapter_lines(chapters),
        hashtags=meta.get("hashtags") or index.get("hashtags") or [],
        series=index.get("series") or "",
    )
    return fill_topic_playlist(description, playlist_url), meta_path


def short_description_for(row: dict, episodes_dir: Path = EPISODES_DIR) -> str:
    index_path = Path(row.get("index") or "")
    manifest = _read_json(_manifest_for(index_path, episodes_dir)) if index_path.is_file() else {}
    title = row.get("story_title") or manifest.get("title") or row.get("title") or ""
    url = row.get("url") or f"https://youtu.be/{row['video_id']}"
    return f"{title}.\n{FULL_EPISODE_LINE.format(url=url)}\n{short_comment_line(manifest.get('comment_question'))}"


def _save_local(meta_path: Path, description: str) -> None:
    meta = _read_json(meta_path)
    meta["description"] = description
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def run(
    credentials,
    rows: list[dict],
    *,
    include_shorts: bool = False,
    dry_run: bool = False,
    updater=update_description,
    episodes_dir: Path = EPISODES_DIR,
) -> dict[str, int]:
    counts = {"long": 0, "short": 0, "failed": 0, "skipped": 0}
    failures = 0
    for row in rows:
        try:
            description, meta_path = full_description_for(row, episodes_dir)
        except RedescribeError as exc:
            print(f"BỎ QUA {row.get('video_id')}: {exc}")
            counts["skipped"] += 1
            continue
        jobs = [(row["video_id"], description, meta_path)]
        if include_shorts:
            short_desc = short_description_for(row, episodes_dir)
            jobs += [(short_id, short_desc, None) for _, short_id in shorts_of(row)]
        for video_id, desc, local in jobs:
            label = "short" if local is None else "long"
            if dry_run:
                print(f"[thử] {label} {video_id}: {desc.splitlines()[0][:70]}")
                counts[label] += 1
                continue
            if updater(credentials, video_id, desc):
                counts[label] += 1
                failures = 0
                if local is not None:
                    _save_local(local, desc)
            else:
                counts["failed"] += 1
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"Hỏng {failures} lần liên tiếp (hết hạn mức?). Dừng; chạy lại hôm sau.")
                    return counts
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Viết lại mô tả video đã đăng theo mẫu đầy đủ.")
    parser.add_argument("--all", action="store_true", help="Cả video đã công khai (mặc định: chỉ video riêng tư/đã hẹn)")
    parser.add_argument("--shorts", action="store_true", help="Sửa cả mô tả short của các video đó")
    parser.add_argument("--video", action="append", default=[], help="Chỉ video_id này (lặp lại được)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    rows = load_index()
    if args.video:
        rows = [r for r in rows if r["video_id"] in set(args.video)]
    try:
        credentials = load_credentials()
    except YouTubeAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not args.all and not args.video:
        statuses = list_status(credentials, [r["video_id"] for r in rows])
        rows = [r for r in rows if statuses.get(r["video_id"], {}).get("privacyStatus") == "private"]
    if not rows:
        print("Không có video nào cần sửa.")
        return 0
    counts = run(credentials, rows, include_shorts=args.shorts, dry_run=args.dry_run)
    print(
        f"Video dài: {counts['long']}, short: {counts['short']}, hỏng: {counts['failed']}, "
        f"bỏ qua: {counts['skipped']}."
    )
    return 1 if counts["failed"] and not counts["long"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
