import warnings


def _format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_chapter_lines(tts_metadata: dict) -> list[str]:
    chapters = sorted(tts_metadata["chapters"], key=lambda c: c["index"])

    if chapters and chapters[0]["start_seconds"] != 0.0:
        warnings.warn(
            "Chương đầu tiên không bắt đầu tại 0:00 — YouTube yêu cầu chương đầu "
            "phải là 0:00 để hiển thị dưới dạng 'Khoảnh khắc chính'.",
            stacklevel=2,
        )

    return [
        f"{_format_timestamp(c['start_seconds'])} {c['heading']}"
        for c in chapters
    ]
