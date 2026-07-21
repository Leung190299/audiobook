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
            chapters=[
                Chapter(index=c["index"], heading=c["heading"], text=c["text"])
                for c in data["chapters"]
            ],
        )
