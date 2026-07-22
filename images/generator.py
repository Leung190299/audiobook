# images/generator.py
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from images.style import STYLE_SUFFIX

MODEL = "Runpod/FLUX.2-klein-4B-mflux-4bit"
BASE_MODEL = "flux2-klein-4b"
WIDTH = 1024
HEIGHT = 576
STEPS = 4


class ImageGenerationError(Exception):
    pass


def _resolve_mflux_cli() -> str:
    venv_cli = os.path.join(".venv", "bin", "mflux-generate-flux2")
    return venv_cli if os.path.exists(venv_cli) else "mflux-generate-flux2"


def generate_background_image(scene_description: str) -> bytes:
    prompt = f"{scene_description}, {STYLE_SUFFIX}"

    tmp_dir = tempfile.mkdtemp(prefix="mflux-image-")
    try:
        output_path = Path(tmp_dir) / "scene.png"

        cmd = [
            _resolve_mflux_cli(),
            "--model", MODEL,
            "--base-model", BASE_MODEL,
            "--prompt", prompt,
            "--steps", str(STEPS),
            "--width", str(WIDTH),
            "--height", str(HEIGHT),
            "--output", str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as exc:
            raise ImageGenerationError(
                f"Không thể gọi {_resolve_mflux_cli()}: {exc}"
            ) from exc

        if result.returncode != 0:
            raise ImageGenerationError(
                f"Lỗi khi gọi mflux sinh ảnh: {result.stderr or result.stdout}"
            )

        if not output_path.exists():
            raise ImageGenerationError(
                "mflux-generate-flux2 trả về thành công (returncode 0) nhưng không ghi ra file output — "
                "có thể do lỗi no-op đã biết của công cụ"
            )

        return output_path.read_bytes()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
