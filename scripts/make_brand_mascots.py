"""Vẽ avatar kênh (ếch nón lá bằng FLUX).

Tấm bên video dài và thumbnail đã chuyển sang bộ sticker kênh tự thiết kế
(scripts/cut_sticker_sheet.py, 07/10); script này chỉ còn vẽ avatar.

    uv run python -m scripts.make_brand_mascots            # vẽ nếu chưa có
    uv run python -m scripts.make_brand_mascots --force    # vẽ lại

Chạy khi máy rảnh RAM: FLUX cần ~6GB.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw

from thumbnail.generator import generate_mascot_image
from thumbnail.sticker import MASCOT_SEED, cut_out_background, mascot_prompt

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "assets" / "brand"

# Avatar: cận mặt, nét to, ít chi tiết. Avatar YouTube hiện ở cỡ 40px trong
# bình luận -- logo cũ (sách, mic, cốc, nốt nhạc, chữ) ở cỡ đó thành một đốm màu.
AVATAR_POSE = "close-up portrait of the face and hat only, wearing headphones, cheerful smile, looking at viewer"
AVATAR_SIZE = 800  # YouTube khuyên ảnh đại diện 800x800
AVATAR_BG = (248, 230, 210)  # cùng màu kem tấm bên video (BrandPanel BRAND.panel)
AVATAR_RING = (74, 44, 26)  # nâu đậm như viền nhân vật
# Phần trên của nhân vật giữ lại cho avatar: nón, mặt và nửa thân (phần
# thân này tràn qua mép dưới vòng tròn và bị cắt đi).
HEAD_RATIO = 0.80


def _ve(pose: str) -> Image.Image:
    raw = generate_mascot_image(mascot_prompt(pose), seed=MASCOT_SEED)
    return cut_out_background(Image.open(io.BytesIO(raw)))


def ve_avatar(force: bool) -> Path:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    out = BRAND_DIR / "avatar-frog.png"
    if out.exists() and not force:
        print(f"đã có, bỏ qua: {out.name}")
        return out
    raw = BRAND_DIR / "avatar-frog-raw.png"
    if raw.exists() and not force:
        # Bản tách nền đã lưu: chỉnh bố cục avatar không phải vẽ lại bằng FLUX.
        frog = Image.open(raw).convert("RGBA")
    else:
        print(f"vẽ {out.name}: {AVATAR_POSE}")
        frog = _ve(AVATAR_POSE)
        frog.save(raw)

    # FLUX hay vẽ nguyên người dù đã xin cận mặt. Cắt lấy đầu + nón (phần trên
    # cùng của nhân vật) để mặt lấp đầy vòng tròn: avatar YouTube hiện ở cỡ
    # 40px trong bình luận, để nguyên người thì mặt chỉ còn vài điểm ảnh.
    frog = frog.crop((0, 0, frog.width, int(frog.height * HEAD_RATIO)))

    canvas = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    # YouTube tự cắt tròn avatar: vẽ sẵn nền tròn + viền để ra đúng như ý.
    ring = AVATAR_SIZE // 40
    draw.ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=AVATAR_RING)
    draw.ellipse((ring, ring, AVATAR_SIZE - 1 - ring, AVATAR_SIZE - 1 - ring), fill=AVATAR_BG)

    # Kiểu chân dung bán thân: rộng ~92% đường kính, đỉnh nón cách mép trên
    # ~8%, phần thân tràn ra ngoài mép dưới để vòng tròn tự cắt. Cắt phẳng rồi
    # đặt lọt trong vòng tròn thì thân kết thúc bằng một đường ngang lơ lửng.
    scale = AVATAR_SIZE * 0.92 / frog.width
    frog = frog.resize((int(frog.width * scale), int(frog.height * scale)), Image.LANCZOS)
    x = (AVATAR_SIZE - frog.width) // 2
    y = int(AVATAR_SIZE * 0.08)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).ellipse((ring, ring, AVATAR_SIZE - 1 - ring, AVATAR_SIZE - 1 - ring), fill=255)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.alpha_composite(frog, (x, y))
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", canvas.size, 0), mask))
    canvas.alpha_composite(layer)
    canvas.save(out)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="Vẽ lại kể cả bản đã có")
    a = p.parse_args()
    print(f"Avatar: {ve_avatar(a.force)}")


if __name__ == "__main__":
    main()
