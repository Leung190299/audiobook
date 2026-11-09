"""Dò kho: cụm từ khóa đã có truyện nào trong kho chưa dùng không."""

from __future__ import annotations

from scripts.story_bank import PRIORITY_ORDER, Story
from keywords.scoring import phrase_in_text


def find_bank_story(phrase: str, stories: list[Story], taken: set[int]) -> Story | None:
    """Truyện chưa dùng mà TIÊU ĐỀ mang đủ từ mang nghĩa của cụm; nhiều truyện thì
    theo ưu tiên A>B>C rồi id nhỏ. Chỉ so tiêu đề, không so premise: premise dài
    nên gần như cụm nào cũng 'có mặt' trong đó (thử 10/11: 'con rể ở nhà vợ' khớp
    nhầm truyện mẹ chồng dạy làm dâu)."""
    free = [s for s in stories if s.id not in taken and s.publish_date is None]
    hits = [s for s in free if phrase_in_text(phrase, s.title, slack=0)]
    for priority in PRIORITY_ORDER:
        same = [s for s in hits if s.priority == priority]
        if same:
            return min(same, key=lambda s: s.id)
    return None
