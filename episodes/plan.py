# episodes/plan.py
"""Chia một truyện N chương thành các tập 15-20 phút.

Đây là nguồn sự thật DUY NHẤT về ranh giới tập: stage 1 (prompt kịch bản) hỏi
nó để biết chương nào phải kết bằng cliffhanger, stage 4 (episodes) hỏi nó để
biết cắt audio ở đâu, stage 5/6 hỏi nó để đánh số thumbnail và metadata. Ba
nơi tự tính riêng thì sớm muộn lệch nhau -- kịch bản viết cliffhanger ở chương
5 mà video lại cắt ở chương 6.

Lý do chia tập (đo trên kênh 22/09/2026): video 40-58 phút chỉ giữ chân trung
bình 1:43 (~3%), nên YouTube không đề xuất; tập 15-20 phút với mở đầu cao trào
và kết cliffhanger là định dạng chuẩn của các kênh truyện audio đang lên. Cùng
một truyện, ba tập, ba lần được đề xuất, giờ xem qua playlist autoplay.

Với 16 chương (TARGET_CHAPTERS): 5 + 6 + 5 chương, mỗi chương ~3 phút đọc ->
~15 / ~18 / ~15 phút. Tập giữa dài hơn một chút vì đó là nơi truyện gài nhiều
xung đột nhất; hai tập đầu/cuối gọn để người nghe dễ bắt đầu và dễ kết thúc.
"""

from dataclasses import dataclass

# Số tập mỗi truyện. Không đọc từ config: đổi số này là đổi cả cấu trúc kịch
# bản (cliffhanger nằm ở đâu), nên phải là quyết định có chủ ý trong mã.
EPISODE_COUNT = 3


class EpisodePlanError(Exception):
    pass


@dataclass(frozen=True)
class EpisodeRange:
    number: int  # 1-based
    total: int
    first_chapter: int  # 1-based, bao gồm
    last_chapter: int  # 1-based, bao gồm

    @property
    def chapter_indices(self) -> range:
        return range(self.first_chapter, self.last_chapter + 1)

    @property
    def is_last(self) -> bool:
        return self.number == self.total

    @property
    def label(self) -> str:
        return f"Tập {self.number}/{self.total}"


def plan_episodes(chapter_count: int, episode_count: int = EPISODE_COUNT) -> list[EpisodeRange]:
    """Chia `chapter_count` chương thành `episode_count` tập liên tiếp.

    Chia gần đều; phần dư dồn vào các tập GIỮA trước (16 chương -> 5/6/5, 17 ->
    5/6/6, 14 -> 4/5/5... với 3 tập: dư 1 vào tập giữa, dư 2 vào tập giữa và
    tập cuối). Tập đầu luôn là tập ngắn nhất: người mới vào kênh cần thấy kết
    quả sớm.
    """
    if episode_count < 1:
        raise EpisodePlanError(f"Số tập phải >= 1, nhận {episode_count}")
    if chapter_count < episode_count:
        raise EpisodePlanError(
            f"Truyện chỉ có {chapter_count} chương, không chia được thành "
            f"{episode_count} tập (mỗi tập cần ít nhất một chương)."
        )

    base, extra = divmod(chapter_count, episode_count)
    sizes = [base] * episode_count
    # Rải phần dư từ tập thứ hai trở đi, tập đầu nhận sau cùng.
    order = list(range(1, episode_count)) + [0]
    for i in range(extra):
        sizes[order[i]] += 1

    episodes: list[EpisodeRange] = []
    first = 1
    for number, size in enumerate(sizes, start=1):
        last = first + size - 1
        episodes.append(
            EpisodeRange(number=number, total=episode_count, first_chapter=first, last_chapter=last)
        )
        first = last + 1
    return episodes


def cliffhanger_chapters(chapter_count: int, episode_count: int = EPISODE_COUNT) -> list[int]:
    """Các chương phải kết bằng cliffhanger: chương cuối của mọi tập trừ tập cuối."""
    return [ep.last_chapter for ep in plan_episodes(chapter_count, episode_count) if not ep.is_last]


def episode_of_chapter(chapter_index: int, episodes: list[EpisodeRange]) -> EpisodeRange:
    for ep in episodes:
        if ep.first_chapter <= chapter_index <= ep.last_chapter:
            return ep
    raise EpisodePlanError(f"Chương {chapter_index} không thuộc tập nào trong kế hoạch.")
