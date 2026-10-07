"""Cắt bảng sticker linh vật (assets/brand/sticker-sheet.webp) thành từng ảnh nền trong.

Bảng 4x4 do kênh tự thiết kế (07/10): cùng chú ếch đội nón lá, mỗi ô một tư thế
kèm câu thoại. Thay cho các tư thế FLUX vẽ trước đây -- nét đều, có chữ tiếng
Việt sẵn, và giống hệt nhau giữa video, thumbnail, avatar.

    uv run python -m scripts.cut_sticker_sheet

Ra assets/brand/stickers/<tên>.png (bản gốc cỡ lớn), rồi chép các bản video
dùng sang remotion/public/sticker-<tên>.png.

Nền bảng trắng ~254, trùng màu viền trắng của sticker, nên không giữ được viền
gốc: bỏ hết vùng sáng nối với mép bảng (cả viền trắng lẫn bóng xám), rồi vẽ lại
viền trắng + bóng bằng thumbnail.sticker.sticker() -- cùng kiểu các thumbnail cũ.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from thumbnail.sticker import sticker

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "assets" / "brand" / "sticker-sheet.webp"
OUT_DIR = ROOT / "assets" / "brand" / "stickers"
PUBLIC = ROOT / "remotion" / "public"

# Theo thứ tự đọc của bảng: trái sang phải, trên xuống dưới.
NAMES = (
    "logo", "nghe-truyen", "hay-qua", "thu-gian",
    "dang-ky", "ngu", "cung-nghe", "cam-on",
    "hum", "truyen-hay", "like", "chill",
    "moi-luc", "co-len", "kien-thuc", "hen-gap",
)
# Sticker tấm bên video dài dùng (remotion/src/BrandPanel.tsx).
VIDEO_STICKERS = ("logo", "nghe-truyen", "dang-ky", "like")

LIGHT = 170  # sáng hơn mức này + gần xám = nền / viền trắng / bóng xám của bảng
MERGE_PX = 10  # chữ thoại cách nhân vật < ~20px thì gộp làm một sticker
UPSCALE = 2  # bảng chỉ ~300px mỗi ô; phóng trước khi vẽ viền cho viền mịn
BORDER = 12


def cut(sheet: Image.Image) -> list[Image.Image]:
    rgb = np.asarray(sheet.convert("RGB")).astype(int)
    light = (rgb.min(-1) >= LIGHT) & (rgb.max(-1) - rgb.min(-1) < 40)
    regions, _ = ndimage.label(light)
    keep = regions != regions[0, 0]  # vùng sáng nối với góc bảng = nền
    # Đốm nhỏ màu nhạt lơ lửng là nhiễu nén của quầng sáng quanh sticker, không
    # phải nét vẽ (chữ, chấm "...", tim đều đậm màu).
    bits, m = ndimage.label(keep)
    area = ndimage.sum(keep, bits, range(1, m + 1))
    tone = ndimage.mean(rgb.min(-1), bits, range(1, m + 1))
    noise = np.flatnonzero((area < 600) & (tone > 140)) + 1
    keep &= ~np.isin(bits, noise)

    groups, n = ndimage.label(ndimage.binary_dilation(keep, iterations=MERGE_PX))
    if n < len(NAMES):
        raise SystemExit(f"Chỉ tách ra {n} mảng, cần {len(NAMES)} -- giảm MERGE_PX.")
    # 16 mảng lớn nhất là 16 sticker; mảng lẻ còn lại (chữ thoại, nốt nhạc, tim
    # nằm xa nhân vật) gộp vào sticker có tâm gần nhất.
    sizes = ndimage.sum(keep, groups, range(1, n + 1))
    centers = ndimage.center_of_mass(keep, groups, range(1, n + 1))
    big = sorted(range(n), key=lambda i: -sizes[i])[: len(NAMES)]
    remap = np.zeros(n + 1, dtype=int)
    for i in range(n):
        nearest = min(big, key=lambda b: np.hypot(*np.subtract(centers[i], centers[b])))
        remap[i + 1] = nearest + 1
    groups = remap[groups]
    n = len(NAMES)
    centers = [centers[b] for b in big]
    groups = np.searchsorted(np.array([0] + [b + 1 for b in sorted(big)]), groups) * (groups > 0)
    centers = [centers[big.index(b)] for b in sorted(big)]
    by_row = sorted(range(n), key=lambda i: centers[i][0])
    cols = int(len(NAMES) ** 0.5)
    order = [i for r in range(0, n, cols) for i in sorted(by_row[r : r + cols], key=lambda i: centers[i][1])]

    alpha_all = Image.fromarray((keep * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.6))
    rgba = sheet.convert("RGBA")
    rgba.putalpha(alpha_all)
    out = []
    for i in order:
        ys, xs = np.nonzero(groups == i + 1)
        box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        piece = rgba.crop(box)
        mask = Image.fromarray(((groups[box[1] : box[3], box[0] : box[2]] == i + 1) * 255).astype("uint8"))
        piece.putalpha(Image.composite(piece.getchannel("A"), Image.new("L", piece.size, 0), mask))
        piece = piece.resize((piece.width * UPSCALE, piece.height * UPSCALE), Image.LANCZOS)
        out.append(sticker(piece, border=BORDER))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, img in zip(NAMES, cut(Image.open(SHEET))):
        img.save(OUT_DIR / f"{name}.png")
        if name in VIDEO_STICKERS:
            img.save(PUBLIC / f"sticker-{name}.png")
        print(f"{name}: {img.width}x{img.height}")


if __name__ == "__main__":
    main()
