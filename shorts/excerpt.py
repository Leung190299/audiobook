# shorts/excerpt.py
"""Chọn chương gay cấn nhất và trích đoạn để dựng video ngắn.

Một lần gọi Gemini duy nhất trả về cả 5 thứ (chương, hook, đoạn trích, tiêu đề,
mô tả). Dùng nhãn dòng-đơn chứ không JSON — cùng lý do đã ghi ở
`metadata/seo_generator.py`: gemini-webapi trả JSON không đủ tin cậy.

`_parse_label` cố tình lặp lại logic của `metadata/seo_generator.py` thay vì dùng
chung: bộ nhãn khác nhau và loại exception khác nhau, gom lại sẽ phải truyền cả
hai thứ đó vào — đúng tiền lệ `thumbnail/prompt_generator.py` đã làm.
"""

import os
import re
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Script


class ShortExcerptError(Exception):
    pass


@dataclass
class ShortExcerpt:
    chapter_index: int
    hook_text: str
    excerpt_text: str
    short_title: str
    short_description: str


MIN_EXCERPT_WORDS = 120
MAX_EXCERPT_WORDS = 320

_LABELS = ("CHAPTER", "HOOK", "EXCERPT", "TITLE", "DESCRIPTION")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def build_excerpt_prompt(script: Script) -> str:
    chapters_block = "\n\n".join(
        f"[Chương {c.index}] {c.heading}\n{c.text}" for c in script.chapters
    )
    return (
        "Bạn là biên tập viên video ngắn cho kênh truyện audio tiếng Việt. "
        "Nhiệm vụ: chọn đoạn kịch tính nhất trong truyện dưới đây để dựng một video "
        "Shorts dài khoảng nửa phút đến hơn một phút, mục đích kéo người xem về nghe "
        "trọn tập.\n\n"
        f"Tiêu đề truyện: {script.title}\n\n"
        f"Nội dung các chương:\n{chapters_block}\n\n"
        "Yêu cầu:\n"
        "- Chọn đúng MỘT chương có tình huống gay cấn nhất.\n"
        f"- Trích {MIN_EXCERPT_WORDS}-{MAX_EXCERPT_WORDS} từ liền mạch trong chương đó, "
        "giữ nguyên văn phong gốc.\n"
        "- Bắt đầu bằng một câu hoàn chỉnh, kết thúc ngay tại cao trào để người nghe "
        "tò mò. KHÔNG tiết lộ kết cục.\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "CHAPTER: <số thứ tự chương, chỉ ghi số>\n"
        "HOOK: <câu giật tít 4-10 từ, VIẾT HOA TOÀN BỘ>\n"
        "EXCERPT: <đoạn trích để đọc>\n"
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
        raise ShortExcerptError(f"Gemini không trả về nhãn '{label}:' khi chọn đoạn trích")
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


def _parse_chapter_index(raw: str, script: Script) -> int:
    match = re.search(r"\d+", raw)
    if match is None:
        raise ShortExcerptError(f"Không đọc được số chương từ Gemini: {raw!r}")

    index = int(match.group())
    valid = {c.index for c in script.chapters}
    if index not in valid:
        raise ShortExcerptError(
            f"Gemini chọn chương {index} nhưng kịch bản chỉ có chương "
            f"{min(valid)}-{max(valid)}"
        )
    return index


def _forceful_retry_prompt(base_prompt: str, word_count: int) -> str:
    """Nối thêm yêu cầu độ dài gắt hơn vào cuối prompt gốc, không lặp lại nội
    dung của `build_excerpt_prompt` — Gemini đã bỏ qua yêu cầu đó một lần."""
    return (
        f"{base_prompt}\n\n"
        f"Câu trả lời trước của bạn dài {word_count} từ, KHÔNG đúng yêu cầu. "
        f"Lần này đoạn trích BẮT BUỘC phải nằm trong khoảng "
        f"{MIN_EXCERPT_WORDS}-{MAX_EXCERPT_WORDS} từ."
    )


async def generate_short_excerpt(
    script: Script, client: "GeminiClient | None" = None
) -> ShortExcerpt:
    if client is None:
        client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    prompt = build_excerpt_prompt(script)

    for attempt in range(2):
        try:
            response = await client.generate_content(prompt)
        except (GeminiError, APIError, AuthError) as exc:
            raise ShortExcerptError(f"Gemini lỗi khi chọn đoạn trích: {exc}") from exc

        text = response.text.strip()

        chapter_index = _parse_chapter_index(_parse_label(text, "CHAPTER"), script)
        excerpt_text = _parse_label(text, "EXCERPT")

        word_count = len(excerpt_text.split())
        if MIN_EXCERPT_WORDS <= word_count <= MAX_EXCERPT_WORDS:
            return ShortExcerpt(
                chapter_index=chapter_index,
                hook_text=_parse_label(text, "HOOK"),
                excerpt_text=excerpt_text,
                short_title=_parse_label(text, "TITLE"),
                short_description=_parse_label(text, "DESCRIPTION"),
            )

        if attempt == 0:
            prompt = _forceful_retry_prompt(prompt, word_count)
            continue

        raise ShortExcerptError(
            f"Đoạn trích dài {word_count} từ, nằm ngoài khoảng "
            f"{MIN_EXCERPT_WORDS}-{MAX_EXCERPT_WORDS}"
        )
