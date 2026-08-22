# shorts/excerpt.py
"""Chọn chương gay cấn nhất để đọc trọn làm video ngắn.

Một lần gọi Gemini duy nhất trả về cả 4 thứ (chương, hook, tiêu đề, mô tả). Nội
dung đọc lấy nguyên văn chương được chọn từ kịch bản — Gemini không sinh ra nó,
nên không còn kiểu lỗi "đoạn trích sai độ dài" và không cần vòng thử lại nữa.
Dùng nhãn dòng-đơn chứ không JSON — cùng lý do đã ghi ở `metadata/seo_generator.py`:
gemini-webapi trả JSON không đủ tin cậy.

`_parse_label` cố tình lặp lại logic của `metadata/seo_generator.py` thay vì dùng
chung: bộ nhãn khác nhau và loại exception khác nhau, gom lại sẽ phải truyền cả
hai thứ đó vào — đúng tiền lệ `thumbnail/prompt_generator.py` đã làm.
"""

import os
import re
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Chapter, Script


class ShortExcerptError(Exception):
    pass


@dataclass
class ShortPick:
    chapter_index: int
    hook_text: str
    chapter_text: str
    short_title: str
    short_description: str


# YouTube Shorts giới hạn 180s. Trừ 4s card CTA và ~6s khoảng nghỉ giữa câu, còn
# ~170s cho lời đọc; ở tốc độ đo thực tế 4.30 từ/giây thì được ~730 từ. Lấy 700
# làm trần cứng để chừa biên an toàn cho dao động tốc độ đọc giữa các giọng/câu.
MAX_CHAPTER_WORDS = 700

# Hai chương cuối luôn là phần kết — lấy làm short thì lộ luôn kết cục và mất lý
# do bấm vào tập dài, nên không bao giờ cho Gemini chọn.
RESERVED_ENDING_CHAPTERS = 2

_LABELS = ("CHAPTER", "HOOK", "TITLE", "DESCRIPTION")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def eligible_chapters(script: Script) -> list[Chapter]:
    """Các chương Gemini được phép chọn: đủ ngắn để đọc trọn trong giới hạn
    Shorts, và không phải một trong các chương kết."""
    ordered = sorted(script.chapters, key=lambda c: c.index)
    candidates = ordered[:-RESERVED_ENDING_CHAPTERS]
    eligible = [c for c in candidates if c.word_count <= MAX_CHAPTER_WORDS]
    if not eligible:
        if not candidates:
            raise ShortExcerptError(
                "Không có chương nào đủ ngắn để làm short: kịch bản không đủ "
                f"chương sau khi loại {RESERVED_ENDING_CHAPTERS} chương kết"
            )
        shortest = min(c.word_count for c in candidates)
        raise ShortExcerptError(
            f"Không có chương nào đủ ngắn để làm short: chương ngắn nhất trong "
            f"số được xét dài {shortest} từ, vượt trần {MAX_CHAPTER_WORDS} từ"
        )
    return eligible


def build_excerpt_prompt(script: Script) -> str:
    chapters = eligible_chapters(script)
    chapters_block = "\n\n".join(
        f"[Chương {c.index}] {c.heading}\n{c.text}" for c in chapters
    )
    allowed = ", ".join(str(c.index) for c in chapters)
    return (
        "Bạn là biên tập viên video ngắn cho kênh truyện audio tiếng Việt. "
        "Nhiệm vụ: chọn một chương gay cấn nhất trong số các chương dưới đây để "
        "đọc trọn làm một video Shorts, mục đích kéo người xem về nghe trọn tập.\n\n"
        f"Tiêu đề truyện: {script.title}\n\n"
        f"Các chương được phép chọn:\n{chapters_block}\n\n"
        "Yêu cầu:\n"
        f"- BẮT BUỘC chọn đúng MỘT chương trong số các chương sau: {allowed}. "
        "KHÔNG được chọn chương nào khác ngoài danh sách này.\n"
        "- Ưu tiên chương đặt ra câu hỏi hoặc xung đột chưa được giải quyết, khiến "
        "người xem tò mò muốn biết tiếp theo ra sao.\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "CHAPTER: <số thứ tự chương, chỉ ghi số>\n"
        "HOOK: <câu giật tít 4-10 từ, VIẾT HOA TOÀN BỘ>\n"
        "TITLE: <tiêu đề đăng Shorts, tối đa 100 ký tự>\n"
        "DESCRIPTION: <mô tả 2-3 câu, có kêu gọi nghe full trên kênh, "
        "kết thúc bằng #shorts>"
    )


def split_sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENTENCE_END.split(text.strip()) if p.strip()]


def _parse_label(text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise ShortExcerptError(f"Gemini không trả về nhãn '{label}:' khi chọn chương")
    start = match.end()

    next_positions = []
    for other in _LABELS:
        if other == label:
            continue
        other_match = re.compile(rf"^{re.escape(other)}:", re.MULTILINE).search(text, start)
        if other_match is not None:
            next_positions.append(other_match.start())

    end = min(next_positions) if next_positions else len(text)
    value = text[start:end].strip()
    if not value:
        raise ShortExcerptError(f"Gemini trả về nhãn '{label}:' rỗng")
    return value


def _parse_chapter_index(raw: str, eligible: list[Chapter]) -> int:
    match = re.search(r"\d+", raw)
    if match is None:
        raise ShortExcerptError(f"Không đọc được số chương từ Gemini: {raw!r}")

    index = int(match.group())
    valid = {c.index for c in eligible}
    if index not in valid:
        raise ShortExcerptError(
            f"Gemini chọn chương {index} nhưng chỉ được chọn trong số chương "
            f"{sorted(valid)}"
        )
    return index


async def pick_short_chapter(
    script: Script, client: "GeminiClient | None" = None
) -> ShortPick:
    if client is None:
        client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    eligible = eligible_chapters(script)
    prompt = build_excerpt_prompt(script)

    try:
        response = await client.generate_content(prompt)
    except (GeminiError, APIError, AuthError) as exc:
        raise ShortExcerptError(f"Gemini lỗi khi chọn chương: {exc}") from exc

    text = response.text.strip()

    chapter_index = _parse_chapter_index(_parse_label(text, "CHAPTER"), eligible)
    chapter_by_index = {c.index: c for c in script.chapters}

    return ShortPick(
        chapter_index=chapter_index,
        hook_text=_parse_label(text, "HOOK"),
        chapter_text=chapter_by_index[chapter_index].text,
        short_title=_parse_label(text, "TITLE"),
        short_description=_parse_label(text, "DESCRIPTION"),
    )
