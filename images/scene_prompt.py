import os

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Chapter


class ScenePromptError(Exception):
    pass


def build_scene_prompt_request(chapter_text: str) -> str:
    return (
        "Đọc đoạn truyện tiếng Việt sau và mô tả LẠI bằng tiếng Anh, NGẮN GỌN (1-2 câu), "
        "chỉ tập trung vào KHÔNG GIAN/BỐI CẢNH và KHÔNG KHÍ của cảnh (ví dụ: phòng khách ấm "
        "cúng buổi tối, cánh đồng hoa lúc hoàng hôn, bờ biển vắng buổi sáng...). KHÔNG mô tả "
        "nhân vật, KHÔNG kể lại cốt truyện, KHÔNG dùng tên riêng. Chỉ trả về câu mô tả bối "
        "cảnh bằng tiếng Anh, không kèm giải thích gì khác, không kèm dấu ngoặc kép.\n\n"
        f"Đoạn truyện:\n{chapter_text}"
    )


async def generate_scene_description(
    chapter: Chapter, client: "GeminiClient | None" = None
) -> str:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    try:
        response = await client.generate_content(build_scene_prompt_request(chapter.text))
    except (GeminiError, APIError, AuthError) as exc:
        raise ScenePromptError(
            f"Gemini lỗi khi tạo mô tả cảnh cho chương {chapter.index}: {exc}"
        ) from exc

    description = response.text.strip().strip('"').strip()
    if not description:
        raise ScenePromptError(
            f"Gemini trả về mô tả cảnh rỗng cho chương {chapter.index}"
        )

    return description
