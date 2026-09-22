# metadata/episodes.py
"""Metadata YouTube cho TỪNG TẬP từ một bộ SEO chung của truyện.

Mỗi tập có tiêu đề riêng ("<tiêu đề> | Tập 2/3"), mô tả riêng (dòng đầu là hook,
mốc chương theo trục của tập, câu hỏi bình luận, chỗ trống cho link tập khác),
và một bình luận ghim. Tất cả từ MỘT lần gọi Gemini (seo_generator) -- ba tập
cùng từ khoá, cùng tag, chỉ khác số tập và mốc chương.

Vòng lặp tương tác mà đánh giá kênh 22/09 chỉ ra là thiếu hẳn (0 bình luận):
câu hỏi ở cuối mô tả + bình luận ghim cùng câu hỏi đó. Người nghe trả lời được
bằng một câu ngắn thì mới gõ.
"""

import json
from pathlib import Path

from metadata.chapters import _format_timestamp
from metadata.seo_generator import SeoCopy

CHANNEL_CTA = "👉 Đăng ký kênh để không bỏ lỡ tập mới mỗi ngày!"
# Chỗ trống mà upload/episode_cli.py thay bằng link thật sau khi đăng. Dùng
# hằng số để hai bên không trôi nhau (bài học từ FULL_EPISODE_PLACEHOLDER của
# shorts).
NEXT_EPISODE_PLACEHOLDER = "▶️ Tập tiếp theo: (link sẽ cập nhật khi tập sau lên sóng)"
PLAYLIST_PLACEHOLDER = "📚 Nghe trọn bộ theo thứ tự: (link playlist)"
DEFAULT_COMMENT_QUESTION = "Nếu là bạn, bạn sẽ làm gì ở tình huống này? Kể mình nghe dưới bình luận nhé!"


def episode_title(story_title: str, number: int, total: int) -> str:
    return f"{story_title} | Tập {number}/{total}"


def episode_chapter_lines(chapters: list[dict]) -> list[str]:
    """[{'heading', 'start_seconds'}] (từ manifest stage 4) -> ['0:00 Mở đầu', ...]."""
    return [f"{_format_timestamp(c['start_seconds'])} {c['heading']}" for c in chapters]


def pinned_comment(comment_question: str, number: int, total: int) -> str:
    question = comment_question or DEFAULT_COMMENT_QUESTION
    if number < total:
        tail = f"Tập {number + 1} lên sóng 20h mai — đăng ký và bật chuông để không bỏ lỡ 🔔"
    else:
        tail = "Hết truyện rồi! Bạn muốn nghe truyện kiểu gì tiếp theo? Comment cho mình biết 👇"
    return f"❓ {question}\n{tail}"


def build_episode_description(
    seo: SeoCopy,
    hook: str,
    comment_question: str,
    number: int,
    total: int,
    chapter_lines: list[str],
) -> str:
    parts: list[str] = []
    if hook:
        parts.append(f"{hook}")
    parts.append(f"Tập {number}/{total}. {seo.description_draft}".strip())
    parts.append(f"❓ {comment_question or DEFAULT_COMMENT_QUESTION}")
    links = [PLAYLIST_PLACEHOLDER]
    if number < total:
        links.append(NEXT_EPISODE_PLACEHOLDER)
    parts.append("\n".join(links))
    parts.append(CHANNEL_CTA)
    parts.append("Chương:\n" + "\n".join(chapter_lines))
    if seo.hashtags:
        parts.append(" ".join(seo.hashtags))
    return "\n\n".join(parts)


def save_episode_metadata(
    stem: str,
    number: int,
    total: int,
    title: str,
    description: str,
    tags: list[str],
    hashtags: list[str],
    pinned: str,
    video_filename: str,
    thumbnail_filename: str | None,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ep_stem = f"{stem}-ep-{number:02d}"
    txt_path = output_dir / f"{ep_stem}.txt"
    txt_path.write_text(
        f"TIÊU ĐỀ:\n{title}\n\n"
        f"MÔ TẢ:\n{description}\n\n"
        f"TAGS:\n{', '.join(tags)}\n\n"
        f"HASHTAGS:\n{' '.join(hashtags)}\n\n"
        f"BÌNH LUẬN GHIM:\n{pinned}\n\n"
        f"TÊN FILE VIDEO (đã đổi):\n{video_filename}\n"
        + (f"\nTHUMBNAIL:\n{thumbnail_filename}\n" if thumbnail_filename else ""),
        encoding="utf-8",
    )
    json_path = output_dir / f"{ep_stem}.json"
    json_path.write_text(
        json.dumps(
            {
                "episode_number": number,
                "episode_total": total,
                "title": title,
                "description": description,
                "tags": tags,
                "hashtags": hashtags,
                "pinned_comment": pinned,
                "video_filename": video_filename,
                "thumbnail_filename": thumbnail_filename,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return txt_path, json_path
