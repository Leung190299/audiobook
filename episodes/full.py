# episodes/full.py
"""Định dạng FULL (24/09/2026): một truyện = MỘT video 35-45 phút.

Phân tích đối thủ 24/09: toàn bộ hit của các kênh truyện audio đang tăng là video
FULL một truyện, không chia tập. Tái dùng nguyên máy cắt của chế độ tập -- một
video full chỉ là "một tập duy nhất gồm mọi chương":

    [cold open 20-30s: đoạn sảng nhất] [nghỉ 1s] [toàn bộ chương] [card kết 8s]

Cold open lấy từ `short_beats[0]` (đoạn trích NGUYÊN VĂN stage 1 hỏi Gemini sau
khi viết xong truyện), dò ra mốc thời gian bằng scripts.text_tools.locate_quote.
Kịch bản cũ không có short_beats, hoặc không dò được, thì rơi về cách chọn của
chế độ tập (~62% chương áp chót, chừa 3 câu cuối) -- không bao giờ hỏng lượt
chạy chỉ vì thiếu cold open.
"""

from __future__ import annotations

import json
from pathlib import Path

from episodes.cutter import ColdOpen, EpisodeCut, EpisodeCutError, pick_cold_open
from episodes.plan import EpisodeRange
from scripts.models import PROLOGUE_HEADING
from scripts.text_tools import locate_quote, span_within

FULL_COLD_OPEN_MIN_SECONDS = 20.0
FULL_COLD_OPEN_MAX_SECONDS = 30.0
FULL_OUTRO_SECONDS = 8.0
FULL_OUTRO_BASE = "Truyện mới lên sóng 20h mỗi tối — đăng ký kênh để không bỏ lỡ!"


def full_range(chapter_count: int) -> EpisodeRange:
    if chapter_count < 1:
        raise EpisodeCutError("Kịch bản không có chương nào.")
    return EpisodeRange(number=1, total=1, first_chapter=1, last_chapter=chapter_count)


def cold_open_from_beat(
    beat: str,
    sentences: list[dict],
    min_seconds: float = FULL_COLD_OPEN_MIN_SECONDS,
    max_seconds: float = FULL_COLD_OPEN_MAX_SECONDS,
) -> ColdOpen | None:
    found = locate_quote(beat, sentences)
    if found is None:
        return None
    start_i, end_i = found
    span = span_within(sentences, start_i, min_seconds, max_seconds, end_i=end_i)
    if span is None:
        return None
    i, j = span
    return ColdOpen(
        source_start_seconds=float(sentences[i]["start_seconds"]),
        source_end_seconds=float(sentences[j]["end_seconds"]),
        chapter_index=int(sentences[i]["chapter_index"]),
    )


def plan_full_cut(tts_metadata: dict, chapter_count: int, short_beats: list[str] | None = None) -> EpisodeCut:
    chapters_by_index = {c["index"]: c for c in tts_metadata.get("chapters", [])}
    sentences = tts_metadata.get("sentences") or []
    if not sentences:
        raise EpisodeCutError(
            "Metadata TTS không có mốc câu (mảng 'sentences' thiếu hoặc rỗng). Chạy lại stage 2."
        )
    ep = full_range(chapter_count)
    for index in ep.chapter_indices:
        if index not in chapters_by_index:
            raise EpisodeCutError(f"Metadata TTS thiếu chương {index}.")

    cold_open = None
    # Truyện đã mở bằng chương "Mở đầu" kể trước đoạn gay cấn (26/10): không ghép
    # thêm trích đoạn audio nữa, người nghe sẽ nghe hai lần mở đầu liền nhau.
    if tts_metadata.get("chapters") and tts_metadata["chapters"][0].get("heading") == PROLOGUE_HEADING:
        return EpisodeCut(
            episode=ep,
            body_source_start_seconds=float(chapters_by_index[1]["start_seconds"]),
            body_source_end_seconds=float(chapters_by_index[chapter_count]["end_seconds"]),
            cold_open=None,
            outro_seconds=FULL_OUTRO_SECONDS,
        )
    if short_beats:
        cold_open = cold_open_from_beat(short_beats[0], sentences)
        if cold_open is None:
            print("CẢNH BÁO: không dò được short_beats[0] trong audio, dùng cold open dự phòng.")
    if cold_open is None:
        # Chương áp chót: xung đột đã lên cao nhưng cú vả mặt lớn (chương kết)
        # chưa lộ. Truyện 1 chương thì đành lấy chương đó.
        fallback_chapter = chapter_count - 1 if chapter_count > 1 else chapter_count
        cold_open = pick_cold_open(
            [s for s in sentences if s["chapter_index"] == fallback_chapter],
            fallback_chapter,
            min_seconds=FULL_COLD_OPEN_MIN_SECONDS,
            max_seconds=FULL_COLD_OPEN_MAX_SECONDS,
        )

    return EpisodeCut(
        episode=ep,
        body_source_start_seconds=float(chapters_by_index[1]["start_seconds"]),
        body_source_end_seconds=float(chapters_by_index[chapter_count]["end_seconds"]),
        cold_open=cold_open,
        outro_seconds=FULL_OUTRO_SECONDS,
    )


def suggest_same_topic(
    topic: str,
    exclude_title: str,
    index_jsonl: Path,
    history_json: Path,
) -> str:
    """Tiêu đề một truyện CÙNG CHỦ ĐỀ để gợi ý ở card kết: ưu tiên truyện đã
    đăng gần nhất (output/metadata/index.jsonl), không có thì truyện gần nhất
    trong lịch sử stage 1. Rỗng nếu chưa có gì."""
    if not topic:
        return ""
    candidates: list[str] = []
    if index_jsonl.exists():
        for line in index_jsonl.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("topic") == topic and row.get("title"):
                candidates.append(row.get("story_title") or row["title"])
    if not candidates and history_json.exists():
        try:
            entries = json.loads(history_json.read_text(encoding="utf-8")).get("entries", [])
        except json.JSONDecodeError:
            entries = []
        candidates = [e.get("title", "") for e in entries if e.get("topic") == topic]
    for title in reversed(candidates):
        if title and title != exclude_title:
            return title
    return ""


def full_outro_text(comment_question: str = "", suggestion: str = "") -> str:
    lines = []
    if comment_question:
        lines.append(comment_question)
    lines.append(FULL_OUTRO_BASE)
    if suggestion:
        lines.append(f"Nghe tiếp: {suggestion}")
    return "\n".join(lines)
