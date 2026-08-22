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
import math
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
        if chapter_index not in headings_by_chapter:
            raise ShortPlanError(
                f"Metadata TTS có câu thuộc chương {chapter_index} nhưng mảng "
                "'chapters' không có chương đó — hai mảng lệch nhau, file metadata "
                "hỏng. Chạy lại stage 2 cho tập này."
            )
        heading = headings_by_chapter[chapter_index]

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


def _split_into(chapter_sentences: list[dict], count: int) -> list[list[dict]]:
    """Chia các câu thành đúng `count` lô có thời lượng gần bằng nhau."""
    start = chapter_sentences[0]["start_seconds"]
    total = chapter_sentences[-1]["end_seconds"] - start
    target = total / count

    batches: list[list[dict]] = []
    current: list[dict] = []

    for sentence in chapter_sentences:
        current.append(sentence)
        remaining_after_this = count - len(batches) - 1
        if remaining_after_this <= 0:
            continue
        # Còn đủ câu cho các lô sau mới được đóng lô hiện tại.
        if len(chapter_sentences) - chapter_sentences.index(sentence) - 1 < remaining_after_this:
            continue
        if sentence["end_seconds"] - current[0]["start_seconds"] >= target:
            batches.append(current)
            current = []

    if current:
        batches.append(current)
    return batches


def _pack_chapter(chapter_sentences: list[dict]) -> list[list[dict]]:
    """Chia các câu của một chương thành các lô gần đều nhau, mỗi lô <= ngân sách.

    Cố tình KHÔNG dùng kiểu tham lam "nhồi đầy 165 giây rồi mở lô mới": chương
    190 giây khi đó ra 160 + 30, tức một short tử tế kèm một mẩu 30 giây gần như
    chỉ có card hook và card CTA. Chia đều cho ra 95 + 95, hai short xem được.

    Một câu tự nó dài hơn ngân sách vẫn thành một lô riêng (không cắt nhỏ hơn
    câu), nên hàm luôn dừng.
    """
    total = chapter_sentences[-1]["end_seconds"] - chapter_sentences[0]["start_seconds"]
    count = max(1, math.ceil(total / MAX_PART_SECONDS))

    while count < len(chapter_sentences):
        batches = _split_into(chapter_sentences, count)
        if all(
            b[-1]["end_seconds"] - b[0]["start_seconds"] <= MAX_PART_SECONDS for b in batches
        ):
            return batches
        count += 1

    # Mỗi câu một lô: không chia nhỏ hơn được nữa.
    return [[sentence] for sentence in chapter_sentences]


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
