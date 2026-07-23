# thumbnail/cli.py
import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from scripts.models import Script
from thumbnail.compositor import overlay_hook_text
from thumbnail.generator import generate_thumbnail_image
from thumbnail.prompt_generator import generate_thumbnail_prompt
from thumbnail.storage import save_thumbnail

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "thumbnails"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


async def _run(script_path: Path, gemini_client=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    prompt = await generate_thumbnail_prompt(script, gemini_client)
    image_bytes = generate_thumbnail_image(prompt.visual_description)
    final_bytes = overlay_hook_text(image_bytes, prompt.hook_text)

    output_path = save_thumbnail(script.trope, final_bytes, OUTPUT_DIR)

    print(f"Đã lưu thumbnail: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh thumbnail cho video truyện audio."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path)))


if __name__ == "__main__":
    main()
