import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from images.generator import generate_background_image
from images.scene_planner import plan_scenes
from images.scene_prompt import generate_scene_description
from images.storage import save_scene_images
from scripts.models import Script

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "images"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


class ImagesInputError(Exception):
    pass


def _mmss(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60:02d}:{whole % 60:02d}"


async def _run(
    script_path: Path, tts_metadata_path: Path, gemini_client=None
) -> None:
    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))

    if tts_metadata["trope"] != script.trope or tts_metadata["title"] != script.title:
        raise ImagesInputError(
            "trope/title của metadata TTS không khớp với script "
            f"(script: {script.trope!r}/{script.title!r}, "
            f"tts: {tts_metadata['trope']!r}/{tts_metadata['title']!r})"
        )

    # Stage 3 nay cần mốc câu của stage 2 để chia cảnh -- nên nhận TTS JSON chứ
    # không chỉ script. Tập dựng trước khi stage 2 ghi mốc câu sẽ bị plan_scenes
    # từ chối với thông báo bảo chạy lại stage 2.
    scenes = plan_scenes(tts_metadata)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    images = []
    for position, scene in enumerate(scenes, start=1):
        # In trước khi vẽ: stage này chạy ~50 phút, người theo dõi log cần biết
        # nó đang ở đâu chứ không phải nó có treo không.
        print(
            f"Cảnh {position}/{len(scenes)}: chương {scene.chapter_index} "
            f"cảnh {scene.number} ({_mmss(scene.start_seconds)}–{_mmss(scene.end_seconds)})",
            flush=True,
        )
        description = await generate_scene_description(
            scene.chapter_index, scene.number, scene.text, gemini_client
        )
        image_bytes = generate_background_image(description)
        images.append((scene, description, image_bytes))

    image_paths, metadata_path = save_scene_images(
        script.trope, script.title, images, OUTPUT_DIR
    )

    print(
        f"Đã lưu {len(image_paths)} ảnh vào {OUTPUT_DIR}\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh ảnh nền cho từng cảnh ~50s của kịch bản bằng Flux."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản (stage 1)")
    parser.add_argument(
        "tts_metadata_path",
        help="Đường dẫn file JSON metadata TTS (stage 2) -- cần mốc câu để chia cảnh",
    )
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path), Path(args.tts_metadata_path)))


if __name__ == "__main__":
    main()
