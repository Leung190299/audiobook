import json
from pathlib import Path

import numpy as np

from scripts.models import Chapter, Script
from tts import cli


def _fake_chapter_audio(duration_seconds=1.0, sample_rate=24000, amplitude=0.1) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class _FakeModel:
    def generate(self, text, instruct):
        return [_fake_chapter_audio()]


def test_run_generates_normalizes_concatenates_and_saves(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    voice_path = tmp_path / "voice.yaml"
    voice_path.write_text(
        "instruction: test voice\ntarget_lufs: -16.0\nsample_rate: 24000\ngap_seconds: 0.1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "VOICE_CONFIG_PATH", voice_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    cli._run(script_path, model=_FakeModel())

    saved_audio = list((tmp_path / "output").glob("*.wav"))
    assert len(saved_audio) == 1

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    assert len(saved_metadata) == 1
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["heading"] == "Chương 1"

    out = capsys.readouterr().out
    assert "Đã lưu audio" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda script_path, model=None: calls.append(script_path))
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
