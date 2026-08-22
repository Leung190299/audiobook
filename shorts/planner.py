# shorts/planner.py
"""Chia mốc thời gian từng câu của cả tập thành các phần short đánh số.

Module này thuần tính toán: nhận metadata TTS (đã có mảng `sentences` theo
câu, ghi bởi `tts/storage.py`), trả về danh sách `ShortPart` — không đụng file
audio, không render, không gọi Gemini.

Quy tắc chia (xem docs/superpowers/specs/2026-08-22-shorts-series-design.md):
gói các câu liên tiếp trong cùng một chương cho tới khi thêm câu kế tiếp sẽ
khiến phần vượt `MAX_PART_SECONDS`, rồi mở phần mới. Không bao giờ bắc cầu qua
ranh giới chương — mỗi phần dùng ảnh nền của đúng một chương.
"""

import itertools
from dataclasses import dataclass

MAX_PART_SECONDS = 165.0


class ShortPlanError(Exception):
    pass


@dataclass
class PartCaption:
    text: str
    start_seconds: float  # đã quy về gốc 0 của phần
    end_seconds: float


@dataclass
class ShortPart:
    number: int  # 1-based, liên tục trên toàn tập
    chapter_index: int
    heading: str  # tiêu đề chương chứa phần này
    source_start_seconds: float  # vị trí trong wav gốc của cả tập
    source_end_seconds: float
    captions: list[PartCaption]

    @property
    def duration_seconds(self) -> float:
        return self.source_end_seconds - self.source_start_seconds


def plan_parts(tts_metadata: dict) -> list[ShortPart]:
    sentences = tts_metadata.get("sentences")
    if not sentences:
        raise ShortPlanError(
            "Metadata TTS không có mốc câu (mảng 'sentences' thiếu hoặc rỗng). "
            "Nguyên nhân thường gặp: tập này được dựng trước khi stage 2 biết "
            "ghi mốc thời gian từng câu. Muốn làm short cho tập này, hãy chạy "
            "lại stage 2 rồi thử lại."
        )

    for sentence in sentences:
        if sentence["end_seconds"] <= sentence["start_seconds"]:
            raise ShortPlanError(
                f"Câu {sentence.get('index')} của chương {sentence.get('chapter_index')} "
                f"có end_seconds ({sentence['end_seconds']}) không lớn hơn "
                f"start_seconds ({sentence['start_seconds']})."
            )

    headings_by_chapter = {
        chapter["index"]: chapter["heading"] for chapter in tts_metadata.get("chapters", [])
    }

    parts: list[ShortPart] = []
    part_number = 1

    for chapter_index, group in itertools.groupby(sentences, key=lambda s: s["chapter_index"]):
        chapter_sentences = list(group)
        heading = headings_by_chapter.get(chapter_index, "")

        for prev, curr in zip(chapter_sentences, chapter_sentences[1:]):
            if curr["start_seconds"] <= prev["start_seconds"]:
                raise ShortPlanError(
                    f"Các câu trong chương {chapter_index} không theo thứ tự thời "
                    f"gian tăng dần: câu {curr.get('index')} bắt đầu tại "
                    f"{curr['start_seconds']}s, không sau câu {prev.get('index')} "
                    f"tại {prev['start_seconds']}s."
                )

        for batch in _pack_chapter(chapter_sentences):
            parts.append(_build_part(part_number, chapter_index, heading, batch))
            part_number += 1

    return parts


def _pack_chapter(chapter_sentences: list[dict]) -> list[list[dict]]:
    """Gói các câu liên tiếp trong một chương thành các lô, mỗi lô <= ngân sách.

    Một câu tự nó dài hơn ngân sách vẫn tạo thành một lô riêng (không cắt nhỏ
    hơn câu), để không bao giờ treo hay bỏ sót câu.
    """
    batches: list[list[dict]] = []
    current_batch: list[dict] = []

    for sentence in chapter_sentences:
        if current_batch:
            batch_start = current_batch[0]["start_seconds"]
            candidate_duration = sentence["end_seconds"] - batch_start
            if candidate_duration > MAX_PART_SECONDS:
                batches.append(current_batch)
                current_batch = []
        current_batch.append(sentence)

    if current_batch:
        batches.append(current_batch)

    return batches


def _build_part(number: int, chapter_index: int, heading: str, batch: list[dict]) -> ShortPart:
    source_start = batch[0]["start_seconds"]
    source_end = batch[-1]["end_seconds"]
    captions = [
        PartCaption(
            text=sentence["text"],
            start_seconds=sentence["start_seconds"] - source_start,
            end_seconds=sentence["end_seconds"] - source_start,
        )
        for sentence in batch
    ]
    return ShortPart(
        number=number,
        chapter_index=chapter_index,
        heading=heading,
        source_start_seconds=source_start,
        source_end_seconds=source_end,
        captions=captions,
    )
