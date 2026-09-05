import os

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Chapter


class ScenePromptError(Exception):
    pass


def build_scene_prompt_request(chapter_text: str) -> str:
    # Prompt cũ chỉ yêu cầu "1-2 câu về bối cảnh". Gemini tuân thủ theo nghĩa đen
    # nhưng nhồi cả chương vào: hai địa điểm nối bằng "transitions into", đám đông,
    # và tính từ tâm trạng (tense, oppressive) mà mô hình vẽ không biết làm gì.
    # Kết quả thật: máy đo tim đứng giữa phòng khách Tết (chương 1), ~40 mặt người
    # méo (chương 8). Từng quy tắc dưới đây chặn đúng một lỗi đã thấy.
    return (
        "Đọc đoạn truyện tiếng Việt sau và viết ĐÚNG MỘT câu tiếng Anh (tối đa 30 từ) "
        "mô tả bối cảnh để vẽ ảnh nền minh hoạ.\n\n"
        "Quy tắc bắt buộc:\n"
        "1. ĐÚNG MỘT địa điểm, ĐÚNG MỘT thời điểm trong ngày. Chương có nhiều cảnh thì "
        "chọn cảnh xuất hiện lâu nhất. KHÔNG dùng transitions / then / shifts to / while.\n"
        "2. Cảnh TRỐNG, không có người: tả căn phòng hay con phố như lúc không ai ở đó. "
        "KHÔNG có people, crowd, family, guests, figures, silhouettes.\n"
        "3. Chỉ tả thứ NHÌN THẤY được: ánh sáng, thời tiết, thời điểm, 2-3 đồ vật đặc "
        "trưng. KHÔNG dùng từ tâm trạng trừu tượng (tense, oppressive, calculating, "
        "ominous, heavy) — thay bằng ánh sáng cụ thể (dim bedside lamp, cold blue dawn, "
        "harsh fluorescent light, golden late afternoon sun).\n"
        "4. KHÔNG tên riêng, KHÔNG kể cốt truyện, KHÔNG có chữ viết hay biển hiệu.\n"
        "5. Trả về đúng một câu, không giải thích, không dấu ngoặc kép.\n\n"
        "Ví dụ đúng: Empty hospital corridor at night, cold fluorescent light, a single "
        "wheelchair by the window, rain streaking the glass\n"
        "Ví dụ sai: A cold emergency room transitions into a cozy living room during "
        "Lunar New Year (hai địa điểm, có chuyển cảnh)\n\n"
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
