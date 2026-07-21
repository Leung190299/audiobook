# images/generator.py
import subprocess
import tempfile
from pathlib import Path

from images.style import STYLE_SUFFIX

MODEL = "schnell"
WIDTH = 1024
HEIGHT = 576
STEPS = 4
QUANTIZE = 4


class ImageGenerationError(Exception):
    pass


def generate_background_image(scene_description: str) -> bytes:
    prompt = f"{scene_description}, {STYLE_SUFFIX}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "output.png"

        try:
            subprocess.run(
                [
                    "mflux-generate",
                    "--model", MODEL,
                    "--steps", str(STEPS),
                    "--quantize", str(QUANTIZE),
                    "--height", str(HEIGHT),
                    "--width", str(WIDTH),
                    "--low-ram",
                    "--prompt", prompt,
                    "--output", str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            raise ImageGenerationError(
                f"mflux-generate lỗi (exit code {exc.returncode}): {exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ImageGenerationError(
                "mflux-generate quá thời gian chờ (10 phút)"
            ) from exc

        if not output_path.exists():
            raise ImageGenerationError(
                "mflux-generate chạy xong nhưng không tạo ra file ảnh output"
            )

        return output_path.read_bytes()
