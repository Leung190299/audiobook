# scripts/text_tools.py
"""Tiện ích chữ dùng chung cho stage 1/4/5/7: cắt tiêu đề, làm sạch chữ
thumbnail, và dò một đoạn trích nguyên văn trong mốc câu của TTS."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

THUMB_TEXT_MAX_WORDS = 12
MAX_THUMB_KEYWORDS = 3


def clip_chars(text: str, max_chars: int) -> str:
    """Cắt ở ranh giới từ, bỏ dấu câu treo ở cuối."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:-–—|")


def clean_thumb_fields(thumb_text: str, keywords, title: str) -> tuple[str, list[str]]:
    """thumb_text <= 12 chữ (rỗng thì lấy tiêu đề); từ khoá phải là chuỗi con
    của thumb_text (so không phân biệt hoa thường, trả về đúng chữ trong
    thumb_text), tối đa 3, không chồng lên nhau. Không còn từ khoá nào hợp lệ
    thì lấy 2 chữ cuối -- cụm hành động thường nằm cuối câu tiêu đề."""
    text = " ".join((thumb_text or title).split())
    words = text.split(" ")
    if len(words) > THUMB_TEXT_MAX_WORDS:
        text = " ".join(words[:THUMB_TEXT_MAX_WORDS]).rstrip(" ,.;:-–—")
    lowered = text.lower()
    if isinstance(keywords, str):
        keywords = [keywords]
    result: list[str] = []
    taken: list[tuple[int, int]] = []
    for kw in keywords or []:
        kw = " ".join(str(kw).split()).strip(" ,.;:!?'\"")
        if not kw:
            continue
        pos = lowered.find(kw.lower())
        if pos < 0:
            continue
        span = (pos, pos + len(kw))
        if any(not (span[1] <= a or span[0] >= b) for a, b in taken):
            continue
        taken.append(span)
        result.append(text[span[0] : span[1]])
        if len(result) == MAX_THUMB_KEYWORDS:
            break
    if not result and text:
        tail = text.split(" ")[-2:]
        result = [" ".join(tail).strip(" ,.;:!?")]
    return text, result


def keyword_spans(text: str, keywords: list[str]) -> list[tuple[int, int, int]]:
    """[(start, end, keyword_index)] của từng từ khoá trong `text` (không phân
    biệt hoa thường). Dùng để tô màu từng chữ trên thumbnail."""
    lowered = text.lower()
    spans = []
    for i, kw in enumerate(keywords):
        pos = lowered.find(kw.lower())
        if pos >= 0 and kw:
            spans.append((pos, pos + len(kw), i))
    return spans


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…]['\"”’])\s+|(?<=[.!?…])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if len(a) >= 15 and len(b) >= 15 and (a in b or b in a):
        return 1.0
    m = SequenceMatcher(None, a, b, autojunk=False)
    if m.real_quick_ratio() < 0.5 or m.quick_ratio() < 0.5:
        return 0.0
    return m.ratio()


FIRST_MATCH_MIN = 0.72
LAST_MATCH_MIN = 0.6
MAX_QUOTE_SENTENCES = 30


def locate_quote(quote: str, sentences: list[dict]) -> tuple[int, int] | None:
    """Tìm đoạn trích `quote` trong danh sách câu (mỗi câu có 'text'). Trả về
    (chỉ số câu đầu, chỉ số câu cuối) -- bao gồm cả hai -- hoặc None.

    Không đòi khớp từng chữ: TTS tách câu khác Gemini, và Gemini "trích nguyên
    văn" vẫn hay sửa một hai chữ. So câu đầu của đoạn trích với từng câu (tỉ lệ
    giống >= 0,72), rồi tìm câu cuối trong ~30 câu kế tiếp."""
    parts = [normalize(p) for p in split_sentences(quote)]
    parts = [p for p in parts if len(p.split()) >= 3] or [normalize(quote)]
    if not parts or not parts[0] or not sentences:
        return None
    norm = [normalize(s.get("text", "")) for s in sentences]

    first_q = parts[0]
    best_i, best_score = -1, 0.0
    for i, s in enumerate(norm):
        score = _similar(first_q, s)
        if score > best_score:
            best_i, best_score = i, score
            if score >= 0.999:
                break
    if best_i < 0 or best_score < FIRST_MATCH_MIN:
        return None

    last_q = parts[-1]
    if len(parts) == 1:
        return best_i, best_i
    best_j, best_last = best_i, 0.0
    for j in range(best_i, min(len(norm), best_i + MAX_QUOTE_SENTENCES)):
        score = _similar(last_q, norm[j])
        if score > best_last:
            best_j, best_last = j, score
    if best_last < LAST_MATCH_MIN:
        best_j = min(len(norm) - 1, best_i + len(parts) - 1)
    return best_i, best_j


def span_within(
    sentences: list[dict],
    start_i: int,
    min_seconds: float,
    max_seconds: float,
    end_i: int | None = None,
    same_chapter: bool = True,
) -> tuple[int, int] | None:
    """Mở rộng/thu hẹp dải câu bắt đầu ở `start_i` để tổng thời lượng nằm trong
    [min, max] giây. Ưu tiên giữ tới `end_i` (hết đoạn trích) nếu vừa; không
    bắc qua chương khác khi `same_chapter`. Không đạt min thì trả None."""
    if not 0 <= start_i < len(sentences):
        return None
    chapter = sentences[start_i].get("chapter_index")
    start = sentences[start_i]["start_seconds"]
    j = start_i
    target_end = end_i if end_i is not None else start_i
    while j + 1 < len(sentences):
        nxt = sentences[j + 1]
        if same_chapter and nxt.get("chapter_index") != chapter:
            break
        if nxt["end_seconds"] - start > max_seconds:
            break
        cur_len = sentences[j]["end_seconds"] - start
        if j >= target_end and cur_len >= min_seconds:
            break
        j += 1
    if sentences[j]["end_seconds"] - start > max_seconds:
        return None
    i = start_i
    # Tiến tới thì vướng một câu rất dài (vượt max) mà chưa đủ min: lùi điểm
    # đầu về các câu ngay trước (cùng chương) -- đoạn vẫn chứa trọn câu mở.
    while sentences[j]["end_seconds"] - sentences[i]["start_seconds"] < min_seconds and i > 0:
        prev = sentences[i - 1]
        if same_chapter and prev.get("chapter_index") != chapter:
            break
        if sentences[j]["end_seconds"] - prev["start_seconds"] > max_seconds:
            break
        i -= 1
    if sentences[j]["end_seconds"] - sentences[i]["start_seconds"] < min_seconds:
        return None
    return i, j
