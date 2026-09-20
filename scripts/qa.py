import re

from scripts.models import Script

MIN_WORDS = 9000
# Đo trên 25 kịch bản đã dựng: dài nhất 13.982 từ, tức trần 14.000 cũ nằm ngay
# đỉnh phân bố tự nhiên. Hai lượt chạy đã chết vì vượt trần 51 và 264 từ, mỗi
# lần mất 3-4 phút sinh kịch bản. 15.000 từ ra khoảng 58 phút audio, vẫn nằm
# trong tầm bình thường của video dài.
MAX_WORDS = 15000
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

    if not (MIN_WORDS <= script.word_count <= MAX_WORDS):
        errors.append(
            f"Độ dài {script.word_count} từ nằm ngoài khoảng {MIN_WORDS}-{MAX_WORDS}."
        )

    if not (MIN_CHAPTERS <= len(script.chapters) <= MAX_CHAPTERS):
        errors.append(
            f"Số chương {len(script.chapters)} nằm ngoài khoảng {MIN_CHAPTERS}-{MAX_CHAPTERS}."
        )

    for chapter in script.chapters:
        if looks_like_refusal(chapter.text):
            errors.append(
                f"Chương {chapter.index} là lời từ chối của Gemini, không phải nội dung truyện."
            )
        elif chapter.word_count < MIN_CHAPTER_WORDS:
            errors.append(
                f"Chương {chapter.index} chỉ có {chapter.word_count} từ, dưới sàn {MIN_CHAPTER_WORDS}."
            )

    lowered_text = script.full_text.lower()
    for term in BANNED_TERMS:
        if term.lower() in lowered_text:
            errors.append(f"Nội dung chứa từ khoá bị cấm: '{term}'.")

    if errors:
        raise ScriptQAError("; ".join(errors))
