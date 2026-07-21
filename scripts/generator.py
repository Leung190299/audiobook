import os

import anthropic

from scripts.models import Chapter, Script
from scripts.prompts import SYSTEM_PROMPT, build_user_prompt

MODEL = "claude-sonnet-5"

OUTPUT_SCRIPT_TOOL = {
    "name": "output_script",
    "description": "Trả về truyện đã sáng tác dưới dạng tiêu đề và danh sách chương.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Tiêu đề truyện, dạng câu hook giật.",
            },
            "chapters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["heading", "text"],
                },
                "minItems": 6,
                "maxItems": 10,
            },
        },
        "required": ["title", "chapters"],
    },
}


class ScriptGenerationError(Exception):
    pass


def generate_script(
    trope_id: str,
    trope_name: str,
    trope_description: str,
    client: "anthropic.Anthropic | None" = None,
) -> Script:
    client = client or anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=[OUTPUT_SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "output_script"},
        messages=[
            {"role": "user", "content": build_user_prompt(trope_name, trope_description)}
        ],
    )

    tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
    if not tool_use_blocks:
        raise ScriptGenerationError("Claude không trả về tool_use block nào.")

    data = tool_use_blocks[0].input
    chapters = [
        Chapter(index=i + 1, heading=chapter["heading"], text=chapter["text"])
        for i, chapter in enumerate(data["chapters"])
    ]
    return Script(trope=trope_id, title=data["title"], chapters=chapters)
