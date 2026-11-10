"""Chấm điểm cụm từ khóa theo 4 cột 0–3 của doc "Quy trình v2" (08/11/2026):

- Cầu: người có gõ cụm này không (điểm gợi ý YouTube).
- View: kênh đối thủ làm cụm này có nổi hơn mặt bằng của họ không.
- Giọng: cụm có hợp giọng kênh (gia đình, đời thường, hài vả mặt) không.
- Mới: kênh mình đã làm cụm này chưa (tên truyện trong kho/đã đăng, cụm đã dùng).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from keywords.sources import CompetitorVideo

# Từ chức năng: không tính khi so khớp cụm với tiêu đề.
STOPWORDS = {
    "truyện", "audio", "nghe", "kể", "chuyện", "full", "hay", "mới", "nhất", "tập",
    "phần", "radio", "đêm", "khuya", "và", "của", "cho", "với", "là", "thì", "bị",
    "được", "có", "một", "cái", "những", "các", "tôi", "ta", "về",
}


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt để so khớp lỏng; 'đ' không tách được bằng NFD nên đổi tay."""
    text = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def content_words(phrase: str) -> list[str]:
    """Các từ mang nghĩa của cụm (bỏ 'truyện audio', bỏ từ chức năng), bỏ dấu."""
    words = re.findall(r"[0-9a-zA-ZÀ-ỹ]+", phrase.lower())
    return [strip_accents(w) for w in words if w not in STOPWORDS and len(w) > 1]


def phrase_in_text(phrase: str, text: str, slack: int = 1) -> bool:
    """Cụm 'có mặt' trong văn bản khi tất cả (trừ tối đa `slack`) từ mang nghĩa
    của nó xuất hiện. Dùng cho cả dò kho lẫn so với đối thủ."""
    words = content_words(phrase)
    if not words:
        return False
    haystack = set(re.findall(r"[0-9a-z]+", strip_accents(text)))
    missing = sum(1 for w in words if w not in haystack)
    # Cụm ≤4 từ phải đủ hết: 'mẹ chồng vàng' thiếu 'vàng' là truyện khác hẳn; thử
    # 10/11 cụm 5 từ thiếu 1 vẫn khớp nhầm tiêu đề đối thủ chỉ vì chung 'vợ', 'chồng'.
    allowed = slack if len(words) >= 5 else 0
    return missing <= allowed


_TITLE_NOISE = re.compile(
    r"\[[^\]]*\]|#\S+|\bsố\s*\d+\b|\btập\s*\d+\b|\btrọn bộ\b|\bfull\b|\bphần\s*\d+\b|\|",
    flags=re.IGNORECASE,
)


def clean_title(title: str, channel: str = "") -> str:
    """Bỏ phần không phải nội dung trong tên video đối thủ: tên kênh, 'SỐ 764',
    '[FULL]', hashtag, 'Tập 3'. Không bỏ thì 'Bắp Nhỏ Audio Số 764' khớp đủ
    'vợ nhỏ', 'số' của một cụm chẳng liên quan."""
    text = _TITLE_NOISE.sub(" ", title)
    for word in channel.split():
        if len(word) > 1:
            text = re.sub(rf"\b{re.escape(word)}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\baudio\b|\btruyện\b", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())


@dataclass
class Cluster:
    phrase: str
    demand: int = 0
    view: int = 0
    voice: int = 0
    novelty: int = 0
    evidence: list[str] = field(default_factory=list)  # tiêu đề đối thủ khớp
    suggest_score: float = 0.0

    @property
    def total(self) -> int:
        return self.demand + self.view + self.voice + self.novelty


def demand_level(score: float, best: float) -> int:
    """0–3 theo tỉ lệ với cụm mạnh nhất trong lượt quét."""
    if score <= 0 or best <= 0:
        return 0
    r = score / best
    return 3 if r >= 0.5 else 2 if r >= 0.2 else 1


def view_level(phrase: str, videos: list[CompetitorVideo]) -> tuple[int, list[str]]:
    hits = [v for v in videos if phrase_in_text(phrase, clean_title(v.title, v.channel))]
    if not hits:
        return 0, []
    best = max(v.ratio for v in hits)
    level = 1 if best < 1 else 2 if best < 2 else 3
    top = sorted(hits, key=lambda v: -v.ratio)[:3]
    return level, [f"{v.channel}: {v.title} (x{v.ratio:g})" for v in top]


def voice_level(phrase: str, blocklist: list[str], allowlist: list[str]) -> int:
    low = " " + " ".join(phrase.lower().split()) + " "
    for bad in blocklist:
        if f" {bad} " in low or (len(bad) > 3 and bad in low):
            return 0
    if any(good in low for good in allowlist):
        return 3
    return 1


def novelty_level(phrase: str, titles: list[str], used_recent: list[str]) -> int:
    norm = " ".join(phrase.lower().split())
    if norm in {" ".join(u.lower().split()) for u in used_recent}:
        return 0
    if any(phrase_in_text(phrase, t, slack=0) for t in titles):
        return 1
    return 3


def score_clusters(
    suggest_scores: dict[str, float],
    videos: list[CompetitorVideo],
    titles: list[str],
    used_recent: list[str],
    blocklist: list[str],
    allowlist: list[str],
) -> list[Cluster]:
    """Mọi cụm có ít nhất 2 từ mang nghĩa, xếp theo tổng điểm giảm dần."""
    best = max(suggest_scores.values(), default=0.0)
    out = []
    for phrase, sc in suggest_scores.items():
        if len(content_words(phrase)) < 2:
            continue
        view, evidence = view_level(phrase, videos)
        out.append(
            Cluster(
                phrase=phrase,
                demand=demand_level(sc, best),
                view=view,
                voice=voice_level(phrase, blocklist, allowlist),
                novelty=novelty_level(phrase, titles, used_recent),
                evidence=evidence,
                suggest_score=sc,
            )
        )
    return sorted(out, key=lambda c: (-c.total, -c.suggest_score, c.phrase))
