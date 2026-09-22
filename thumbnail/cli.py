# thumbnail/cli.py
"""Stage 5: một ảnh nền (mflux) -> ảnh truyện + một ảnh cho MỖI TẬP.

    uv run python -m thumbnail.cli <script_json> [--episodes <manifest_json>]
    # Đã lưu thumbnail: output/thumbnails/<trope>-<ts>.png
    # Thumbnail tập 1/3: output/thumbnails/<trope>-<ts>-ep-01.png
    # ...

Chỉ vẽ ảnh nền MỘT lần (~1 phút mflux); các bản theo tập chỉ khác badge "TẬP
N/3", nên ghép chữ lại từ cùng bytes ảnh -- ba tập cùng một mặt, cùng một câu
hook, khác số: người xem lướt danh sách nhận ra ngay đây là một bộ.

Không có --episodes thì vẫn ra một ảnh như pipeline cũ (dựng video full).
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from episodes.storage import load_manifest
from scripts.models import Script
from thumbnail.compositor import overlay_hook_text
from thumbnail.generator import generate_thumbnail_image
from thumbnail.prompt_generator import generate_thumbnail_prompt
from thumbnail.storage import make_stem, save_episode_thumbnail

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "thumbnails"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


async def _run(script_path: Path, gemini_client=None, episodes_manifest: Path | None = None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    prompt = await generate_thumbnail_prompt(script, gemini_client)
    image_bytes = generate_thumbnail_image(prompt.visual_description)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = make_stem(script.trope)
    base_path = OUTPUT_DIR / f"{stem}.png"
    base_path.write_bytes(overlay_hook_text(image_bytes, prompt.hook_text))
    print(f"Đã lưu thumbnail: {base_path}")

    if episodes_manifest is not None:
        manifest = load_manifest(episodes_manifest)
        for ep in manifest["episodes"]:
            label = f"TẬP {ep['number']}/{ep['total']}"
            final_bytes = overlay_hook_text(image_bytes, prompt.hook_text, episode_label=label)
            path = save_episode_thumbnail(stem, ep["number"], final_bytes, OUTPUT_DIR)
            print(f"Thumbnail tập {ep['number']}/{ep['total']}: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh thumbnail cho video truyện audio.")
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument(
        "--episodes",
        type=Path,
        default=None,
        help="Manifest của stage episodes (<stem>-episodes.json): sinh thêm một ảnh/tập có badge TẬP N",
    )
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path), episodes_manifest=args.episodes))


if __name__ == "__main__":
    main()
