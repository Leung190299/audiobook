import argparse
import asyncio
import json
import os
from pathlib import Path

from gemini_webapi import GeminiClient
from together import Together

from images.generator import generate_background_image
from images.scene_prompt import generate_scene_description
from images.storage import save_chapter_images
from scripts.models import Script

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "images"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


def _load_flux_client() -> Together:
    return Together(api_key=os.environ["TOGETHER_API_KEY"])


async def _run(script_path: Path, gemini_client=None, flux_client=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    if flux_client is None:
        flux_client = _load_flux_client()

    images = []
    for chapter in script.chapters:
        scene_description = await generate_scene_description(chapter, gemini_client)
        image_bytes = generate_background_image(scene_description, flux_client)
        images.append((chapter.index, scene_description, image_bytes))

    image_paths, metadata_path = save_chapter_images(
        script.trope, script.title, images, OUTPUT_DIR
    )

    print(
        f"Đã lưu {len(image_paths)} ảnh vào {OUTPUT_DIR}\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh ảnh nền cho kịch bản truyện audio bằng Flux."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path)))


if __name__ == "__main__":
    main()
