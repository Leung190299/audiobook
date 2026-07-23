# tests/thumbnail/test_compositor.py
import io

from PIL import Image

from thumbnail.compositor import (
    MAX_FONT_SIZE,
    STROKE_WIDTH,
    TEXT_WIDTH_RATIO,
    _fit_font,
    overlay_hook_text,
)


def _make_test_image_bytes(width: int = 1280, height: int = 720) -> bytes:
    image = Image.new("RGB", (width, height), "gray")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_overlay_hook_text_returns_valid_png_same_size():
    image_bytes = _make_test_image_bytes()

    result = overlay_hook_text(image_bytes, "PHẢN ĐÒN")

    result_image = Image.open(io.BytesIO(result))
    assert result_image.format == "PNG"
    assert result_image.size == (1280, 720)


def test_overlay_hook_text_uppercases_input():
    image_bytes = _make_test_image_bytes()

    # Should not raise regardless of input case.
    result = overlay_hook_text(image_bytes, "chữ thường")

    result_image = Image.open(io.BytesIO(result))
    assert result_image.size == (1280, 720)


def test_fit_font_uses_max_size_for_short_text():
    image = Image.new("RGB", (1280, 720), "gray")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)

    font = _fit_font(draw, "SỐC", image.width)

    assert font.size == MAX_FONT_SIZE


def test_fit_font_shrinks_long_text_to_fit_width():
    image = Image.new("RGB", (1280, 720), "gray")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    long_hook = "MỘT CÂU HOOK RẤT LÀ DÀI ĐỂ KIỂM TRA CO CHỮ TỰ ĐỘNG THU NHỎ LẠI"

    font = _fit_font(draw, long_hook, image.width)

    bbox = draw.textbbox((0, 0), long_hook, font=font, stroke_width=STROKE_WIDTH)
    text_width = bbox[2] - bbox[0]
    assert text_width <= image.width * TEXT_WIDTH_RATIO
    assert font.size < MAX_FONT_SIZE
