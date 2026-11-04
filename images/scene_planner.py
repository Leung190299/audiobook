"""Chia mỗi chương thành các cảnh ~50 giây theo mốc câu của stage 2.

Một ảnh gánh cả chương 3-4 phút là lý do video nhìn "đứng": đo tập 04/09, mỗi
ảnh đứng yên trung bình 202 giây. Cắt tại ranh giới câu để cảnh không đổi giữa
chừng một câu. Thuần tính toán -- không gọi Gemini hay mflux, nên test chạy
không cần cookie hay model.
"""

from dataclasses import dataclass

# Mục tiêu độ dài một cảnh. 50s là khoảng mắt còn thấy "mới đổi cảnh" mà stage 3
# chưa quá chậm: 16 chương ~200s -> ~64 ảnh -> ~50 phút với 44s/ảnh.
TARGET_SCENE_SECONDS = 50.0


class ScenePlanError(Exception):
    pass


@dataclass(frozen=True)
class ScenePlan:
    chapter_index: int
    number: int  # 1-based trong chương
    # Trục thời gian toàn tập. Các cảnh của một chương phủ kín chương: cảnh 1 bắt
    # đầu đúng start của chương, cảnh cuối kết thúc đúng end, cảnh sau bắt đầu
    # đúng lúc cảnh trước kết thúc. Stage 4 và 7 dựa vào bất biến này.
    start_seconds: float
    end_seconds: float
    text: str  # các câu trong cảnh ghép lại, để Gemini tả bối cảnh


def plan_scenes(
    tts_metadata: dict, target_seconds: float = TARGET_SCENE_SECONDS
) -> list[ScenePlan]:
    sentences = tts_metadata.get("sentences")
    if not sentences:
        raise ScenePlanError(
            "Metadata TTS không có mốc câu (mảng 'sentences' thiếu hoặc rỗng). "
            "Tập này dựng trước khi stage 2 biết ghi mốc câu -- muốn chia cảnh, "
            "hãy chạy lại stage 2."
        )

    by_chapter: dict[int, list[dict]] = {}
    for sentence in sentences:
        by_chapter.setdefault(sentence["chapter_index"], []).append(sentence)

    plans: list[ScenePlan] = []
    for chapter in tts_metadata["chapters"]:
        index = chapter["index"]
        chapter_sentences = by_chapter.get(index)
        if not chapter_sentences:
            raise ScenePlanError(
                f"Chương {index} không có câu nào trong metadata TTS."
            )
        plans.extend(
            _split_chapter(
                index,
                chapter["start_seconds"],
                chapter["end_seconds"],
                chapter_sentences,
                target_seconds,
            )
        )
    return plans


def _split_chapter(
    index: int,
    chapter_start: float,
    chapter_end: float,
    sentences: list[dict],
    target_seconds: float,
) -> list[ScenePlan]:
    duration = chapter_end - chapter_start
    wanted = max(1, round(duration / target_seconds))
    wanted = min(wanted, len(sentences))  # mỗi cảnh ít nhất một câu

    # Duyệt một lượt, đóng cảnh khi câu vừa thêm chạm mốc chia đều kế tiếp.
    # Hai ràng buộc: không đóng cảnh cuối (nó ôm phần còn lại), và phải đóng
    # ngay khi số câu còn lại chỉ vừa đủ cho số cảnh còn lại.
    groups: list[list[dict]] = []
    current: list[dict] = []
    for position, sentence in enumerate(sentences):
        current.append(sentence)
        scenes_left = wanted - len(groups)  # kể cả cảnh đang mở
        sentences_left = len(sentences) - position - 1
        ideal_end = chapter_start + duration * (len(groups) + 1) / wanted
        must_close = sentences_left == scenes_left - 1
        if scenes_left > 1 and (sentence["end_seconds"] >= ideal_end or must_close):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    plans = []
    for number, group in enumerate(groups, start=1):
        is_first = number == 1
        is_last = number == len(groups)
        start = chapter_start if is_first else group[0]["start_seconds"]
        end = chapter_end if is_last else groups[number][0]["start_seconds"]
        plans.append(
            ScenePlan(
                chapter_index=index,
                number=number,
                start_seconds=start,
                end_seconds=end,
                text=" ".join(s["text"] for s in group),
            )
        )
    return plans
