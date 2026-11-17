import re

from scripts.models import PROLOGUE_HEADING, Script

MIN_WORDS = 9000
# Đo trên 25 kịch bản đã dựng: dài nhất 13.982 từ, tức trần 14.000 cũ nằm ngay
# đỉnh phân bố tự nhiên. Hai lượt chạy đã chết vì vượt trần 51 và 264 từ, mỗi
# lần mất 3-4 phút sinh kịch bản. 15.000 từ ra khoảng 58 phút audio, vẫn nằm
# trong tầm bình thường của video dài.
MAX_WORDS = 15000
# Bản FULL 35-45 phút (24/09/2026): sàn = số từ cho 35 phút ở tốc độ đọc của
# mô hình đang viết (scripts/prompts.py words_per_second), chừa ~5% viết hụt.
# Gemini: ~8.400; Claude đọc chậm hơn nên ~7.500.
FULL_MIN_SLACK = 0.95
FULL_MAX_SLACK = 1.25
MIN_CHAPTERS = 14
# Sàn độ dài MỖI chương. Tổng từ không đủ để bắt lỗi: tập 05/09 có chương 4 chỉ
# 29 từ — nguyên văn lời từ chối của Gemini — mà tổng vẫn hơn 12.000 nên QA cũ
# cho qua, và TTS đọc luôn câu "tôi chỉ là một mô hình ngôn ngữ" vào tập.
# Chương thật đo được 740-1.170 từ; 300 chặn được cả từ chối lẫn chương cụt.
MIN_CHAPTER_WORDS = 300
MAX_CHAPTERS = 18

# Từ tục / miệt thị không được xuất hiện trong TIÊU ĐỀ. Tập 20/09 thật: Gemini
# đặt "Bà Chó Sủa Mỏ Hỗn Hóa Ra Lại Là Đồng Minh" -- thân truyện sạch, chỉ tiêu
# đề hỏng, và tiêu đề in lên card cuối 5 short lẫn metadata. So khớp nguyên từ
# (không lấy "chó" trong "chống") vì tiếng Việt có dấu, \b của regex vẫn đủ.
OFFENSIVE_TITLE_TERMS = (
    "chó", "đĩ", "điếm", "con hoang", "khốn nạn", "súc vật", "mặt lồn", "cặc",
    "đụ", "địt", "ngu si", "đần độn", "thằng khốn", "con khốn",
)

BANNED_TERMS = [
    "phù mỏ audio",
]


# Câu mở đầu điển hình của lời từ chối. Chỉ xét phần đầu văn bản để "tôi không
# thể tin nổi" giữa truyện không bị bắt nhầm.
REFUSAL_MARKERS = (
    "mô hình ngôn ngữ",
    "language model",
    "tôi không thể giúp",
    "tôi không thể tạo",
    "tôi không thể hỗ trợ",
    "tôi không thể đáp ứng",
    "xin lỗi, tôi không thể",
    "i can't help",
    "i cannot help",
    "i can't assist",
    "i'm unable to",
    "i am unable to",
)


class ScriptQAError(Exception):
    pass


def looks_like_refusal(text: str) -> bool:
    head = text.strip().lower()[:200]
    return any(marker in head for marker in REFUSAL_MARKERS)


def title_problem(title: str) -> str | None:
    lowered = title.lower()
    for term in OFFENSIVE_TITLE_TERMS:
        if re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", lowered):
            return f"Tiêu đề chứa từ không dùng được trên kênh: '{term}'."
    return None


def validate_script(script: Script) -> None:
    errors = []

    if problem := title_problem(script.title):
        errors.append(problem)

    if script.format == "full":
        from scripts.prompts import FULL_CHAPTERS_RANGE, full_words_range

        lo, hi = full_words_range()
        min_words = int(lo * FULL_MIN_SLACK)
        # Trần cũng theo mục tiêu phút: đánh giá 17/11 -- đừng kéo cho đủ 42 phút.
        max_words = int(hi * FULL_MAX_SLACK)
        # +1 chương cho đoạn "Mở đầu" nếu AUDIOBOOK_PROLOGUE bật.
        min_chapters, max_chapters = FULL_CHAPTERS_RANGE[0], FULL_CHAPTERS_RANGE[1] + 1
    else:
        min_words, max_words = MIN_WORDS, MAX_WORDS
        min_chapters, max_chapters = MIN_CHAPTERS, MAX_CHAPTERS
    if not (min_words <= script.word_count <= max_words):
        errors.append(
            f"Độ dài {script.word_count} từ nằm ngoài khoảng {min_words}-{max_words}."
        )

    if not (min_chapters <= len(script.chapters) <= max_chapters):
        errors.append(
            f"Số chương {len(script.chapters)} nằm ngoài khoảng {min_chapters}-{max_chapters}."
        )

    for chapter in script.chapters:
        if looks_like_refusal(chapter.text):
            errors.append(
                f"Chương {chapter.index} là lời từ chối của Gemini, không phải nội dung truyện."
            )
        elif chapter.word_count < MIN_CHAPTER_WORDS and chapter.heading != PROLOGUE_HEADING:
            errors.append(
                f"Chương {chapter.index} chỉ có {chapter.word_count} từ, dưới sàn {MIN_CHAPTER_WORDS}."
            )

    # Hợp đồng với stage 5: từ khoá tô màu phải nằm nguyên văn trong chữ
    # thumbnail, nếu không compositor không biết tô chữ nào.
    for kw in script.thumb_keywords:
        if kw.lower() not in script.thumb_text.lower():
            errors.append(f"Từ khoá thumbnail '{kw}' không nằm trong thumb_text '{script.thumb_text}'.")

    lowered_text = script.full_text.lower()
    for term in BANNED_TERMS:
        if term.lower() in lowered_text:
            errors.append(f"Nội dung chứa từ khoá bị cấm: '{term}'.")

    if errors:
        raise ScriptQAError("; ".join(errors))
