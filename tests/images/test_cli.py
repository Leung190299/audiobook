import json
from pathlib import Path

from images import cli
from scripts.models import Chapter, Script


async def test_run_generates_scene_descriptions_and_images_and_saves(
    tmp_path, monkeypatch, capsys
):
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

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_gemini_client = object()
    fake_flux_client = object()

    async def fake_generate_scene_description(chapter, client):
        assert client is fake_gemini_client
        return f"scene for chapter {chapter.index}"

    def fake_generate_background_image(scene_description, client):
        assert client is fake_flux_client
        return f"fake image bytes for {scene_description}".encode("utf-8")

    monkeypatch.setattr(cli, "generate_scene_description", fake_generate_scene_description)
    monkeypatch.setattr(cli, "generate_background_image", fake_generate_background_image)

    await cli._run(script_path, gemini_client=fake_gemini_client, flux_client=fake_flux_client)

    saved_images = sorted((tmp_path / "output").glob("*.png"))
    assert len(saved_images) == 2

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    assert len(saved_metadata) == 1
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["scene_description"] == "scene for chapter 1"

    out = capsys.readouterr().out
    assert "Đã lưu 2 ảnh" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, gemini_client=None, flux_client=None):
        calls.append(script_path)

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
