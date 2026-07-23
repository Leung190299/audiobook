# thumbnail/generator.py
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from thumbnail.style import THUMBNAIL_STYLE_SUFFIX

MODEL = "Runpod/FLUX.2-klein-4B-mflux-4bit"
BASE_MODEL = "flux2-klein-4b"
WIDTH = 1280
HEIGHT = 720
STEPS = 8


class ThumbnailGenerationError(Exception):
    pass


def _resolve_mflux_cli() -> str:
    venv_cli = os.path.join(".venv", "bin", "mflux-generate-flux2")
    return venv_cli if os.path.exists(venv_cli) else "mflux-generate-flux2"


def generate_thumbnail_image(visual_description: str) -> bytes:
    prompt = f"{visual_description}, {THUMBNAIL_STYLE_SUFFIX}"

    tmp_dir = tempfile.mkdtemp(prefix="mflux-thumbnail-")
    try:
        output_path = Path(tmp_dir) / "thumbnail.png"

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
            raise ThumbnailGenerationError(
                f"Không thể gọi {_resolve_mflux_cli()}: {exc}"
            ) from exc

        if result.returncode != 0:
            raise ThumbnailGenerationError(
                f"Lỗi khi gọi mflux sinh thumbnail: {result.stderr or result.stdout}"
            )

        if not output_path.exists():
            raise ThumbnailGenerationError(
                "mflux-generate-flux2 trả về thành công (returncode 0) nhưng không ghi ra file output — "
                "có thể do lỗi no-op đã biết của công cụ"
            )

        return output_path.read_bytes()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
