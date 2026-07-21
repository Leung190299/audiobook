# scripts/generator.py
import json
import os

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Chapter, Script
from scripts.prompts import build_chapter_prompt, build_outline_prompt


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

    try:
        outline_response = await chat.send_message(
            build_outline_prompt(trope_name, trope_description)
        )
    except (GeminiError, APIError, AuthError) as exc:
        raise ScriptGenerationError(f"Gemini lỗi khi sinh dàn ý: {exc}") from exc

    outline = _parse_json_response(outline_response.text)
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
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScriptGenerationError(
            f"Không parse được JSON từ phản hồi Gemini: {exc}"
        ) from exc
