# thumbnail/compositor.py
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "BeVietnamPro-Black.ttf"
)
MAX_FONT_SIZE = 100
# NOTE: measured against the actual bundled Be Vietnam Pro Black font at
# TEXT_WIDTH_RATIO=0.9 on a 1280px-wide canvas, very long hook strings need to
# shrink to ~30pt to fit. A floor of 40 was too high -- the shrink loop (step
# -4 from MAX_FONT_SIZE=100) never lands on a checked size below 44 in that
# case, so it fell through to a still-too-wide 40pt font. The floor is set
# lower here to give the loop room to actually reach a fitting size.
MIN_FONT_SIZE = 20
TEXT_WIDTH_RATIO = 0.9
STROKE_WIDTH = 6


def _fit_font(
    draw: "ImageDraw.ImageDraw", text: str, image_width: int
) -> "ImageFont.FreeTypeFont":
    max_text_width = image_width * TEXT_WIDTH_RATIO
    size = MAX_FONT_SIZE
    while size > MIN_FONT_SIZE:
        font = ImageFont.truetype(str(FONT_PATH), size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_text_width:
            return font
        size -= 4
    return ImageFont.truetype(str(FONT_PATH), MIN_FONT_SIZE)


def overlay_hook_text(image_bytes: bytes, hook_text: str) -> bytes:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)

    text = hook_text.upper()
    font = _fit_font(draw, text, image.width)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (image.width - text_width) / 2 - bbox[0]
    y = image.height * (2 / 3) - text_height / 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill="white",
        stroke_width=STROKE_WIDTH,
        stroke_fill="black",
    )

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
