from dataclasses import dataclass, field


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
            thumb_text=data.get("thumb_text", "") or "",
            thumb_keywords=list(data.get("thumb_keywords") or []),
            short_beats=list(data.get("short_beats") or []),
            chapters=[
                Chapter(index=c["index"], heading=c["heading"], text=c["text"])
                for c in data["chapters"]
            ],
        )
