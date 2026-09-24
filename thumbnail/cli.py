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

Từ 24/09/2026, kịch bản CHỦ ĐỀ (có `thumb_text`) dùng layout "linh vật sticker +
cả câu tiêu đề" (thumbnail/sticker.py) và không cần Gemini: chữ đã có từ stage 1.
Sinh 2 linh vật (2 tư thế) -> bản A + bản B cho Test & compare của YouTube:

    # (full)      Đã lưu thumbnail: output/thumbnails/<stem>-thumbnail-a.png
    #             Thumbnail B: output/thumbnails/<stem>-thumbnail-b.png
    # (episodes)  Đã lưu thumbnail: <stem>.png, Thumbnail tập N/3: <stem>-ep-0N.png,
    #             Thumbnail B: <stem>-thumbnail-b.png (badge TẬP 1/3)
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
from scripts.topics import TOPICS
from thumbnail.compositor import overlay_hook_text
from thumbnail.generator import generate_mascot_image, generate_thumbnail_image
from thumbnail.prompt_generator import generate_thumbnail_prompt
from thumbnail.sticker import MASCOT_SEED, compose_sticker_thumbnail, mascot_prompt
from thumbnail.storage import make_stem, save_episode_thumbnail

# Chủ đề lạ (kịch bản sửa tay) vẫn có màu: nền kem, đỏ + xanh lá.
FALLBACK_PALETTE = ("#FFE3C2", "#E4312B", "#1E7A46")
FALLBACK_POSES = ("arms crossed with a smug side-eye", "gasping with both hands on cheeks")

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "thumbnails"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


def _run_sticker(script: Script, manifest: dict | None) -> None:
    topic = TOPICS.get(script.topic)
    palette = topic.thumb_palette if topic else FALLBACK_PALETTE
    poses = (topic.mascot_pose_hints if topic else ()) or FALLBACK_POSES
    pose_a = poses[0]
    pose_b = poses[1 % len(poses)]
    mascot_a = generate_mascot_image(mascot_prompt(pose_a), MASCOT_SEED)
    # Bản B đổi biểu cảm linh vật VÀ đảo màu từ khoá -- hai biến khác nhau rõ
    # để Test & compare có gì mà so. Cùng seed để vẫn là một nhân vật.
    mascot_b = mascot_a if pose_b == pose_a else generate_mascot_image(mascot_prompt(pose_b), MASCOT_SEED)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = make_stem(script.trope)
    fmt = (manifest or {}).get("format") or script.format or "full"

    def render(mascot: bytes, label: str | None = None, swap: bool = False) -> bytes:
        return compose_sticker_thumbnail(
            mascot, script.thumb_text, script.thumb_keywords, palette,
            episode_label=label, swap_keyword_colors=swap,
        )

    if fmt == "full" or manifest is None:
        a_path = OUTPUT_DIR / f"{stem}-thumbnail-a.png"
        b_path = OUTPUT_DIR / f"{stem}-thumbnail-b.png"
        a_path.write_bytes(render(mascot_a))
        b_path.write_bytes(render(mascot_b, swap=True))
        print(f"Đã lưu thumbnail: {a_path}")
        print(f"Thumbnail B: {b_path}")
        return

    base_path = OUTPUT_DIR / f"{stem}.png"
    base_path.write_bytes(render(mascot_a))
    print(f"Đã lưu thumbnail: {base_path}")
    for ep in manifest["episodes"]:
        label = f"TẬP {ep['number']}/{ep['total']}"
        path = save_episode_thumbnail(stem, ep["number"], render(mascot_a, label), OUTPUT_DIR)
        print(f"Thumbnail tập {ep['number']}/{ep['total']}: {path}")
    first = manifest["episodes"][0]
    b_path = OUTPUT_DIR / f"{stem}-thumbnail-b.png"
    b_path.write_bytes(render(mascot_b, f"TẬP {first['number']}/{first['total']}", swap=True))
    print(f"Thumbnail B: {b_path}")


async def _run(script_path: Path, gemini_client=None, episodes_manifest: Path | None = None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if script.thumb_text:
        manifest = load_manifest(episodes_manifest) if episodes_manifest is not None else None
        _run_sticker(script, manifest)
        return

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
