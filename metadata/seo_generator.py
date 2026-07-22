import os
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Script


class SeoGenerationError(Exception):
    pass


@dataclass
class SeoCopy:
    title: str
    description_draft: str
    tags: list[str]
    hashtags: list[str]


_LABELS = ("TITLE", "DESCRIPTION", "TAGS", "HASHTAGS")


def build_seo_prompt(script: Script) -> str:
    headings = "\n".join(f"- {c.heading}" for c in script.chapters)
    return (
        "Bạn là chuyên gia SEO YouTube. Dựa trên thông tin truyện audio tiếng Việt sau, "
        "hãy sinh nội dung SEO cho video YouTube.\n\n"
        f"Tiêu đề truyện: {script.title}\n"
        f"Thể loại: {script.trope}\n"
        f"Danh sách chương:\n{headings}\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "TITLE: <tiêu đề video YouTube, tối đa 70 ký tự, chứa từ khóa chính trong "
        "60 ký tự đầu, hấp dẫn nhưng không giật tít sai sự thật>\n"
        "DESCRIPTION: <mô tả video 200-300 từ bằng tiếng Việt, câu đầu tiên (khoảng "
        "150 ký tự) chứa từ khóa chính, giới thiệu tự nhiên nội dung truyện, không kể "
        "hết cốt truyện>\n"
        "TAGS: <10-15 tag phân tách bằng dấu phẩy, tag đầu tiên là từ khóa chính xác nhất>\n"
        "HASHTAGS: <2-3 hashtag có dấu #, phân tách bằng khoảng trắng>"
    )


def _parse_label(text: str, label: str) -> str:
    marker = f"{label}:"
    start = text.find(marker)
    if start == -1:
        raise SeoGenerationError(f"Gemini không trả về nhãn '{label}:' trong output SEO")
    start += len(marker)

    next_positions = [
        pos
        for other in _LABELS
        if other != label
        for pos in [text.find(f"\n{other}:", start)]
        if pos != -1
    ]
    end = min(next_positions) if next_positions else len(text)

    value = text[start:end].strip()
    if not value:
        raise SeoGenerationError(f"Gemini trả về nhãn '{label}:' rỗng")
    return value


async def generate_seo_copy(
    script: Script, client: "GeminiClient | None" = None
) -> SeoCopy:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    try:
        response = await client.generate_content(build_seo_prompt(script))
    except (GeminiError, APIError, AuthError) as exc:
        raise SeoGenerationError(f"Gemini lỗi khi sinh nội dung SEO: {exc}") from exc

    text = response.text.strip()

    title = _parse_label(text, "TITLE")
    description_draft = _parse_label(text, "DESCRIPTION")
    tags_raw = _parse_label(text, "TAGS")
    hashtags_raw = _parse_label(text, "HASHTAGS")

    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    hashtags = [h.strip() for h in hashtags_raw.split() if h.strip()]

    return SeoCopy(
        title=title, description_draft=description_draft, tags=tags, hashtags=hashtags
    )
