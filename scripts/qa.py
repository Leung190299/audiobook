from scripts.models import Script

MIN_WORDS = 5000
MAX_WORDS = 8000
MIN_CHAPTERS = 6
MAX_CHAPTERS = 10

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
        if term in lowered_text:
            errors.append(f"Nội dung chứa từ khoá bị cấm: '{term}'.")

    if errors:
        raise ScriptQAError("; ".join(errors))
