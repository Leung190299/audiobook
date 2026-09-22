# thumbnail/compositor.py
"""Ghép chữ lên ảnh thumbnail 1280x720.

Bố cục (từ 22/09/2026, theo đánh giá kênh: CTR 3,2% với chữ nhỏ vàng viền đen
trải giữa ảnh):
- Dải tối gradient ở 45% dưới ảnh để chữ trắng luôn đọc được, dù ảnh sáng.
- Câu hook 2-4 từ, IN HOA, chữ to nhất có thể vừa 90% chiều rộng, NEO ĐÁY
  (không đặt giữa mặt nhân vật). Hook dài quá 4 từ được cắt về 4 từ đầu trước
  khi đo -- trên màn hình điện thoại, chữ nhỏ hơn ~70pt là không đọc được.
- Badge "TẬP N/3" góc trên trái, nền vàng chữ đen, để ba tập cùng một ảnh nền
  vẫn phân biệt được trong danh sách video và người xem biết mình đang ở đâu.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "BeVietnamPro-Black.ttf"
)
MAX_FONT_SIZE = 150
# Sàn đủ đọc trên thumbnail 320px rộng của mobile (~1/4 kích thước gốc).
MIN_FONT_SIZE = 64
TEXT_WIDTH_RATIO = 0.9
STROKE_WIDTH = 8
MAX_HOOK_WORDS = 4
# Chữ hook có thể xuống 2 dòng khi 1 dòng phải co dưới ngưỡng này.
TWO_LINE_THRESHOLD = 96
BOTTOM_MARGIN = 36
GRADIENT_START_RATIO = 0.55  # dải tối bắt đầu từ 55% chiều cao
GRADIENT_MAX_ALPHA = 215

BADGE_FONT_SIZE = 44
BADGE_PADDING = (22, 12)
BADGE_MARGIN = 28
BADGE_FILL = (255, 216, 77)
BADGE_TEXT = (20, 20, 20)


def _font(size: int) -> "ImageFont.FreeTypeFont":
    return ImageFont.truetype(str(FONT_PATH), size)


def _text_width(draw: "ImageDraw.ImageDraw", text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
    return bbox[2] - bbox[0]


def _fit_font(
    draw: "ImageDraw.ImageDraw", text: str, image_width: int
) -> "ImageFont.FreeTypeFont":
    """Cỡ chữ lớn nhất (bước 4) để `text` vừa 90% chiều rộng; không nhỏ hơn sàn."""
    max_text_width = image_width * TEXT_WIDTH_RATIO
    size = MAX_FONT_SIZE
    while size > MIN_FONT_SIZE:
        font = _font(size)
        if _text_width(draw, text, font) <= max_text_width:
            return font
        size -= 4
    return _font(MIN_FONT_SIZE)


def clip_hook(hook_text: str, max_words: int = MAX_HOOK_WORDS) -> str:
    words = hook_text.upper().split()
    return " ".join(words[:max_words])


def _split_two_lines(words: list[str]) -> tuple[str, str]:
    """Chia thành 2 dòng cân số ký tự nhất; dòng trên ngắn hơn hoặc bằng."""
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = abs(len(a) - len(b))
        if best is None or score < best[0]:
            best = (score, a, b)
    return best[1], best[2]


def _layout_lines(draw: "ImageDraw.ImageDraw", text: str, image_width: int) -> tuple[list[str], "ImageFont.FreeTypeFont"]:
    font = _fit_font(draw, text, image_width)
    words = text.split()
    if font.size >= TWO_LINE_THRESHOLD or len(words) < 2:
        return [text], font
    line_a, line_b = _split_two_lines(words)
    wider = max((line_a, line_b), key=len)
    font2 = _fit_font(draw, wider, image_width)
    # Chỉ xuống dòng khi chữ to lên thật; nếu không thì giữ 1 dòng.
    if font2.size > font.size:
        return [line_a, line_b], font2
    return [text], font


def _draw_gradient(image: Image.Image) -> Image.Image:
    width, height = image.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    start = int(height * GRADIENT_START_RATIO)
    span = max(1, height - start)
    for y in range(start, height):
        alpha = int(GRADIENT_MAX_ALPHA * ((y - start) / span) ** 1.2)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def _draw_badge(image: Image.Image, label: str) -> None:
    draw = ImageDraw.Draw(image)
    font = _font(BADGE_FONT_SIZE)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = BADGE_PADDING
    x0, y0 = BADGE_MARGIN, BADGE_MARGIN
    x1, y1 = x0 + tw + 2 * px, y0 + th + 2 * py
    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=BADGE_FILL)
    draw.text((x0 + px - bbox[0], y0 + py - bbox[1]), label, font=font, fill=BADGE_TEXT)


def overlay_hook_text(image_bytes: bytes, hook_text: str, episode_label: str | None = None) -> bytes:
    """Ghép hook (và badge tập nếu có) lên ảnh, trả về PNG.

    `episode_label` dạng "TẬP 1/3"; None cho bản không đánh số (ảnh gốc của
    truyện, hoặc pipeline cũ dựng một video).
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = _draw_gradient(image)
    draw = ImageDraw.Draw(image)

    text = clip_hook(hook_text)
    lines, font = _layout_lines(draw, text, image.width)

    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=STROKE_WIDTH)
        line_heights.append((bbox, bbox[3] - bbox[1]))
    gap = int(font.size * 0.12)
    total_h = sum(h for _, h in line_heights) + gap * (len(lines) - 1)

    y = image.height - BOTTOM_MARGIN - total_h
    for line, (bbox, h) in zip(lines, line_heights):
        w = bbox[2] - bbox[0]
        x = (image.width - w) / 2 - bbox[0]
        draw.text(
            (x, y - bbox[1]),
            line,
            font=font,
            fill="white",
            stroke_width=STROKE_WIDTH,
            stroke_fill="black",
        )
        y += h + gap

    if episode_label:
        _draw_badge(image, episode_label)

    output = io.BytesIO()
    image.convert("RGB").save(output, format="PNG")
    return output.getvalue()
