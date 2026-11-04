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
from dataclasses import dataclass, replace

MAX_PART_SECONDS = 165.0

# Số trích đoạn ngắn dựng cho mỗi tập. Trước đây stage 7 cắt trọn tập thành ~31
# phần nối tiếp; nay short chỉ còn là mồi kéo người nghe về video dài, nên 5 cái
# rải đều có sức mời tốt hơn 31 cái kể hết câu chuyện.
# 22/09/2026: xuống 3. Kênh đo được: trích đoạn 4/5 của một tập 1,2N view trong
# khi 1/5 của chính tập đó 423 -- ba cái tốt hơn năm cái loãng; và hạn mức
# YouTube Data API (10.000 đơn vị/ngày, 1.600/lần đăng) chỉ đủ 3 tập + 3 trích
# đoạn trong một lượt đăng (xem upload/episodes_cli.py).
TEASER_COUNT = 3

# Vị trí (theo tỉ lệ thời lượng tập) của từng trích đoạn. Bắt đầu sớm ở 5% để
# lấy được cú hook mở đầu, dừng ở 85% để chừa hẳn đoạn kết -- trích đoạn để mời
# nghe, không phải để kể nốt. Với count khác 5, _teaser_fractions rải đều trong
# cùng khoảng 5%-85%.
TEASER_POSITIONS = (0.05, 0.25, 0.45, 0.65, 0.85)


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
    # Câu thoại mở đầu của Short dựng từ short_beats (24/09/2026) -- làm tiêu đề
    # và chữ trên card đầu. Rỗng với trích đoạn kiểu cũ (dùng tiêu đề chương).
    hook_line: str = ""

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


def plan_teasers(tts_metadata: dict, count: int = TEASER_COUNT) -> list[ShortPart]:
    """Chọn `count` phần rải đều cả tập để làm trích đoạn mời nghe.

    Dùng lại nguyên `plan_parts()` để mỗi trích đoạn vẫn là một khoảng 85-165
    giây không bắc cầu qua ranh giới chương, rồi chỉ giữ lại những phần nằm gần
    các mốc trong `TEASER_POSITIONS`. Phần cuối tập bị loại khỏi danh sách ứng
    viên: mời người ta nghe trọn tập mà lại chiếu sẵn cái kết là tự phá mục đích.

    Đánh số lại từ 1 -- nhãn "TRÍCH ĐOẠN 3/5" phải đếm trong bộ trích đoạn, chứ
    không phải số thứ tự cũ trong ~31 phần của cả tập.
    """
    parts = plan_parts(tts_metadata)
    if len(parts) <= count:
        return _renumber(parts)

    candidates = parts[:-1]
    if len(candidates) <= count:
        return _renumber(candidates)

    episode_end = parts[-1].source_end_seconds
    chosen: list[int] = []
    for fraction in _teaser_fractions(count):
        target = fraction * episode_end
        best = min(
            (i for i in range(len(candidates)) if i not in chosen),
            key=lambda i: abs(_midpoint(candidates[i]) - target),
        )
        chosen.append(best)

    return _renumber([candidates[i] for i in sorted(chosen)])


def _teaser_fractions(count: int) -> tuple[float, ...]:
    if count == len(TEASER_POSITIONS):
        return TEASER_POSITIONS
    if count == 1:
        return ((TEASER_POSITIONS[0] + TEASER_POSITIONS[-1]) / 2,)
    step = (TEASER_POSITIONS[-1] - TEASER_POSITIONS[0]) / (count - 1)
    return tuple(TEASER_POSITIONS[0] + i * step for i in range(count))


def _midpoint(part: ShortPart) -> float:
    return (part.source_start_seconds + part.source_end_seconds) / 2


def _renumber(parts: list[ShortPart]) -> list[ShortPart]:
    return [replace(part, number=i) for i, part in enumerate(parts, start=1)]


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


# --- Shorts từ short_beats (24/09/2026) ---------------------------------------
# 3 Shorts/truyện, mỗi cái là một đoạn hài/sảng stage 1 đã trích nguyên văn, mở
# bằng chính câu thoại buồn cười đó. 30-55 giây: đủ trọn một miếng hài, dưới
# ngưỡng người xem lướt đi.
BEAT_MIN_SECONDS = 30.0
BEAT_MAX_SECONDS = 55.0


def plan_beat_shorts(
    tts_metadata: dict,
    beats: list[str],
    count: int = TEASER_COUNT,
    min_seconds: float = BEAT_MIN_SECONDS,
    max_seconds: float = BEAT_MAX_SECONDS,
) -> list[ShortPart]:
    """Mỗi beat -> một ShortPart bắt đầu đúng câu mở của đoạn trích, kéo dài
    30-55s trong cùng chương. Beat không dò được (hoặc chương quá ngắn) thì bị
    bỏ và phần thiếu được bù bằng trích đoạn rải đều kiểu cũ -- không bao giờ
    ra ít Short hơn trước chỉ vì Gemini trích sai một đoạn."""
    from scripts.text_tools import locate_quote, span_within

    sentences = tts_metadata.get("sentences") or []
    if not sentences:
        raise ShortPlanError("Metadata TTS không có mốc câu (mảng 'sentences' thiếu hoặc rỗng).")
    headings = {c["index"]: c["heading"] for c in tts_metadata.get("chapters", [])}

    chosen: list[ShortPart] = []
    for beat in beats:
        if len(chosen) == count:
            break
        found = locate_quote(beat, sentences)
        if found is None:
            continue
        span = span_within(sentences, found[0], min_seconds, max_seconds, end_i=found[1])
        if span is None:
            continue
        i, j = span
        start, end = sentences[i]["start_seconds"], sentences[j]["end_seconds"]
        if any(start < p.source_end_seconds and end > p.source_start_seconds for p in chosen):
            continue
        chapter = sentences[i]["chapter_index"]
        part = _build_part(0, chapter, headings.get(chapter, ""), sentences[i : j + 1])
        part.hook_line = sentences[i]["text"].strip()
        chosen.append(part)

    if len(chosen) < count:
        for teaser in plan_teasers(tts_metadata, count):
            if len(chosen) == count:
                break
            if any(
                teaser.source_start_seconds < p.source_end_seconds
                and teaser.source_end_seconds > p.source_start_seconds
                for p in chosen
            ):
                continue
            chosen.append(teaser)

    chosen.sort(key=lambda p: p.source_start_seconds)
    return _renumber(chosen)


def short_title_from_line(line: str, max_chars: int = 50) -> str:
    """Tiêu đề Short = câu thoại mở đầu (<= 50 ký tự, cắt ở ranh giới từ) + #Shorts."""
    line = " ".join(line.split()).strip()
    if len(line) > max_chars:
        cut = line[: max_chars - 1]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        line = cut.rstrip(" ,.;:-–—") + "…"
    return f"{line} #Shorts"
