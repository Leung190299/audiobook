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
# Truyện thuộc series có nhân vật xuyên suốt (Nhà Họ Trần, Khu Trọ Cô Ba...):
# nói rõ để người nghe biết còn truyện khác cùng dàn nhân vật.
SERIES_LINE = "📚 Series {series} — nghe các truyện khác trong playlist"
# Nhãn kho dùng cho truyện không thuộc series nào.
STANDALONE_SERIES = "Truyện lẻ"
# Cảnh báo nội dung AI. Nói CẢ "hư cấu" lẫn "do AI tạo": truyện kể ngôi "tôi"
# về tranh chấp đất, chị dâu, khu trọ -- toàn chuyện đời thường, người nghe rất
# dễ tin là có thật rồi kể lại. Chỉ ghi "do AI tạo" thì họ vẫn có thể nghĩ AI
# đang kể lại một vụ có thật.
#
# Bản ngắn nằm ngay sau hook vì YouTube chỉ hiện ~2 dòng đầu trước khi phải bấm
# "thêm": đặt ở đó thì thấy được mà không đè mất hook.
AI_NOTICE_SHORT = "⚠️ Truyện hư cấu. Kịch bản, giọng đọc và hình ảnh do AI tạo ra."
AI_NOTICE_FULL = (
    "⚠️ Đây là truyện hư cấu, không phải chuyện có thật. Kịch bản, giọng đọc và "
    "hình ảnh trong video đều do AI tạo ra. Tên người, địa danh và mọi tình tiết "
    "đều là tưởng tượng; trùng với người thật việc thật là ngoài ý muốn."
)
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


# YouTube bỏ qua TẤT CẢ hashtag trong mô tả nếu có quá 15 cái.
MAX_DESCRIPTION_HASHTAGS = 15
# Từ khoá trong mô tả: đủ cho tìm kiếm, nhiều hơn chỉ là nhồi chữ.
MAX_DESCRIPTION_KEYWORDS = 10


def build_minimal_description(title: str, hashtags: list[str], keywords: list[str]) -> str:
    """Mô tả tối giản theo format tham khảo đang chạy tốt (05/10/2026): tiêu đề,
    hashtag, từ khoá. Giữ thêm cảnh báo AI ngay dòng hai -- yêu cầu riêng của
    kênh từ 30/09, và YouTube chỉ hiện ~2 dòng đầu trước khi phải bấm "thêm".

    Bỏ khối chương, câu hỏi bình luận, link playlist so với build_full_description:
    format tham khảo không có, mà 38 phút vẫn 2,38 triệu view.
    """
    parts = [title, AI_NOTICE_SHORT]
    tags = list(dict.fromkeys(hashtags))[:MAX_DESCRIPTION_HASHTAGS]
    if tags:
        parts.append("Hashtags: " + " ".join(tags))
    words = [k for k in dict.fromkeys(keywords) if k][:MAX_DESCRIPTION_KEYWORDS]
    if words:
        parts.append("Keywords: " + ", ".join(words))
    return "\n\n".join(parts)


def build_full_description(
    seo: SeoCopy,
    hook: str,
    comment_question: str,
    chapter_lines: list[str],
    hashtags: list[str],
    series: str = "",
) -> str:
    parts: list[str] = []
    if hook:
        parts.append(hook)
    parts.append(AI_NOTICE_SHORT)
    summary = two_sentence_summary(seo.description_draft)
    if summary:
        parts.append(summary)
    parts.append(f"❓ {comment_question or DEFAULT_SIDE_QUESTION}")
    if series and series != STANDALONE_SERIES:
        parts.append(SERIES_LINE.format(series=series))
    parts.append(TOPIC_PLAYLIST_PLACEHOLDER)
    parts.append(FULL_CTA)
    if chapter_lines:
        parts.append("Chương:\n" + "\n".join(chapter_lines))
    parts.append(AI_NOTICE_FULL)
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
