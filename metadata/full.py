# metadata/full.py
"""Metadata YouTube cho video FULL của một truyện CHỦ ĐỀ (spec 24/09/2026 §6).

- Tiêu đề: `[Truyện Audio] <title> | <Tên kênh>` — tổng <= 100 ký tự, phần
  <title> <= 60 (câu kể chuyện theo công thức của chủ đề, từ stage 1).
- Mô tả: hook → tóm tắt 2 câu → ❓ câu hỏi chọn phe → link playlist CHỦ ĐỀ →
  CTA đăng ký → chương → hashtag (#truyenaudio + 2 hashtag của chủ đề).
- Bình luận ghim = câu hỏi chọn phe ("1 = ..., 2 = ...").
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from metadata.chapters import _format_timestamp
from metadata.seo_generator import SeoCopy, clip_title

TITLE_PREFIX = "[Truyện Audio]"
MAX_STORY_TITLE_CHARS = 60
MAX_YOUTUBE_TITLE_CHARS = 100
DEFAULT_CHANNEL_NAME = "Audio Truyện"
BASE_HASHTAG = "#truyenaudio"
FULL_CTA = "👉 Đăng ký kênh và bật chuông — truyện mới lên sóng 20h mỗi tối!"
# upload.episodes_cli thay dòng này bằng link playlist của chủ đề (biến .env
# trong registry), hoặc xoá nếu chưa đặt.
TOPIC_PLAYLIST_PLACEHOLDER = "📚 Nghe thêm truyện cùng chủ đề: (link playlist)"
DEFAULT_SIDE_QUESTION = "Nếu là bạn, bạn có nhịn không? 1 = nhịn cho yên nhà, 2 = xử đẹp luôn"
# Luật YouTube cho "Khoảnh khắc chính": mốc đầu 0:00, ít nhất 3 mốc, cách nhau >= 10s.
MIN_CHAPTER_GAP_SECONDS = 10
MIN_CHAPTER_COUNT = 3


def channel_name() -> str:
    return os.getenv("CHANNEL_NAME") or DEFAULT_CHANNEL_NAME


def full_title(story_title: str, channel: str | None = None) -> str:
    channel = channel or channel_name()
    core = clip_title(story_title, MAX_STORY_TITLE_CHARS)
    title = f"{TITLE_PREFIX} {core} | {channel}"
    if len(title) > MAX_YOUTUBE_TITLE_CHARS:
        title = f"{TITLE_PREFIX} {core}"
    return title[:MAX_YOUTUBE_TITLE_CHARS]


def youtube_chapter_lines(chapters: list[dict]) -> list[str]:
    """[{'heading','start_seconds'}] -> dòng chương hợp luật YouTube; không đủ 3
    mốc hợp lệ thì trả [] (thà không có khối chương còn hơn khối bị YouTube bỏ qua)."""
    kept: list[tuple[float, str]] = []
    for c in sorted(chapters, key=lambda c: c["start_seconds"]):
        start = 0.0 if not kept else float(c["start_seconds"])
        if kept and start - kept[-1][0] < MIN_CHAPTER_GAP_SECONDS:
            continue
        kept.append((start, c["heading"]))
    if len(kept) < MIN_CHAPTER_COUNT:
        return []
    return [f"{_format_timestamp(s)} {h}" for s, h in kept]


def two_sentence_summary(text: str) -> str:
    text = " ".join(text.split())
    parts = re.split(r"(?<=[.!?…])\s+", text)
    return " ".join(parts[:2]).strip()


def topic_hashtags(topic_tags: tuple[str, ...] | list[str] | None, fallback: list[str]) -> list[str]:
    tags = [BASE_HASHTAG] + list(topic_tags or fallback[:2])
    seen, out = set(), []
    for t in tags:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def build_full_description(
    seo: SeoCopy,
    hook: str,
    comment_question: str,
    chapter_lines: list[str],
    hashtags: list[str],
) -> str:
    parts: list[str] = []
    if hook:
        parts.append(hook)
    summary = two_sentence_summary(seo.description_draft)
    if summary:
        parts.append(summary)
    parts.append(f"❓ {comment_question or DEFAULT_SIDE_QUESTION}")
    parts.append(TOPIC_PLAYLIST_PLACEHOLDER)
    parts.append(FULL_CTA)
    if chapter_lines:
        parts.append("Chương:\n" + "\n".join(chapter_lines))
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n\n".join(parts)


def full_pinned_comment(comment_question: str) -> str:
    return f"❓ {comment_question or DEFAULT_SIDE_QUESTION}\n🔔 Truyện mới lên sóng 20h mỗi tối — bật chuông để không lỡ nhé!"


def save_full_metadata(
    stem: str,
    data: dict,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = output_dir / f"{stem}-full.txt"
    txt_path.write_text(
        f"TIÊU ĐỀ:\n{data['title']}\n\n"
        f"MÔ TẢ:\n{data['description']}\n\n"
        f"TAGS:\n{', '.join(data['tags'])}\n\n"
        f"HASHTAGS:\n{' '.join(data['hashtags'])}\n\n"
        f"BÌNH LUẬN GHIM:\n{data['pinned_comment']}\n\n"
        f"TÊN FILE VIDEO (đã đổi):\n{data['video_filename']}\n"
        + (f"\nTHUMBNAIL A:\n{data['thumbnail_filename']}\n" if data.get("thumbnail_filename") else "")
        + (
            f"\nTHUMBNAIL B (Test & compare — tải tay trong Studio):\n{data['thumbnail_b_filename']}\n"
            if data.get("thumbnail_b_filename")
            else ""
        ),
        encoding="utf-8",
    )
    json_path = output_dir / f"{stem}-full-video.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return txt_path, json_path
