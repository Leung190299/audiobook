import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from video import cli


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    script_path = tmp_path / "script.json"
    _write_json(
        script_path,
        {
            "trope": "demo",
            "title": "T",
            "chapters": [{"index": 1, "heading": "C1", "text": "Noi dung"}],
        },
    )

    tts_metadata_path = tmp_path / "tts.json"
    _write_json(
        tts_metadata_path,
        {
            "trope": "demo",
            "title": "T",
            "sample_rate": 24000,
            "chapters": [
                {"index": 1, "heading": "C1", "start_seconds": 0.0, "end_seconds": 2.0}
            ],
        },
    )
    (tmp_path / "tts.wav").write_bytes(b"fake wav")

    images_metadata_path = tmp_path / "images.json"
    _write_json(
        images_metadata_path,
        {
            "trope": "demo",
            "title": "T",
            "chapters": [
                {"index": 1, "filename": "demo-chapter-1.png", "scene_description": "a"}
            ],
        },
    )

    return script_path, tts_metadata_path, images_metadata_path


def test_run_builds_props_and_renders_video(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    # REPO_ROOT must be an ancestor of the fixture files for build_video_props'
    # Path.relative_to() to succeed — tmp_path stands in for the repo root here.
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    script_path, tts_metadata_path, images_metadata_path = _write_fixture_inputs(tmp_path)

    def fake_run(cmd, **kwargs):
        output_path = Path(cmd[5])
        output_path.write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("video.cli.subprocess.run", side_effect=fake_run) as mock_run:
        result_path = cli._run(script_path, tts_metadata_path, images_metadata_path)

    assert result_path.exists()
    assert result_path.suffix == ".mp4"

    cmd = mock_run.call_args.args[0]
    kwargs = mock_run.call_args.kwargs
    assert kwargs["cwd"] == cli.REMOTION_DIR
    assert cmd[:5] == ["npx", "remotion", "render", "src/index.ts", "MainVideo"]
    assert cmd[5] == str(result_path)
    assert cmd[6].startswith("--props=")
    assert cmd[7] == f"--public-dir={tmp_path}"

    # audio/image paths are relative to REPO_ROOT (tmp_path here), not absolute
    props_path = Path(cmd[6].removeprefix("--props="))
    saved_props = json.loads(props_path.read_text(encoding="utf-8"))
    assert saved_props["audioPath"] == "tts.wav"
    assert saved_props["chapters"][0]["imagePath"] == "demo-chapter-1.png"


def test_run_raises_on_render_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    script_path, tts_metadata_path, images_metadata_path = _write_fixture_inputs(tmp_path)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="render failed")

    with patch("video.cli.subprocess.run", side_effect=fake_run):
        with pytest.raises(cli.VideoRenderError, match="render failed"):
            cli._run(script_path, tts_metadata_path, images_metadata_path)


def test_run_raises_when_output_file_missing_despite_success_code(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    script_path, tts_metadata_path, images_metadata_path = _write_fixture_inputs(tmp_path)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("video.cli.subprocess.run", side_effect=fake_run):
        with pytest.raises(cli.VideoRenderError, match="file video không được tạo"):
            cli._run(script_path, tts_metadata_path, images_metadata_path)


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    def fake_run(script_path, tts_metadata_path, images_metadata_path):
        calls.append((script_path, tts_metadata_path, images_metadata_path))
        return Path("/fake/output.mp4")

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "script.json", "tts.json", "images.json"]
    )

    cli.main()

    assert calls == [(Path("script.json"), Path("tts.json"), Path("images.json"))]
