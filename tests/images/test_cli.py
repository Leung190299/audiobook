import json
from pathlib import Path

import pytest

from images import cli
from images.scene_prompt import ScenePromptError
from scripts.models import Chapter, Script


def _write_inputs(tmp_path):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Một. Hai."),
            Chapter(index=2, heading="Chương 2", text="Ba."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    tts_metadata = {
        "trope": "demo", "title": "Tiêu đề demo", "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": 100.0},
            {"index": 2, "heading": "Chương 2", "start_seconds": 100.5, "end_seconds": 130.5},
        ],
        "sentences": [
            {"chapter_index": 1, "index": 1, "text": "Một.", "start_seconds": 0.0, "end_seconds": 50.0},
            {"chapter_index": 1, "index": 2, "text": "Hai.", "start_seconds": 50.0, "end_seconds": 100.0},
            {"chapter_index": 2, "index": 1, "text": "Ba.", "start_seconds": 100.5, "end_seconds": 130.5},
        ],
    }
    tts_path = tmp_path / "audio.json"
    tts_path.write_text(json.dumps(tts_metadata, ensure_ascii=False), encoding="utf-8")
    return script_path, tts_path


async def test_run_chia_canh_ta_canh_ve_anh_va_luu(tmp_path, monkeypatch, capsys):
    script_path, tts_path = _write_inputs(tmp_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    fake_gemini_client = object()
    described = []

    async def fake_generate_scene_description(chapter_index, scene_number, text, client):
        assert client is fake_gemini_client
        described.append((chapter_index, scene_number, text))
        return f"scene {chapter_index}.{scene_number}"

    def fake_generate_background_image(scene_description):
        return f"png for {scene_description}".encode("utf-8")

    monkeypatch.setattr(cli, "generate_scene_description", fake_generate_scene_description)
    monkeypatch.setattr(cli, "generate_background_image", fake_generate_background_image)

    await cli._run(script_path, tts_path, gemini_client=fake_gemini_client)

    # Chương 1 dài 100s -> 2 cảnh; chương 2 dài 30s -> 1 cảnh. Mô tả nhận đúng
    # đoạn văn của cảnh, không phải cả chương.
    assert described == [(1, 1, "Một."), (1, 2, "Hai."), (2, 1, "Ba.")]

    saved_images = sorted((tmp_path / "output").glob("*.png"))
    assert [p.name.split("-", 2)[2] for p in saved_images] == [
        "chapter-1-scene-1.png", "chapter-1-scene-2.png", "chapter-2-scene-1.png",
    ]
    data = json.loads(next((tmp_path / "output").glob("*.json")).read_text(encoding="utf-8"))
    assert data["chapters"][0]["scenes"][1]["scene_description"] == "scene 1.2"

    out = capsys.readouterr().out
    assert "Cảnh 1/3: chương 1 cảnh 1 (00:00–00:50)" in out
    assert "Đã lưu 3 ảnh vào" in out
    assert "Metadata: " in out


async def test_run_thu_lai_khi_gemini_loi_thoang_qua(tmp_path, monkeypatch):
    script_path, tts_path = _write_inputs(tmp_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "RETRY_DELAY_SECONDS", 0)
    calls = []

    async def fake_generate_scene_description(chapter_index, scene_number, text, client):
        calls.append((chapter_index, scene_number))
        if len(calls) == 1:
            raise ScenePromptError("lỗi thoáng qua")
        return f"scene {chapter_index}.{scene_number}"

    monkeypatch.setattr(cli, "generate_scene_description", fake_generate_scene_description)
    monkeypatch.setattr(
        cli, "generate_background_image", lambda description: description.encode("utf-8")
    )

    await cli._run(script_path, tts_path, gemini_client=object())

    # Lần đầu hỏng, lần hai mới thành công cho cảnh 1 -- vẫn được gọi lại đúng
    # cảnh đó, không bỏ qua hay lặp sang cảnh khác.
    assert calls == [(1, 1), (1, 1), (1, 2), (2, 1)]


async def test_run_het_luot_thu_van_loi_thi_nem_ngoai(tmp_path, monkeypatch):
    script_path, tts_path = _write_inputs(tmp_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "RETRY_DELAY_SECONDS", 0)
    calls = []

    async def always_fails(chapter_index, scene_number, text, client):
        calls.append((chapter_index, scene_number))
        raise ScenePromptError("lỗi dai dẳng")

    monkeypatch.setattr(cli, "generate_scene_description", always_fails)

    with pytest.raises(ScenePromptError, match="lỗi dai dẳng"):
        await cli._run(script_path, tts_path, gemini_client=object())

    # Đúng SCENE_ATTEMPTS lần cho cảnh đầu tiên rồi ném ra ngoài, không thử
    # sang cảnh kế tiếp.
    assert calls == [(1, 1)] * cli.SCENE_ATTEMPTS


async def test_run_tu_choi_khi_tts_khong_khop_script(tmp_path, monkeypatch):
    script_path, tts_path = _write_inputs(tmp_path)
    tts = json.loads(tts_path.read_text(encoding="utf-8"))
    tts["title"] = "Tập khác"
    tts_path.write_text(json.dumps(tts, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    with pytest.raises(cli.ImagesInputError, match="trope/title"):
        await cli._run(script_path, tts_path, gemini_client=object())


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, tts_metadata_path, gemini_client=None):
        calls.append((script_path, tts_metadata_path))

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json", "some/audio.json"])

    cli.main()

    assert calls == [(Path("some/script.json"), Path("some/audio.json"))]
