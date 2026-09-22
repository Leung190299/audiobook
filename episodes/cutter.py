# episodes/cutter.py
"""Tính mốc cắt audio cho từng tập từ metadata TTS: thuần số học, không đụng file.

Mỗi tập gồm ba khúc nối tiếp nhau trên trục thời gian của tập:

    [cold open ~20-35s] [nghỉ 1s] [thân tập: các chương của tập] [outro CTA ~6s]

Cold open (mở đầu bằng cao trào) là một đoạn CẮT LẠI từ chính chương cuối của
tập -- chương cliffhanger -- chiếu trước khi vào truyện, giống phim truyền hình
chiếu 30 giây gay cấn trước khi chạy tên phim. Không TTS thêm, không gọi Gemini:
audio đã có sẵn, chỉ chọn khoảng câu. Vì sao cần: video 40-58 phút của kênh giữ
chân trung bình 1:43, tức người nghe bỏ đi trước khi truyện kịp vào chuyện;
30 giây đầu phải là lý do để ở lại.

Đoạn cold open KHÔNG lấy những câu cuối của chương (câu cliffhanger): mời nghe
mà chiếu sẵn cú lật là tự phá tập.
"""

from dataclasses import dataclass

from episodes.plan import EpisodeRange

# Cold open dài trong khoảng này (giây). Ngắn hơn 12s thì chưa kịp hiểu chuyện
# gì đang xảy ra; dài hơn 35s thì thành xem trước cả chương.
COLD_OPEN_MIN_SECONDS = 12.0
COLD_OPEN_MAX_SECONDS = 35.0
# Bắt đầu chọn từ mốc này của chương cuối tập: 2/3 chương trở đi là lúc xung
# đột đã lên cao nhưng cú lật cuối chưa xảy ra.
COLD_OPEN_START_FRACTION = 0.62
# Số câu cuối chương không bao giờ đưa vào cold open (câu cliffhanger + câu dẫn).
COLD_OPEN_RESERVED_TAIL_SENTENCES = 3
# Khoảng lặng giữa cold open và thân tập; đủ để người nghe nhận ra "vào truyện".
COLD_OPEN_GAP_SECONDS = 1.0
# Card kết tập (kêu gọi đăng ký + tập sau) hiện bao lâu sau khi hết tiếng.
OUTRO_SECONDS = 6.0


class EpisodeCutError(Exception):
    pass


@dataclass(frozen=True)
class ColdOpen:
    source_start_seconds: float
    source_end_seconds: float
    chapter_index: int

    @property
    def duration_seconds(self) -> float:
        return self.source_end_seconds - self.source_start_seconds


@dataclass(frozen=True)
class EpisodeCut:
    episode: EpisodeRange
    body_source_start_seconds: float
    body_source_end_seconds: float
    cold_open: ColdOpen | None
    gap_seconds: float = COLD_OPEN_GAP_SECONDS
    outro_seconds: float = OUTRO_SECONDS

    @property
    def body_offset_seconds(self) -> float:
        """Mốc (trục tập) mà thân tập bắt đầu: sau cold open và khoảng nghỉ."""
        if self.cold_open is None:
            return 0.0
        return self.cold_open.duration_seconds + self.gap_seconds

    @property
    def body_duration_seconds(self) -> float:
        return self.body_source_end_seconds - self.body_source_start_seconds

    @property
    def outro_start_seconds(self) -> float:
        return self.body_offset_seconds + self.body_duration_seconds

    @property
    def total_seconds(self) -> float:
        return self.outro_start_seconds + self.outro_seconds

    def to_episode_time(self, source_seconds: float) -> float:
        """Đổi một mốc trong wav gốc (nằm trong thân tập) sang trục thời gian tập."""
        return source_seconds - self.body_source_start_seconds + self.body_offset_seconds


def plan_cuts(tts_metadata: dict, episodes: list[EpisodeRange]) -> list[EpisodeCut]:
    chapters_by_index = {c["index"]: c for c in tts_metadata.get("chapters", [])}
    sentences = tts_metadata.get("sentences") or []
    if not sentences:
        raise EpisodeCutError(
            "Metadata TTS không có mốc câu (mảng 'sentences' thiếu hoặc rỗng) -- tập "
            "này dựng trước khi stage 2 biết ghi mốc câu. Chạy lại stage 2 rồi thử lại."
        )

    cuts: list[EpisodeCut] = []
    for ep in episodes:
        for index in ep.chapter_indices:
            if index not in chapters_by_index:
                raise EpisodeCutError(
                    f"Metadata TTS thiếu chương {index} mà {ep.label} cần "
                    f"(chương {ep.first_chapter}–{ep.last_chapter})."
                )
        first = chapters_by_index[ep.first_chapter]
        last = chapters_by_index[ep.last_chapter]
        body_start = float(first["start_seconds"])
        body_end = float(last["end_seconds"])
        if body_end <= body_start:
            raise EpisodeCutError(
                f"{ep.label}: mốc chương không hợp lệ ({body_start}s → {body_end}s)."
            )

        last_chapter_sentences = [s for s in sentences if s["chapter_index"] == ep.last_chapter]
        cold_open = pick_cold_open(last_chapter_sentences, ep.last_chapter)

        cuts.append(
            EpisodeCut(
                episode=ep,
                body_source_start_seconds=body_start,
                body_source_end_seconds=body_end,
                cold_open=cold_open,
            )
        )
    return cuts


def pick_cold_open(
    chapter_sentences: list[dict],
    chapter_index: int,
    min_seconds: float = COLD_OPEN_MIN_SECONDS,
    max_seconds: float = COLD_OPEN_MAX_SECONDS,
) -> ColdOpen | None:
    """Chọn một dải câu liên tiếp trong chương làm cold open, hoặc None nếu
    chương quá ngắn để cắt được đoạn tử tế mà không đụng câu cuối.

    Thuật toán: bỏ `COLD_OPEN_RESERVED_TAIL_SENTENCES` câu cuối; trong phần còn
    lại, bắt đầu từ câu gần mốc 62% chương nhất, nối thêm câu kế tiếp chừng nào
    tổng còn <= max. Nếu chưa đủ min thì lùi điểm bắt đầu về trước từng câu.
    """
    usable = chapter_sentences[:-COLD_OPEN_RESERVED_TAIL_SENTENCES] if len(
        chapter_sentences
    ) > COLD_OPEN_RESERVED_TAIL_SENTENCES else []
    if not usable:
        return None

    chapter_start = chapter_sentences[0]["start_seconds"]
    chapter_end = chapter_sentences[-1]["end_seconds"]
    target = chapter_start + COLD_OPEN_START_FRACTION * (chapter_end - chapter_start)
    start_i = min(range(len(usable)), key=lambda i: abs(usable[i]["start_seconds"] - target))

    def window(i: int) -> tuple[float, float]:
        start = usable[i]["start_seconds"]
        end = usable[i]["end_seconds"]
        j = i
        while j + 1 < len(usable) and usable[j + 1]["end_seconds"] - start <= max_seconds:
            j += 1
            end = usable[j]["end_seconds"]
        return start, end

    start, end = window(start_i)
    while end - start < min_seconds and start_i > 0:
        start_i -= 1
        start, end = window(start_i)

    if end - start < min_seconds:
        return None
    return ColdOpen(
        source_start_seconds=float(start),
        source_end_seconds=float(end),
        chapter_index=chapter_index,
    )
