import pytest
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

    def fake_overlay_hook_text(image_bytes, hook_text, episode_label=None):
        assert image_bytes == b"fake raw image bytes"
        assert hook_text == "SỐC"
        assert episode_label is None
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

    async def fake_run(script_path, gemini_client=None, episodes_manifest=None):
        calls.append((script_path, episodes_manifest))

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "script.json", "--episodes", "m.json"])

    cli.main()

    assert calls == [(Path("script.json"), Path("m.json"))]


async def test_run_voi_manifest_sinh_them_anh_moi_tap(tmp_path, monkeypatch, capsys):
    script = Script(trope="demo", title="T", chapters=[Chapter(index=1, heading="C1", text="x")])
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")
    manifest_path = tmp_path / "demo-episodes.json"
    manifest_path.write_text(
        json.dumps({"episodes": [{"number": 1, "total": 3}, {"number": 2, "total": 3}, {"number": 3, "total": 3}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    async def fake_prompt(script, client):
        return ThumbnailPrompt(hook_text="MẸ CHỒNG QUỲ XIN", visual_description="v")

    labels = []

    def fake_overlay(image_bytes, hook_text, episode_label=None):
        labels.append(episode_label)
        return f"img-{episode_label}".encode()

    monkeypatch.setattr(cli, "generate_thumbnail_prompt", fake_prompt)
    monkeypatch.setattr(cli, "generate_thumbnail_image", lambda v: b"raw")
    monkeypatch.setattr(cli, "overlay_hook_text", fake_overlay)

    await cli._run(script_path, gemini_client=object(), episodes_manifest=manifest_path)

    assert labels == [None, "TẬP 1/3", "TẬP 2/3", "TẬP 3/3"]
    files = sorted(p.name for p in (tmp_path / "output").glob("*.png"))
    assert len(files) == 4
    assert [f for f in files if "-ep-" in f] == sorted(f for f in files if "-ep-" in f)
    assert any(f.endswith("-ep-02.png") for f in files)
    out = capsys.readouterr().out
    assert "Đã lưu thumbnail:" in out and "Thumbnail tập 3/3:" in out


# --- từ khoá không khớp tiêu đề thì báo lỗi, không tự đoán (spec 24/09 §4) ---


def test_kiem_tra_tu_khoa_khong_khop_thi_bao_loi_neu_ro_tu_khoa():
    from thumbnail.cli import ThumbnailInputError, check_thumb_keywords

    with pytest.raises(ThumbnailInputError) as exc:
        check_thumb_keywords("Bác Cả Đòi Chia Đất", ["Livestream Luôn"])

    msg = str(exc.value)
    assert "Livestream Luôn" in msg  # nêu đúng từ khoá hỏng
    assert "Bác Cả Đòi Chia Đất" in msg  # và chữ trên thumbnail để đối chiếu


def test_kiem_tra_tu_khoa_khop_thi_khong_sao():
    from thumbnail.cli import check_thumb_keywords

    check_thumb_keywords("Bác Cả Đòi Chia Đất", ["Chia Đất", "Bác Cả"])


def test_kiem_tra_khong_phan_biet_hoa_thuong():
    from thumbnail.cli import check_thumb_keywords

    check_thumb_keywords("Bác Cả Đòi Chia Đất", ["chia đất"])


def test_khong_co_tu_khoa_thi_bo_qua():
    from thumbnail.cli import check_thumb_keywords

    check_thumb_keywords("Bác Cả Đòi Chia Đất", [])
