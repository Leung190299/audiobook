import os
import re
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Script


class SeoGenerationError(Exception):
    pass


# Tiêu đề truyện tối đa để còn chỗ cho " | Tập N/3" (10 ký tự) trong 70 ký tự
# hiển thị trọn trên mobile. Gemini vượt thì cắt ở ranh giới từ chứ không ném
# lỗi -- một tiêu đề 65 ký tự không đáng mất lượt chạy.
MAX_TITLE_CHARS = 60


def clip_title(title: str, max_chars: int = MAX_TITLE_CHARS) -> str:
    title = " ".join(title.split())
    if len(title) <= max_chars:
        return title
    cut = title[:max_chars]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:-–—|")


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
        + (f"Câu hook: {script.hook}\n" if script.hook else "")
        + f"Danh sách chương:\n{headings}\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "TITLE: <tiêu đề video YouTube, TỐI ĐA 60 KÝ TỰ (sẽ ghép thêm ' | Tập N/3' "
        "phía sau nên không được dài hơn), bắt đầu bằng cú lật/nỗi oan cụ thể "
        "(ví dụ 'Mẹ Chồng Quỳ Xin Con Dâu Trả Nợ'), KHÔNG mở bằng 'Truyện Audio:' "
        "hay tên thể loại, hấp dẫn nhưng không giật tít sai sự thật>\n"
        "DESCRIPTION: <mô tả video 200-300 từ bằng tiếng Việt, câu đầu tiên (khoảng "
        "150 ký tự) chứa từ khóa chính, giới thiệu tự nhiên nội dung truyện, không kể "
        "hết cốt truyện>\n"
        "TAGS: <10-15 tag phân tách bằng dấu phẩy, tag đầu tiên là từ khóa chính xác nhất>\n"
        "HASHTAGS: <2-3 hashtag có dấu #, phân tách bằng khoảng trắng>"
    )


def _parse_label(text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise SeoGenerationError(f"Gemini không trả về nhãn '{label}:' trong output SEO")
    start = match.end()

    next_positions = []
    for other in _LABELS:
        if other == label:
            continue
        other_pattern = re.compile(rf"^{re.escape(other)}:", re.MULTILINE)
        other_match = other_pattern.search(text, start)
        if other_match is not None:
            next_positions.append(other_match.start())

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

    title = clip_title(_parse_label(text, "TITLE").strip().strip("'\""))
    description_draft = _parse_label(text, "DESCRIPTION")
    tags_raw = _parse_label(text, "TAGS")
    hashtags_raw = _parse_label(text, "HASHTAGS")

    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    hashtags = [h.strip() for h in hashtags_raw.split() if h.strip()]

    return SeoCopy(
        title=title, description_draft=description_draft, tags=tags, hashtags=hashtags
    )
