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
            chapters=[
                Chapter(index=c["index"], heading=c["heading"], text=c["text"])
                for c in data["chapters"]
            ],
        )
