# scripts/generator.py
import asyncio
import json
import os

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Chapter, Script
from scripts.prompts import build_chapter_prompt, build_outline_prompt


# Số lần hỏi Gemini cho dàn ý trước khi bỏ cuộc. Xem lý do ở generate_script().
OUTLINE_ATTEMPTS = 3
# Giây chờ trước lần thử lại đầu tiên; lần sau nhân đôi, nhân ba.
RETRY_DELAY_SECONDS = 5


class ScriptGenerationError(Exception):
    pass


async def generate_script(
    trope_id: str,
    trope_name: str,
    trope_description: str,
    client: "GeminiClient | None" = None,
) -> Script:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    chat = client.start_chat()

    # Gemini thỉnh thoảng trả JSON hỏng ở dàn ý — hay gặp nhất là một dấu nháy kép
    # không escape lọt vào giữa summary của chương cuối, đóng chuỗi sớm và làm vỡ cả
    # khối. Đo thực tế: hỏng 2 lần trong cùng một ngày, cùng vị trí. Prompt đã cấm
    # nháy kép, nhưng cấm không bằng thử lại: hỏng ở đây là mất trắng cả lượt chạy
    # một tiếng rưỡi. Chỉ thử lại lỗi parse; lỗi API thì ném ngay vì nó không tự khỏi.
    outline = None
    for attempt in range(OUTLINE_ATTEMPTS):
        try:
            outline_response = await chat.send_message(
                build_outline_prompt(trope_name, trope_description)
            )
        except (GeminiError, APIError, AuthError) as exc:
            raise ScriptGenerationError(f"Gemini lỗi khi sinh dàn ý: {exc}") from exc

        try:
            outline = _parse_json_response(outline_response.text)
            break
        except ScriptGenerationError:
            if attempt == OUTLINE_ATTEMPTS - 1:
                raise
            # Chờ trước khi hỏi lại. Một lượt hỏng ngày 03/09 nhận ba phản hồi RỖNG
            # liên tiếp trong chưa đầy hai phút — hỏi lại tức thì chỉ lặp lại đúng
            # trạng thái đó. Chờ vài giây cho Gemini qua cơn.
            await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    try:
        title = outline["title"]
        chapter_plans = [(plan["heading"], plan["summary"]) for plan in outline["chapters"]]
    except (KeyError, TypeError) as exc:
        raise ScriptGenerationError(
            f"Dữ liệu dàn ý không đúng cấu trúc mong đợi: {exc}\n"
            f"Phản hồi thô từ Gemini: {outline_response.text[:500]!r}"
        ) from exc

    total_chapters = len(chapter_plans)
    chapters = []
    for i, (heading, summary) in enumerate(chapter_plans):
        chapter_number = i + 1
        try:
            chapter_response = await chat.send_message(
                build_chapter_prompt(chapter_number, total_chapters, heading, summary)
            )
        except (GeminiError, APIError, AuthError) as exc:
            raise ScriptGenerationError(
                f"Gemini lỗi khi sinh chương {chapter_number}: {exc}"
            ) from exc

        chapters.append(
            Chapter(index=chapter_number, heading=heading, text=chapter_response.text.strip())
        )

    return Script(trope=trope_id, title=title, chapters=chapters)


def _parse_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[len("json") :].strip()
    try:
        # strict=False: Gemini hay nhét ký tự xuống dòng thô vào giữa chuỗi, mà
        # json.loads mặc định từ chối ký tự điều khiển trong chuỗi. Đo thực tế:
        # lỗi "Invalid control character" làm hỏng một lượt chạy ngày 03/09.
        return json.loads(text, strict=False)
    except json.JSONDecodeError as exc:
        # Gemini từ chối nội dung thì trả văn bản thường, không phải JSON hỏng.
        # Báo đúng loại lỗi kèm nguyên văn: một lượt ngày 03/09 mất bốn lần chạy
        # và ba bản vá nhầm chỗ chỉ vì thông báo cũ nói "không parse được JSON".
        if not text.lstrip().startswith(("{", "[")):
            raise ScriptGenerationError(
                "Gemini không trả về JSON mà trả văn bản thường — nhiều khả năng "
                f"là lời từ chối nội dung. Nguyên văn: {text[:300]!r}"
            ) from exc
        raise ScriptGenerationError(
            f"Không parse được JSON từ phản hồi Gemini: {exc}"
        ) from exc
