"""Stage 6: SEO metadata.

Hai chế độ:

    # (mới, run_daily.sh dùng) từng tập -- đọc manifest của stage 4
    uv run python -m metadata.cli <script_json> --episodes <manifest_json>
    # Đã lưu metadata tập 1/3: output/metadata/<stem>-ep-01.txt
    # ...
    # Danh sách: output/metadata/<stem>-episodes.json

    # (cũ) một video full
    uv run python -m metadata.cli <script_json> <tts_json> <video_mp4>

Chế độ tập gọi Gemini MỘT lần cho cả truyện rồi suy ra tiêu đề/mô tả từng tập
(xem metadata/episodes.py); đổi tên mp4 của từng tập sang slug SEO có hậu tố
-tap-N; nếu stage 5 đã sinh ảnh theo tập (<stem>-ep-0N.png) thì ghi kèm đường
dẫn ảnh vào metadata để stage 8 khỏi phải đoán.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from episodes.storage import load_manifest, stem_from_manifest
from metadata.full import (
    build_full_description,
    build_minimal_description,
    full_pinned_comment,
    full_title,
    save_full_metadata,
    topic_hashtags,
    youtube_chapter_lines,
)
from metadata.chapters import build_chapter_lines
from metadata.episodes import (
    build_episode_description,
    episode_chapter_lines,
    episode_title,
    pinned_comment,
    save_episode_metadata,
)
from metadata.filename import rename_video_file, slugify
from metadata.seo_generator import generate_seo_copy
from metadata.storage import save_seo_metadata
from scripts.models import Script
from scripts.topics import TOPICS

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "metadata"
THUMBNAILS_DIR = Path(__file__).resolve().parent.parent / "output" / "thumbnails"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


async def _run(
    script_path: Path,
    tts_metadata_path: Path,
    video_path: Path,
    gemini_client=None,
) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    seo_copy = await generate_seo_copy(script, gemini_client)
    chapter_lines = build_chapter_lines(tts_metadata)
    new_video_path = rename_video_file(video_path, seo_copy.title)

    txt_path, json_path = save_seo_metadata(
        script.trope, seo_copy, chapter_lines, new_video_path.name, OUTPUT_DIR
    )

    print(
        f"Đã lưu metadata SEO: {txt_path}\n"
        f"JSON: {json_path}\n"
        f"Video đã đổi tên: {new_video_path}"
    )


def _find_episode_thumbnail(thumbnails_dir: Path, trope: str, number: int) -> Path | None:
    """Ảnh của tập N do stage 5 sinh: file `<trope>-<ts>-ep-0N.png` mới nhất."""
    candidates = sorted(thumbnails_dir.glob(f"{trope}-*-ep-{number:02d}.png"))
    return candidates[-1] if candidates else None


def _find_full_thumbnails(thumbnails_dir: Path, trope: str) -> tuple[Path | None, Path | None]:
    """Bản A/B mới nhất stage 5 sinh cho video full: `<trope>-<ts>-thumbnail-{a,b}.png`."""
    a = sorted(thumbnails_dir.glob(f"{trope}-*-thumbnail-a.png"))
    b = sorted(thumbnails_dir.glob(f"{trope}-*-thumbnail-b.png"))
    return (a[-1] if a else None), (b[-1] if b else None)


def _run_full(script: Script, seo, manifest: dict, stem: str, thumbnails_dir: Path) -> Path:
    topic = TOPICS.get(script.topic)
    ep = manifest["episodes"][0]
    story_title = script.title if script.topic else seo.title
    title = full_title(story_title)
    question = manifest.get("comment_question") or script.comment_question
    hashtags = topic_hashtags(topic.hashtags if topic else None, seo.hashtags)
    # Mô tả đầy đủ: hook, cảnh báo AI, tóm tắt, câu hỏi, playlist, CTA, chương,
    # hashtag. Bản tối giản 05/10 (tiêu đề + "Keywords: 10 từ khoá") bị đánh giá
    # kênh 05/11 xếp vào nhóm nguyên nhân sụt phân phối -- quay lại bản đầu
    # tháng 10. build_minimal_description giữ lại, không dùng ở đây nữa.
    description = build_full_description(
        seo,
        hook=manifest.get("hook") or script.hook,
        comment_question=question,
        chapter_lines=youtube_chapter_lines(ep["chapters"]),
        hashtags=hashtags,
        series=script.series,
    )
    new_video_path = rename_video_file(Path(ep["video_path"]), slugify(story_title))
    thumb_a, thumb_b = _find_full_thumbnails(thumbnails_dir, script.trope)
    data = {
        "topic": script.topic,
        "format": "full",
        "episode_number": 1,
        "episode_total": 1,
        "story_title": story_title,
        "title": title,
        "description": description,
        "tags": seo.tags,
        "hashtags": hashtags,
        "pinned_comment": full_pinned_comment(question),
        "video_filename": new_video_path.name,
        "thumbnail_filename": thumb_a.name if thumb_a else None,
        "thumbnail_b_filename": thumb_b.name if thumb_b else None,
    }
    txt_path, json_path = save_full_metadata(stem, data, OUTPUT_DIR)
    print(f"Đã lưu metadata full: {txt_path}")
    print(f"Video full đã đổi tên: {new_video_path}")

    index_path = OUTPUT_DIR / f"{stem}-full.json"
    index_path.write_text(
        json.dumps(
            {
                "trope": script.trope,
                "topic": script.topic,
                "format": "full",
                "story_title": story_title,
                # Chỉ khác 0 ở chế độ kho: stage 8 dùng để lấy publish_date và
                # ghi lại video_id vào output/story_bank_state.json.
                "story_id": script.story_id,
                "series": script.series,
                "tags": seo.tags,
                "hashtags": hashtags,
                "episodes": [
                    {
                        "number": 1,
                        "total": 1,
                        "title": title,
                        "video_path": str(new_video_path),
                        "metadata_path": str(json_path),
                        "thumbnail_path": str(thumb_a) if thumb_a else None,
                        "thumbnail_b_path": str(thumb_b) if thumb_b else None,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Danh sách: {index_path}")
    return index_path


async def _run_episodes(
    script_path: Path,
    manifest_path: Path,
    gemini_client=None,
    thumbnails_dir: Path | None = None,
) -> Path:
    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    manifest = load_manifest(manifest_path)
    thumbnails_dir = thumbnails_dir or THUMBNAILS_DIR

    if gemini_client is None:
        gemini_client = await _load_gemini_client()
    seo = await generate_seo_copy(script, gemini_client)

    # Stem chung với stage 4: `<trope>-<ts>-{episodes,full}.json` -> `<trope>-<ts>`.
    stem = stem_from_manifest(manifest_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if manifest.get("format") == "full":
        return _run_full(script, seo, manifest, stem, thumbnails_dir)

    topic = TOPICS.get(script.topic)
    if topic is not None:
        seo.hashtags = topic_hashtags(topic.hashtags, seo.hashtags)

    entries: list[dict] = []
    for ep in manifest["episodes"]:
        number, total = ep["number"], ep["total"]
        title = episode_title(seo.title, number, total)
        description = build_episode_description(
            seo,
            hook=manifest.get("hook") or script.hook,
            comment_question=manifest.get("comment_question") or script.comment_question,
            number=number,
            total=total,
            chapter_lines=episode_chapter_lines(ep["chapters"]),
        )
        pinned = pinned_comment(manifest.get("comment_question") or script.comment_question, number, total)

        video_path = Path(ep["video_path"])
        new_video_path = rename_video_file(video_path, f"{slugify(seo.title)}-tap-{number}")
        thumbnail = _find_episode_thumbnail(thumbnails_dir, script.trope, number)

        txt_path, json_path = save_episode_metadata(
            stem,
            number,
            total,
            title,
            description,
            seo.tags,
            seo.hashtags,
            pinned,
            new_video_path.name,
            thumbnail.name if thumbnail else None,
            OUTPUT_DIR,
        )
        entries.append(
            {
                "number": number,
                "total": total,
                "title": title,
                "video_path": str(new_video_path),
                "metadata_path": str(json_path),
                "thumbnail_path": str(thumbnail) if thumbnail else None,
            }
        )
        print(f"Đã lưu metadata tập {number}/{total}: {txt_path}")
        print(f"Video tập {number} đã đổi tên: {new_video_path}")

    index_path = OUTPUT_DIR / f"{stem}-episodes.json"
    index_path.write_text(
        json.dumps(
            {
                "trope": script.trope,
                "topic": script.topic,
                "format": "episodes",
                "story_title": seo.title,
                "tags": seo.tags,
                "hashtags": seo.hashtags,
                "episodes": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Danh sách: {index_path}")
    return index_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh metadata SEO (title/description/tags/hashtags/chapters) cho video YouTube."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("tts_metadata_path", nargs="?", help="(chế độ full) JSON metadata TTS")
    parser.add_argument("video_path", nargs="?", help="(chế độ full) file video .mp4")
    parser.add_argument(
        "--episodes",
        type=Path,
        default=None,
        help="Manifest của stage episodes (<stem>-episodes.json): sinh metadata cho từng tập",
    )
    args = parser.parse_args()
    if args.episodes is not None:
        asyncio.run(_run_episodes(Path(args.script_path), args.episodes))
        return
    if not (args.tts_metadata_path and args.video_path):
        parser.error("Chế độ full cần <tts_metadata_json> <video_mp4>, hoặc dùng --episodes <manifest>.")
    asyncio.run(
        _run(Path(args.script_path), Path(args.tts_metadata_path), Path(args.video_path))
    )


if __name__ == "__main__":
    main()
