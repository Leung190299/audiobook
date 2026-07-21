# scripts/generator.py
import json
import os

from gemini_webapi import GeminiClient

from scripts.models import Chapter, Script
from scripts.prompts import build_prompt


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

    response = await client.generate_content(build_prompt(trope_name, trope_description))
    data = _parse_script_json(response.text)

    try:
        title = data["title"]
        chapters = [
            Chapter(index=i + 1, heading=chapter["heading"], text=chapter["text"])
            for i, chapter in enumerate(data["chapters"])
        ]
    except (KeyError, TypeError) as exc:
        raise ScriptGenerationError(
            f"Dữ liệu JSON không đúng cấu trúc mong đợi: {exc}"
        ) from exc

    return Script(trope=trope_id, title=title, chapters=chapters)


def _parse_script_json(raw_text: str) -> dict:
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
