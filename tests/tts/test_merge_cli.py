import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from scripts.models import Chapter, Script
from tts import merge_cli


def _write_chapter_audio(
    chapter_dir: Path, trope: str, index: int, heading: str, duration_seconds=1.0, sample_rate=24000
):
    chapter_dir.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    audio = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    stem = f"{trope}-ch{index}"
    audio_path = chapter_dir / f"{stem}.wav"
    sf.write(audio_path, audio, sample_rate)

    metadata_path = chapter_dir / f"{stem}.json"
    metadata_path.write_text(
        json.dumps(
            {
                "trope": trope,
                "title": "Tiêu đề demo",
                "sample_rate": sample_rate,
                "chapters": [
                    {
                        "index": index,
                        "heading": heading,
                        "start_seconds": 0.0,
                        "end_seconds": duration_seconds,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return audio_path, metadata_path


def _write_script(tmp_path: Path) -> Path:
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
    return script_path


def test_merge_combines_chapters_in_script_order(tmp_path, monkeypatch, capsys):
    script_path = _write_script(tmp_path)
    chapter_dir = tmp_path / "chapters"
    _write_chapter_audio(chapter_dir, "demo", 1, "Chương 1")
    _write_chapter_audio(chapter_dir, "demo", 2, "Chương 2")

    voice_path = tmp_path / "voice.yaml"
    voice_path.write_text(
        "instruction: test voice\ntarget_lufs: -16.0\nsample_rate: 24000\ngap_seconds: 0.5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(merge_cli, "VOICE_CONFIG_PATH", voice_path)
    monkeypatch.setattr(merge_cli, "OUTPUT_DIR", tmp_path / "output")

    merge_cli._run(script_path, chapter_dir)

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    assert len(saved_metadata) == 1
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert [c["index"] for c in data["chapters"]] == [1, 2]
    # 1s + 0.5s gap + 1s = 2.5s total
    assert data["chapters"][1]["start_seconds"] == pytest.approx(1.5)

    out = capsys.readouterr().out
    assert "Đã ghép 2 chương" in out


def test_merge_raises_on_missing_chapter(tmp_path, monkeypatch):
    script_path = _write_script(tmp_path)
    chapter_dir = tmp_path / "chapters"
    _write_chapter_audio(chapter_dir, "demo", 1, "Chương 1")

    voice_path = tmp_path / "voice.yaml"
    voice_path.write_text(
        "instruction: test voice\ntarget_lufs: -16.0\nsample_rate: 24000\ngap_seconds: 0.5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(merge_cli, "VOICE_CONFIG_PATH", voice_path)

    with pytest.raises(merge_cli.MergeError, match=r"\[2\]"):
        merge_cli._run(script_path, chapter_dir)
