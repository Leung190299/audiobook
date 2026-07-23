# tests/thumbnail/test_cli.py
import json
from pathlib import Path

from scripts.models import Chapter, Script
from thumbnail import cli
from thumbnail.prompt_generator import ThumbnailPrompt


async def test_run_generates_and_saves_thumbnail(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_prompt = ThumbnailPrompt(hook_text="SỐC", visual_description="a shocked face")

    async def fake_generate_thumbnail_prompt(script, client):
        return fake_prompt

    def fake_generate_thumbnail_image(visual_description):
        assert visual_description == "a shocked face"
        return b"fake raw image bytes"

    def fake_overlay_hook_text(image_bytes, hook_text):
        assert image_bytes == b"fake raw image bytes"
        assert hook_text == "SỐC"
        return b"fake final image bytes"

    monkeypatch.setattr(cli, "generate_thumbnail_prompt", fake_generate_thumbnail_prompt)
    monkeypatch.setattr(cli, "generate_thumbnail_image", fake_generate_thumbnail_image)
    monkeypatch.setattr(cli, "overlay_hook_text", fake_overlay_hook_text)

    fake_gemini_client = object()
    await cli._run(script_path, gemini_client=fake_gemini_client)

    saved = list((tmp_path / "output").glob("*.png"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"fake final image bytes"

    out = capsys.readouterr().out
    assert "Đã lưu thumbnail" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, gemini_client=None):
        calls.append(script_path)

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "script.json"])

    cli.main()

    assert calls == [Path("script.json")]
