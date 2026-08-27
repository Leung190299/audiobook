from scripts.models import Script

MIN_WORDS = 9000
# Đo trên 25 kịch bản đã dựng: dài nhất 13.982 từ, tức trần 14.000 cũ nằm ngay
# đỉnh phân bố tự nhiên. Hai lượt chạy đã chết vì vượt trần 51 và 264 từ, mỗi
# lần mất 3-4 phút sinh kịch bản. 15.000 từ ra khoảng 58 phút audio, vẫn nằm
# trong tầm bình thường của video dài.
MAX_WORDS = 15000
MIN_CHAPTERS = 14
MAX_CHAPTERS = 18

BANNED_TERMS = [
    "phù mỏ audio",
]


class ScriptQAError(Exception):
    pass


def validate_script(script: Script) -> None:
    errors = []

    if not (MIN_WORDS <= script.word_count <= MAX_WORDS):
        errors.append(
            f"Độ dài {script.word_count} từ nằm ngoài khoảng {MIN_WORDS}-{MAX_WORDS}."
        )

    if not (MIN_CHAPTERS <= len(script.chapters) <= MAX_CHAPTERS):
        errors.append(
            f"Số chương {len(script.chapters)} nằm ngoài khoảng {MIN_CHAPTERS}-{MAX_CHAPTERS}."
        )

    lowered_text = script.full_text.lower()
    for term in BANNED_TERMS:
        if term.lower() in lowered_text:
            errors.append(f"Nội dung chứa từ khoá bị cấm: '{term}'.")

    if errors:
        raise ScriptQAError("; ".join(errors))
