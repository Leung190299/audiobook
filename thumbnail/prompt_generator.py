# thumbnail/prompt_generator.py
import os
import re
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Script


class ThumbnailPromptError(Exception):
    pass


@dataclass
class ThumbnailPrompt:
    hook_text: str
    visual_description: str


_LABELS = ("HOOK", "VISUAL")


def build_thumbnail_prompt_request(script: Script) -> str:
    headings = "\n".join(f"- {c.heading}" for c in script.chapters)
    return (
        "Bạn là chuyên gia thiết kế thumbnail YouTube. Dựa trên thông tin truyện "
        "audio tiếng Việt sau, hãy tạo nội dung cho thumbnail hấp dẫn.\n\n"
        f"Tiêu đề truyện: {script.title}\n"
        f"Thể loại: {script.trope}\n"
        f"Danh sách chương:\n{headings}\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "HOOK: <câu hook 2-4 từ tiếng Việt, IN HOA, giật gân nhưng đúng nội dung "
        "truyện, phù hợp làm chữ nổi bật trên thumbnail>\n"
        "VISUAL: <mô tả bằng tiếng Anh, 1-2 câu, một cảnh cận cảnh nhân vật thể "
        "hiện cảm xúc chủ đạo/cao trào của truyện (ví dụ: shocked expression, "
        "triumphant smirk, tearful determination) - KHÔNG dùng tên riêng, KHÔNG "
        "mô tả toàn bộ cốt truyện>"
    )


def _parse_label(text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise ThumbnailPromptError(
            f"Gemini không trả về nhãn '{label}:' trong output thumbnail"
        )
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
        raise ThumbnailPromptError(f"Gemini trả về nhãn '{label}:' rỗng")
    return value


async def generate_thumbnail_prompt(
    script: Script, client: "GeminiClient | None" = None
) -> ThumbnailPrompt:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    try:
        response = await client.generate_content(build_thumbnail_prompt_request(script))
    except (GeminiError, APIError, AuthError) as exc:
        raise ThumbnailPromptError(
            f"Gemini lỗi khi sinh nội dung thumbnail: {exc}"
        ) from exc

    text = response.text.strip()

    hook_text = _parse_label(text, "HOOK")
    visual_description = _parse_label(text, "VISUAL")

    return ThumbnailPrompt(hook_text=hook_text, visual_description=visual_description)
