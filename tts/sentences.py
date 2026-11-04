# tts/sentences.py
"""Tách văn bản chương thành danh sách câu.

Tách thuần theo dấu kết câu (`.` `!` `?` `…`), không gộp câu ngắn lại với nhau
— mỗi câu đọc riêng để stage 2 ghi được mốc thời gian theo câu.
"""

import re

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENTENCE_END.split(text.strip()) if p.strip()]
