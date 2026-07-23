# tests/thumbnail/test_generator.py
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from thumbnail.generator import ThumbnailGenerationError, generate_thumbnail_image


def _fake_run_writing_output(png_bytes: bytes):
    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_bytes(png_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    return _run


def test_generate_thumbnail_image_returns_bytes_from_output_file():
    fake_bytes = b"fake png bytes"

    with patch(
        "thumbnail.generator.subprocess.run",
        side_effect=_fake_run_writing_output(fake_bytes),
    ) as mock_run:
        result = generate_thumbnail_image("a shocked young woman, dramatic lighting")

    assert result == fake_bytes

    cmd = mock_run.call_args.args[0]
    assert cmd[0].endswith("mflux-generate-flux2")
    assert cmd[cmd.index("--model") + 1] == "Runpod/FLUX.2-klein-4B-mflux-4bit"
    assert cmd[cmd.index("--base-model") + 1] == "flux2-klein-4b"
    assert cmd[cmd.index("--width") + 1] == "1280"
    assert cmd[cmd.index("--height") + 1] == "720"
    assert cmd[cmd.index("--steps") + 1] == "8"
    prompt = cmd[cmd.index("--prompt") + 1]
    assert prompt.startswith("a shocked young woman, dramatic lighting, ")
    assert "no text" in prompt
    assert "close-up" in prompt


def test_generate_thumbnail_image_raises_on_nonzero_returncode():
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="", stderr="model load failed"
        )

    with patch("thumbnail.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ThumbnailGenerationError, match="model load failed"):
            generate_thumbnail_image("a scene")


def test_generate_thumbnail_image_raises_on_missing_binary():
    with patch(
        "thumbnail.generator.subprocess.run",
        side_effect=FileNotFoundError("mflux-generate-flux2 not found"),
    ):
        with pytest.raises(ThumbnailGenerationError) as exc_info:
            generate_thumbnail_image("a scene")

        error_msg = str(exc_info.value)
        assert "mflux-generate-flux2" in error_msg
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, FileNotFoundError)


def test_generate_thumbnail_image_raises_when_output_file_missing_despite_success_code():
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("thumbnail.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ThumbnailGenerationError) as exc_info:
            generate_thumbnail_image("a scene")

        error_msg = str(exc_info.value)
        assert "returncode 0" in error_msg
        assert "no-op" in error_msg.lower() or "không ghi ra" in error_msg


def test_generate_thumbnail_image_cleans_up_temp_dir():
    fake_bytes = b"fake png bytes"
    captured_dirs = {}

    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        captured_dirs["dir"] = output_path.parent
        output_path.write_bytes(fake_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("thumbnail.generator.subprocess.run", side_effect=_run):
        generate_thumbnail_image("a scene")

    assert not captured_dirs["dir"].exists()
