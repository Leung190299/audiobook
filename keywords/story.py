"""Kiểm tra và lưu bản ghi truyện do stage 0 sinh ra vào kho phụ
data/story_bank.auto.json (gitignore; id từ 1000 để không đụng kho biên tập)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from keywords.prompts import BANNED_TITLE_STARTS, PREMISE_WORDS, TITLE_MAX_CHARS
from keywords.scoring import content_words, phrase_in_text
from scripts.prompts import MAX_HOOK_WORDS, MAX_QUESTION_WORDS
from scripts.story_bank import AUTO_ID_START, DEFAULT_AUTO_BANK_PATH
from scripts.topics import TOPICS

REQUIRED = ("topic", "title", "hook", "premise", "twist", "comment_question", "thumb_keywords")


def validate_story(data: dict, phrase: str, existing_titles: list[str]) -> list[str]:
    """Danh sách lỗi (rỗng = đạt). Mỗi lỗi là một câu để gửi lại cho mô hình."""
    problems = []
    for key in REQUIRED:
        if not data.get(key):
            problems.append(f"thiếu trường {key}")
    if problems:
        return problems
    title = " ".join(str(data["title"]).split())
    if len(title) > TITLE_MAX_CHARS:
        problems.append(f"title dài {len(title)} ký tự, tối đa {TITLE_MAX_CHARS}")
    if title.lower().startswith(BANNED_TITLE_STARTS):
        problems.append("title không được mở đầu bằng 'Tôi', 'Trọng Sinh' hay 'Cô Út'")
    if not phrase_in_text(phrase, title, slack=1 if len(content_words(phrase)) > 3 else 0):
        problems.append(f"title phải chứa các từ chính của từ khóa '{phrase}'")
    if title.lower() in {t.lower() for t in existing_titles}:
        problems.append("title trùng một truyện đã có, đặt tên khác")
    # Tiêu đề viết hoa mọi chữ nên không dò xưng hô được; lấy tên từ premise/twist
    # (ở đó 'bà Phượng' viết thường xưng hô) rồi xem tên nào lọt vào tiêu đề.
    body_names = _proper_names(f"{data['premise']} {data['twist']}")
    title_words = set(re.findall(r"[A-ZÀ-Ỹ][a-zà-ỹ]+", title))
    leaked = [n for n in body_names if n in title_words]
    if leaked:
        problems.append(
            f"title không đặt tên riêng nhân vật ({', '.join(leaked)}), nhân vật chính xưng 'Tôi' như mọi truyện của kênh"
        )
    if str(data["topic"]) not in TOPICS:
        problems.append(f"topic phải là một trong: {', '.join(TOPICS)}")
    if len(str(data["hook"]).split()) > MAX_HOOK_WORDS:
        problems.append(f"hook dài quá {MAX_HOOK_WORDS} từ")
    if len(str(data["comment_question"]).split()) > MAX_QUESTION_WORDS:
        problems.append(f"comment_question dài quá {MAX_QUESTION_WORDS} từ")
    lo, hi = PREMISE_WORDS
    for key in ("premise", "twist"):
        n = len(str(data[key]).split())
        if not lo - 20 <= n <= hi + 40:  # nới nhẹ: Gemini đếm từ khác mình
            problems.append(f"{key} có {n} từ, cần {lo}-{hi} từ")
    kws = data["thumb_keywords"]
    if not isinstance(kws, list) or not kws or not all(isinstance(k, str) and k in title for k in kws):
        problems.append("thumb_keywords phải là 1 cụm nằm nguyên văn trong title")
    elif not all(2 <= len(k.split()) <= 4 for k in kws):
        problems.append("thumb_keywords phải dài 2-4 chữ (thumbnail chỉ tô màu một cụm ngắn)")
    # Tên riêng trong hook phải có trong truyện: lượt 10/11 hook gọi 'bà Loan' còn
    # premise là 'ông bà Tám' -- stage 1 sẽ viết chương 1 theo hook rồi lạc tên.
    body = f"{data['premise']} {data['twist']}"
    for name in _proper_names(str(data["hook"])):
        if name not in body:
            problems.append(f"tên '{name}' trong hook không xuất hiện trong premise/twist; dùng đúng tên nhân vật")
    for key in ("premise", "twist", "hook", "comment_question"):
        if '"' in str(data[key]):
            problems.append(f"{key} có dấu nháy kép, dùng nháy đơn")
    return problems


# (?i:...) chỉ bỏ phân biệt hoa/thường cho từ xưng hô ('Bà Loan' đầu câu), tên
# riêng phía sau vẫn phải viết hoa.
_NAME_PREFIX = r"(?i:ông|bà|chị|anh|cô|chú|bác|thím|dì|cậu|mợ|mẹ|bố|em|thằng|con)"


# Từ hay đứng đầu câu thoại sau xưng hô, viết hoa nhưng không phải tên: "Con Đừng
# hòng", "Mày Trả lại". Bắt nhầm thì mô hình bị hỏi lại vô ích (lượt 10/11: 'đừng').
_NOT_NAMES = {
    "đừng", "đi", "ơi", "này", "đây", "kia", "không", "có", "là", "mày", "tao", "nó", "ta",
    "chúng", "cứ", "hãy", "thôi", "đã", "sẽ", "phải", "về", "ra", "vào", "ở", "làm", "nói",
    "đưa", "ký", "trả", "cút", "im", "nghe", "biết", "muốn", "định", "dám", "mà", "thì",
}


def _proper_names(text: str) -> list[str]:
    """Tên riêng đi sau từ xưng hô ('bà Loan', 'chị Mai'), bỏ từ đầu câu/đầu thoại."""
    names = []
    for match in re.finditer(rf"\b{_NAME_PREFIX}\s+([A-ZÀ-Ỹ][a-zà-ỹ]+)", text):
        name = match.group(1)
        if name.lower() in _NOT_NAMES or name in names:
            continue
        names.append(name)
    return names


def to_bank_record(data: dict, story_id: int, phrase: str) -> dict:
    title = " ".join(str(data["title"]).split())
    return {
        "id": story_id,
        "topic": str(data["topic"]),
        "series": "Truyện lẻ",
        "title": title,
        "premise": str(data["premise"]).strip(),
        "twist": str(data["twist"]).strip(),
        "hook": str(data["hook"]).strip(),
        "comment_question": str(data["comment_question"]).strip(),
        "thumb_keywords": [str(k) for k in data["thumb_keywords"]][:1],
        "timing": "Quanh năm",
        "priority": "A",
        "publish_date": None,
        "keyword": phrase,
    }


def load_auto_stories(path: Path = DEFAULT_AUTO_BANK_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = data.get("stories", [])
    return [row for row in data if isinstance(row, dict)]


def next_auto_id(path: Path = DEFAULT_AUTO_BANK_PATH) -> int:
    ids = [int(r["id"]) for r in load_auto_stories(path) if "id" in r]
    return max([AUTO_ID_START - 1, *ids]) + 1


def append_auto_story(record: dict, path: Path = DEFAULT_AUTO_BANK_PATH) -> Path:
    rows = load_auto_stories(path)
    rows.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stories": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def slugify(text: str) -> str:
    from keywords.scoring import strip_accents

    return re.sub(r"[^a-z0-9]+", "-", strip_accents(text)).strip("-")[:60]
