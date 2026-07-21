# tests/images/test_generator.py
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from images.generator import ImageGenerationError, generate_background_image


def _fake_run_writing_output(png_bytes: bytes):
    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_bytes(png_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    return _run


def test_generate_background_image_returns_bytes_from_output_file():
    fake_bytes = b"fake png bytes"

    with patch(
        "images.generator.subprocess.run",
        side_effect=_fake_run_writing_output(fake_bytes),
    ) as mock_run:
        result = generate_background_image("cozy living room at dusk")

    assert result == fake_bytes

    cmd = mock_run.call_args.args[0]
    assert cmd[0].endswith("mflux-generate-flux2")
    assert cmd[cmd.index("--model") + 1] == "Runpod/FLUX.2-klein-4B-mflux-4bit"
    assert cmd[cmd.index("--base-model") + 1] == "flux2-klein-4b"
    assert cmd[cmd.index("--width") + 1] == "1024"
    assert cmd[cmd.index("--height") + 1] == "576"
    assert cmd[cmd.index("--steps") + 1] == "4"
    prompt = cmd[cmd.index("--prompt") + 1]
    assert prompt.startswith("cozy living room at dusk, ")
    assert "no text" in prompt


def test_generate_background_image_raises_on_nonzero_returncode():
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="", stderr="model load failed"
        )

    with patch("images.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ImageGenerationError, match="model load failed"):
            generate_background_image("a scene")


def test_generate_background_image_raises_when_output_file_missing_despite_success_code():
    def _run(cmd, **kwargs):
        # Simulates the known mflux-generate-flux2 no-op bug: returncode 0
        # but no file actually written.
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("images.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ImageGenerationError):
            generate_background_image("a scene")


def test_generate_background_image_cleans_up_temp_dir():
    fake_bytes = b"fake png bytes"
    captured_dirs = {}

    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        captured_dirs["dir"] = output_path.parent
        output_path.write_bytes(fake_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("images.generator.subprocess.run", side_effect=_run):
        generate_background_image("a scene")

    assert not captured_dirs["dir"].exists()
