# tests/images/test_generator.py
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import images.generator as generator_module
from images.generator import ImageGenerationError, generate_background_image


def test_generate_background_image_returns_file_bytes(monkeypatch):
    written = {}

    def fake_run(cmd, check, capture_output, text, timeout):
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_bytes(b"fake png bytes")
        written["cmd"] = cmd
        return MagicMock(returncode=0)

    monkeypatch.setattr(generator_module.subprocess, "run", fake_run)

    image_bytes = generate_background_image("cozy living room at dusk")

    assert image_bytes == b"fake png bytes"
    cmd = written["cmd"]
    joined = " ".join(cmd)
    assert "cozy living room at dusk," in joined
    assert "no text" in joined
    assert cmd[cmd.index("--model") + 1] == "schnell"
    assert cmd[cmd.index("--quantize") + 1] == "4"
    assert cmd[cmd.index("--height") + 1] == "576"
    assert cmd[cmd.index("--width") + 1] == "1024"
    assert "--low-ram" in cmd


def test_generate_background_image_raises_on_process_error(monkeypatch):
    def fake_run(cmd, check, capture_output, text, timeout):
        raise subprocess.CalledProcessError(1, cmd, stderr="mflux crashed")

    monkeypatch.setattr(generator_module.subprocess, "run", fake_run)

    with pytest.raises(ImageGenerationError):
        generate_background_image("a scene")


def test_generate_background_image_raises_on_timeout(monkeypatch):
    def fake_run(cmd, check, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(generator_module.subprocess, "run", fake_run)

    with pytest.raises(ImageGenerationError, match="thời gian"):
        generate_background_image("a scene")


def test_generate_background_image_raises_when_output_file_missing(monkeypatch):
    def fake_run(cmd, check, capture_output, text, timeout):
        return MagicMock(returncode=0)

    monkeypatch.setattr(generator_module.subprocess, "run", fake_run)

    with pytest.raises(ImageGenerationError):
        generate_background_image("a scene")


def test_generate_background_image_raises_when_mflux_generate_not_found(monkeypatch):
    def fake_run(cmd, check, capture_output, text, timeout):
        raise FileNotFoundError("mflux-generate not found")

    monkeypatch.setattr(generator_module.subprocess, "run", fake_run)

    with pytest.raises(ImageGenerationError, match="mflux-generate"):
        generate_background_image("a scene")
