# images/generator.py
import base64
import os

from together import Together

from images.style import STYLE_SUFFIX

MODEL = "black-forest-labs/FLUX.1-schnell-Free"
WIDTH = 1024
HEIGHT = 576
STEPS = 4


class ImageGenerationError(Exception):
    pass


def generate_background_image(
    scene_description: str, client: "Together | None" = None
) -> bytes:
    client = client or Together(api_key=os.environ["TOGETHER_API_KEY"])

    prompt = f"{scene_description}, {STYLE_SUFFIX}"

    try:
        response = client.images.generate(
            model=MODEL,
            prompt=prompt,
            width=WIDTH,
            height=HEIGHT,
            steps=STEPS,
            n=1,
            response_format="base64",
        )
    except Exception as exc:
        raise ImageGenerationError(f"Lỗi khi gọi Flux sinh ảnh: {exc}") from exc

    try:
        b64_data = response.data[0].b64_json
    except (AttributeError, IndexError, TypeError) as exc:
        raise ImageGenerationError(
            f"Kết quả Together AI không đúng định dạng mong đợi: {exc}"
        ) from exc

    return base64.b64decode(b64_data)
