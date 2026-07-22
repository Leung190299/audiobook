import json
from datetime import datetime, timezone
from pathlib import Path

from metadata.seo_generator import SeoCopy

CHANNEL_CTA = "👉 Đăng ký kênh để không bỏ lỡ tập mới!"


def build_full_description(description_draft: str, chapter_lines: list[str]) -> str:
    chapters_block = "\n".join(chapter_lines)
    return f"{description_draft}\n\n{CHANNEL_CTA}\n\nChương:\n{chapters_block}"


def save_seo_metadata(
    trope: str,
    seo_copy: SeoCopy,
    chapter_lines: list[str],
    new_video_filename: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    full_description = build_full_description(seo_copy.description_draft, chapter_lines)

    txt_path = output_dir / f"{trope}-{timestamp}.txt"
    txt_content = (
        f"TIÊU ĐỀ:\n{seo_copy.title}\n\n"
        f"MÔ TẢ:\n{full_description}\n\n"
        f"TAGS:\n{', '.join(seo_copy.tags)}\n\n"
        f"HASHTAGS:\n{' '.join(seo_copy.hashtags)}\n\n"
        f"TÊN FILE VIDEO (đã đổi):\n{new_video_filename}\n"
    )
    txt_path.write_text(txt_content, encoding="utf-8")

    json_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {
        "trope": trope,
        "title": seo_copy.title,
        "description": full_description,
        "tags": seo_copy.tags,
        "hashtags": seo_copy.hashtags,
        "video_filename": new_video_filename,
    }
    json_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return txt_path, json_path
