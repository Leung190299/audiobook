import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from metadata.chapters import build_chapter_lines
from metadata.filename import rename_video_file
from metadata.seo_generator import generate_seo_copy
from metadata.storage import save_seo_metadata
from scripts.models import Script

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "metadata"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


async def _run(
    script_path: Path,
    tts_metadata_path: Path,
    video_path: Path,
    gemini_client=None,
) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    seo_copy = await generate_seo_copy(script, gemini_client)
    chapter_lines = build_chapter_lines(tts_metadata)
    new_video_path = rename_video_file(video_path, seo_copy.title)

    txt_path, json_path = save_seo_metadata(
        script.trope, seo_copy, chapter_lines, new_video_path.name, OUTPUT_DIR
    )

    print(
        f"Đã lưu metadata SEO: {txt_path}\n"
        f"JSON: {json_path}\n"
        f"Video đã đổi tên: {new_video_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh metadata SEO (title/description/tags/hashtags/chapters) cho video YouTube."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("tts_metadata_path", help="Đường dẫn file JSON metadata TTS")
    parser.add_argument("video_path", help="Đường dẫn file video .mp4")
    args = parser.parse_args()
    asyncio.run(
        _run(Path(args.script_path), Path(args.tts_metadata_path), Path(args.video_path))
    )


if __name__ == "__main__":
    main()
