import json
from pathlib import Path

from metadata import cli
from metadata.seo_generator import SeoCopy
from scripts.models import Chapter, Script


async def test_run_generates_metadata_and_renames_video(tmp_path, monkeypatch, capsys):
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

    tts_metadata = {
        "trope": "demo",
        "title": "Tiêu đề demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": 100.0},
            {"index": 2, "heading": "Chương 2", "start_seconds": 100.5, "end_seconds": 200.0},
        ],
    }
    tts_metadata_path = tmp_path / "tts.json"
    tts_metadata_path.write_text(
        json.dumps(tts_metadata, ensure_ascii=False), encoding="utf-8"
    )

    video_path = tmp_path / "demo-20260722T000000Z.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_seo_copy = SeoCopy(
        title="Video Demo Hấp Dẫn",
        description_draft="Mô tả nháp hấp dẫn.",
        tags=["tag1", "tag2"],
        hashtags=["#tag1"],
    )

    async def fake_generate_seo_copy(script, client):
        return fake_seo_copy

    monkeypatch.setattr(cli, "generate_seo_copy", fake_generate_seo_copy)

    fake_gemini_client = object()
    await cli._run(
        script_path, tts_metadata_path, video_path, gemini_client=fake_gemini_client
    )

    saved_txt = list((tmp_path / "output").glob("*.txt"))
    assert len(saved_txt) == 1

    new_video_path = tmp_path / "video-demo-hap-dan.mp4"
    assert new_video_path.exists()
    assert not video_path.exists()

    out = capsys.readouterr().out
    assert "Đã lưu metadata SEO" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, tts_metadata_path, video_path, gemini_client=None):
        calls.append((script_path, tts_metadata_path, video_path))

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "script.json", "tts.json", "video.mp4"]
    )

    cli.main()

    assert calls == [(Path("script.json"), Path("tts.json"), Path("video.mp4"))]
