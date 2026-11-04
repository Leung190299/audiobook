# thumbnail/sticker.py
"""Thumbnail layout "linh vật sticker + cả câu tiêu đề" (spec 24/09/2026).

Học từ thumbnail thắng của đối thủ: nền pastel, một linh vật hoạt hình bên
trái, gần như CẢ CÂU tiêu đề (8-12 chữ) bên phải bằng font đậm condensed, 2-3 từ
khoá đổi màu, badge tên kênh cố định. Người xem nhận ra kênh bằng linh vật và
nhận ra chủ đề bằng màu nền (mỗi chủ đề một màu, xem scripts/topics.py).

    ┌──────────── 1280 ────────────┐
    │[AUDIO TRUYỆN]     [TẬP 1/3]? │
    │  ( linh vật )  BÁC CẢ ĐÒI    │
    │  (  ~42%   )   CHIA ĐẤT CỦA  │  <- 3-4 dòng, >= 72px, từ khoá tô 2 màu
    │  ( sticker )   BỐ, TÔI LIVE… │
    └──────────────────────────────┘

Linh vật là nhân vật GỐC của kênh: ếch xanh tròn đội nón lá -- không dùng vịt
trắng hay capybara (nhận diện của đối thủ) hay nhân vật có bản quyền. Từ 07/10
lấy từ bộ sticker kênh tự thiết kế (assets/brand/stickers/, cắt bởi
scripts/cut_sticker_sheet.py) theo `thumb_stickers` của chủ đề -- cùng một chú
ếch với tấm bên video, không còn vẽ bằng FLUX mỗi lượt.

Ảnh linh vật nền đặc (ảnh FLUX cũ, ảnh test) vẫn nhận: tách nền bằng loang màu
từ mép ảnh (viền đen dày của phong cách sticker chặn không cho loang vào trong
nhân vật) rồi vẽ viền trắng.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from scripts.text_tools import keyword_spans

WIDTH, HEIGHT = 1280, 720
MASCOT_AREA_RATIO = 0.42
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
STICKER_DIR = Path(__file__).resolve().parent.parent / "assets" / "brand" / "stickers"
# Anton: condensed rất đậm, có đủ dấu tiếng Việt (kiểm tra "Ố Ẫ Ự Ỹ" trong
# tests/thumbnail/test_sticker.py). Oswald/Bebas Neue Pro VN là phương án thay.
TITLE_FONT_PATH = FONTS_DIR / "Anton-Regular.ttf"
BADGE_FONT_PATH = FONTS_DIR / "BeVietnamPro-Black.ttf"

MAX_FONT_SIZE = 150
MIN_FONT_SIZE = 72
MAX_LINES = 4
LINE_SPACING = 1.22
TEXT_COLOR = (59, 35, 20)  # nâu đen
TEXT_STROKE = (255, 255, 255)
MARGIN = 40
TEXT_TOP = 104  # chừa chỗ cho badge kênh
BADGE_FILL = (59, 35, 20)
BADGE_TEXT = (255, 255, 255)
EPISODE_BADGE_FILL = (255, 216, 77)
EPISODE_BADGE_TEXT = (20, 20, 20)
STICKER_BORDER = 14

DEFAULT_CHANNEL_NAME = "Audio Truyện"

MASCOT_SEED = 240926
MASCOT_CHARACTER = (
    "an original cute mascot character: a chubby round little green frog with big "
    "expressive eyes and rosy cheeks, wearing a small Vietnamese conical straw hat (non la)"
)
MASCOT_STYLE = (
    "flat 2D vector sticker illustration, thick dark brown outline, simple cel shading, "
    "full body, centered, isolated on a plain pure white background, no text, no logo, "
    "no watermark, no border"
)


def mascot_prompt(pose: str) -> str:
    return f"{MASCOT_CHARACTER}, {pose}, {MASCOT_STYLE}"


def load_sticker(name: str) -> bytes:
    """Sticker linh vật đã tách nền + viền trắng, theo tên (vd. "hum")."""
    path = STICKER_DIR / f"{name}.png"
    if not path.exists():
        raise FileNotFoundError(
            f"Không có sticker {path}. Chạy: uv run python -m scripts.cut_sticker_sheet"
        )
    return path.read_bytes()


def channel_name() -> str:
    return os.getenv("CHANNEL_NAME") or DEFAULT_CHANNEL_NAME


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --- linh vật ----------------------------------------------------------------


def cut_out_background(image: Image.Image, threshold: int = 38) -> Image.Image:
    """Nền trắng (hoặc gần trắng) nối với mép ảnh -> trong suốt."""
    rgb = image.convert("RGB")
    marker = (255, 0, 255)
    w, h = rgb.size
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    seeds += [(x, 0) for x in range(0, w, max(1, w // 16))]
    seeds += [(x, h - 1) for x in range(0, w, max(1, w // 16))]
    seeds += [(0, y) for y in range(0, h, max(1, h // 16))]
    seeds += [(w - 1, y) for y in range(0, h, max(1, h // 16))]
    for xy in seeds:
        px = rgb.getpixel(xy)
        if px == marker:
            continue
        if min(px) >= 255 - threshold * 2:  # chỉ loang từ điểm sáng (nền)
            ImageDraw.floodfill(rgb, xy, marker, thresh=threshold)
    arr = np.asarray(rgb)
    background = np.all(arr == np.array(marker, dtype=arr.dtype), axis=-1)
    alpha = Image.fromarray(np.where(background, 0, 255).astype("uint8"), "L")
    # Ăn 1px vào trong để bỏ viền trắng lợn cợn do khử răng cưa.
    alpha = alpha.filter(ImageFilter.MinFilter(3))
    out = image.convert("RGBA")
    out.putalpha(alpha)
    bbox = alpha.getbbox()
    return out.crop(bbox) if bbox else out


def sticker(image: Image.Image, border: int = STICKER_BORDER) -> Image.Image:
    """Viền trắng dày + bóng đổ mềm quanh nhân vật đã tách nền."""
    pad = border * 3
    w, h = image.size
    canvas = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    alpha = Image.new("L", canvas.size, 0)
    alpha.paste(image.getchannel("A"), (pad, pad))
    size = border * 2 + 1
    outline = alpha.filter(ImageFilter.MaxFilter(size if size % 2 else size + 1))
    shadow = outline.filter(ImageFilter.GaussianBlur(border))
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_layer.putalpha(shadow.point(lambda v: v * 45 // 100))
    canvas.alpha_composite(shadow_layer, (border // 2, border))
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
    white.putalpha(outline)
    canvas.alpha_composite(white)
    canvas.alpha_composite(image, (pad, pad))
    return canvas


# --- chữ ---------------------------------------------------------------------


def _font(size: int, path: Path = TITLE_FONT_PATH) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _stroke(size: int) -> int:
    return max(3, size // 22)


def _wrap(draw: ImageDraw.ImageDraw, words: list[str], font, max_width: int) -> list[list[int]]:
    """Ngắt dòng tham lam; trả về danh sách dòng, mỗi dòng là chỉ số từ."""
    lines: list[list[int]] = []
    current: list[int] = []
    stroke = _stroke(font.size)
    for i, word in enumerate(words):
        trial = " ".join(words[j] for j in current + [i])
        width = draw.textlength(trial, font=font) + 2 * stroke
        if current and width > max_width:
            lines.append(current)
            current = [i]
        else:
            current.append(i)
    if current:
        lines.append(current)
    return lines


def _line_height(font) -> int:
    return int(font.size * LINE_SPACING)


def layout_title(
    text: str, box_width: int, box_height: int, min_size: int = MIN_FONT_SIZE
) -> tuple[ImageFont.FreeTypeFont, list[list[int]], list[str]]:
    """Cỡ chữ lớn nhất để `text` (IN HOA) vừa hộp trong <= 4 dòng.

    Không vừa ở 72px thì tiếp tục co (và báo) -- tràn khung còn tệ hơn chữ nhỏ."""
    words = text.upper().split()
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    size = MAX_FONT_SIZE
    while True:
        font = _font(size)
        lines = _wrap(draw, words, font, box_width)
        widest = max(
            draw.textlength(" ".join(words[i] for i in line), font=font) + 2 * _stroke(size)
            for line in lines
        )
        height = _line_height(font) * len(lines)
        if len(lines) <= MAX_LINES and height <= box_height and widest <= box_width:
            return font, lines, words
        if size <= 24:
            return font, lines, words
        if size <= min_size:
            print(f"CẢNH BÁO: tiêu đề thumbnail phải co dưới {min_size}px mới vừa: {text!r}")
        size -= 2


def _word_colors(words: list[str], keywords: list[str], palette: list[tuple]) -> list[tuple]:
    upper = " ".join(words)
    spans = keyword_spans(upper, [k.upper() for k in keywords])
    colors = []
    pos = 0
    for word in words:
        start, end = pos, pos + len(word)
        color = TEXT_COLOR
        for s, e, idx in spans:
            if start < e and end > s:
                color = palette[idx % len(palette)]
                break
        colors.append(color)
        pos = end + 1
    return colors


def _draw_badge(image: Image.Image, label: str, xy: tuple[int, int], fill, text_fill, anchor_right=False) -> None:
    draw = ImageDraw.Draw(image)
    font = _font(34, BADGE_FONT_PATH)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 20, 11
    x0, y0 = xy
    if anchor_right:
        x0 = x0 - tw - 2 * px
    draw.rounded_rectangle([x0, y0, x0 + tw + 2 * px, y0 + th + 2 * py], radius=16, fill=fill)
    draw.text((x0 + px - bbox[0], y0 + py - bbox[1]), label, font=font, fill=text_fill)


def compose_sticker_thumbnail(
    mascot_bytes: bytes | None,
    thumb_text: str,
    keywords: list[str],
    palette: tuple[str, str, str],
    channel: str | None = None,
    episode_label: str | None = None,
    swap_keyword_colors: bool = False,
) -> bytes:
    bg = hex_to_rgb(palette[0])
    kw_colors = [hex_to_rgb(palette[1]), hex_to_rgb(palette[2])]
    if swap_keyword_colors:
        kw_colors.reverse()

    image = Image.new("RGBA", (WIDTH, HEIGHT), bg + (255,))
    mascot_w = int(WIDTH * MASCOT_AREA_RATIO)

    # Quầng sáng sau linh vật cho nổi khỏi nền.
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy, r = mascot_w // 2 + 10, HEIGHT // 2 + 30, int(HEIGHT * 0.42)
    gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 120))
    image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))

    if mascot_bytes:
        mascot = Image.open(io.BytesIO(mascot_bytes))
        if mascot.mode != "RGBA" or mascot.getchannel("A").getextrema() == (255, 255):
            mascot = sticker(cut_out_background(mascot))
        # Ảnh đã nền trong (bộ sticker kênh) có sẵn viền trắng: vẽ thêm viền nữa
        # thành viền dày gấp đôi.
        box_w, box_h = mascot_w - 20, HEIGHT - 70
        scale = min(box_w / mascot.width, box_h / mascot.height)
        mascot = mascot.resize((max(1, int(mascot.width * scale)), max(1, int(mascot.height * scale))), Image.LANCZOS)
        x = (mascot_w - mascot.width) // 2 + 6
        y = HEIGHT - mascot.height - 10
        image.alpha_composite(mascot, (x, y))

    # Khối chữ bên phải.
    box_x0 = mascot_w + 8
    box_w = WIDTH - MARGIN - box_x0
    box_h = HEIGHT - TEXT_TOP - MARGIN
    font, lines, words = layout_title(thumb_text, box_w, box_h)
    colors = _word_colors(words, keywords, kw_colors)
    draw = ImageDraw.Draw(image)
    stroke = _stroke(font.size)
    lh = _line_height(font)
    block_h = lh * len(lines)
    y = TEXT_TOP + (box_h - block_h) // 2
    ascent, _ = font.getmetrics()
    for line in lines:
        x = box_x0 + stroke
        # Căn đỉnh theo ascent để dấu mũ tiếng Việt (Ố, Ẫ) không đè dòng trên.
        baseline = y + int(lh * 0.5 + ascent * 0.42)
        for k, i in enumerate(line):
            word = words[i] + (" " if k < len(line) - 1 else "")
            draw.text(
                (x, baseline),
                word,
                font=font,
                fill=colors[i],
                stroke_width=stroke,
                stroke_fill=TEXT_STROKE,
                anchor="ls",
            )
            x += draw.textlength(word, font=font)
        y += lh

    _draw_badge(image, (channel or channel_name()).upper(), (MARGIN - 8, 28), BADGE_FILL, BADGE_TEXT)
    if episode_label:
        _draw_badge(image, episode_label, (WIDTH - MARGIN + 8, 28), EPISODE_BADGE_FILL, EPISODE_BADGE_TEXT, anchor_right=True)

    out = io.BytesIO()
    image.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def text_bounds(thumb_text: str) -> tuple[int, int, int, int, int]:
    """(cỡ chữ, số dòng, bề rộng dòng dài nhất, tổng cao, bề rộng hộp) -- cho test
    kiểm tra không tràn khung mà không phải đọc pixel."""
    box_x0 = int(WIDTH * MASCOT_AREA_RATIO) + 8
    box_w = WIDTH - MARGIN - box_x0
    box_h = HEIGHT - TEXT_TOP - MARGIN
    font, lines, words = layout_title(thumb_text, box_w, box_h)
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    widest = max(
        int(draw.textlength(" ".join(words[i] for i in line), font=font)) + 2 * _stroke(font.size)
        for line in lines
    )
    return font.size, len(lines), widest, _line_height(font) * len(lines), box_w
