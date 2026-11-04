from dataclasses import dataclass, field

# Chương đầu kể trước đoạn gay cấn nhất rồi dẫn về đầu truyện (26/10). Mọi bước
# dò đoạn trích (cold open, short, TikTok) phải bỏ chương này: nó kể lại cao trào
# nên dò sẽ trúng bản kể trước thay vì cao trào thật.
PROLOGUE_HEADING = "Mở đầu"


def without_prologue(tts_metadata: dict) -> dict:
    """Bản sao metadata stage 2 đã bỏ chương 'Mở đầu' và các câu của nó."""
    skip = {c["index"] for c in tts_metadata.get("chapters", []) if c.get("heading") == PROLOGUE_HEADING}
    if not skip:
        return tts_metadata
    return {
        **tts_metadata,
        "chapters": [c for c in tts_metadata.get("chapters", []) if c["index"] not in skip],
        "sentences": [s for s in tts_metadata.get("sentences", []) if s["chapter_index"] not in skip],
    }


@dataclass
class Chapter:
    index: int
    heading: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class Script:
    trope: str
    title: str
    chapters: list[Chapter] = field(default_factory=list)
    # Hai trường Gemini sinh cùng dàn ý (từ 22/09/2026), dùng cho vòng lặp
    # tương tác: `hook` là một câu tóm cú lật/nỗi oan lớn nhất (dòng đầu mô tả,
    # chữ trên card mở đầu); `comment_question` là câu hỏi cụ thể đặt cho người
    # nghe ở cuối tập và trong bình luận ghim. Rỗng với kịch bản dựng trước ngày
    # đó -- mọi nơi dùng phải chịu được chuỗi rỗng.
    hook: str = ""
    comment_question: str = ""
    # Các trường từ 24/09/2026 (chủ đề + định dạng FULL). Rỗng với kịch bản cũ
    # hoặc kịch bản dựng từ trope/trend -- mọi nơi dùng phải chịu được rỗng.
    topic: str = ""  # id trong scripts/topics.py
    format: str = ""  # "full" | "episodes"
    setting: str = ""  # bối cảnh đã chọn từ registry
    premise: str = ""  # 1 câu tóm tắt tình huống, dùng chặn trùng 30 ngày
    # Chỉ có ở chế độ kho (data/story_bank.json): id truyện để lần vết ở
    # index.jsonl/story_bank_state, và tên series cho dòng mô tả.
    story_id: int = 0
    series: str = ""
    thumb_text: str = ""  # chữ trên thumbnail (<= 12 chữ)
    thumb_keywords: list[str] = field(default_factory=list)  # chuỗi con của thumb_text
    # Trích NGUYÊN VĂN 3 đoạn buồn cười/sảng nhất (stage 1 hỏi sau khi viết xong
    # các chương) -- stage 4 lấy đoạn đầu làm cold open, stage 7 làm 3 Shorts.
    short_beats: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(chapter.word_count for chapter in self.chapters)

    @property
    def full_text(self) -> str:
        return "\n\n".join(chapter.text for chapter in self.chapters)

    def to_dict(self) -> dict:
        return {
            "trope": self.trope,
            "title": self.title,
            "hook": self.hook,
            "comment_question": self.comment_question,
            "topic": self.topic,
            "format": self.format,
            "setting": self.setting,
            "premise": self.premise,
            "thumb_text": self.thumb_text,
            "thumb_keywords": list(self.thumb_keywords),
            # Stage 6 nạp lại kịch bản từ JSON: thiếu hai trường này thì mô tả
            # mất dòng series và publishAt tính theo truyện số 0 (sai ngày).
            "story_id": self.story_id,
            "series": self.series,
            "short_beats": list(self.short_beats),
            "chapters": [
                {"index": c.index, "heading": c.heading, "text": c.text}
                for c in self.chapters
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Script":
        return cls(
            trope=data["trope"],
            title=data["title"],
            hook=data.get("hook", "") or "",
            comment_question=data.get("comment_question", "") or "",
            topic=data.get("topic", "") or "",
            format=data.get("format", "") or "",
            setting=data.get("setting", "") or "",
            premise=data.get("premise", "") or "",
            story_id=int(data.get("story_id") or 0),
            series=data.get("series", "") or "",
            thumb_text=data.get("thumb_text", "") or "",
            thumb_keywords=list(data.get("thumb_keywords") or []),
            short_beats=list(data.get("short_beats") or []),
            chapters=[
                Chapter(index=c["index"], heading=c["heading"], text=c["text"])
                for c in data["chapters"]
            ],
        )
