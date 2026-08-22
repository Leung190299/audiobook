# tests/shorts/test_cli.py
import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from shorts import cli as shorts_cli
from shorts.excerpt import ShortExcerpt


def _excerpt() -> ShortExcerpt:
    return ShortExcerpt(
        chapter_index=2,
        hook_text="CÔ ẤY BIẾT HẾT RỒI",
        excerpt_text="Cô ấy bước vào phòng khách. Trời đổ mưa rất to.",
        short_title="Tiêu đề short",
        short_description="Nghe full trên kênh. #shorts",
    )


class _FakeModel:
    """Trả về 0.5 giây âm thanh cho mỗi câu, đủ để tính mốc thời gian.

    Phải là sóng có biên độ thật chứ không phải toàn số 0: chuẩn hoá độ ồn của
    im lặng tuyệt đối cho ra NaN, khiến pyloudnorm bắn RuntimeWarning.
    """

    def infer(self, **kwargs):
        t = np.arange(12000, dtype=np.float32) / 24000
        return (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch):
    repo_root = tmp_path
    (repo_root / "config").mkdir()
    (repo_root / "config" / "voice.yaml").write_text(
        "voice: 'Thục Đoan'\nstyle: 'normal'\ntarget_lufs: -16.0\n"
        "sample_rate: 24000\ngap_seconds: 0.5\n",
        encoding="utf-8",
    )

    scripts_dir = repo_root / "output" / "scripts"
    scripts_dir.mkdir(parents=True)
    script_path = scripts_dir / "trong_sinh_bao_thu-20260822T000000Z.json"
    script_path.write_text(
        json.dumps(
            {
                "trope": "trong_sinh_bao_thu",
                "title": "Trọng Sinh Báo Thù",
                "chapters": [
                    {"index": 1, "heading": "Chương 1", "text": "..."},
                    {"index": 2, "heading": "Chương 2", "text": "..."},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-2.png").write_bytes(b"x")
    images_path = images_dir / "trong_sinh_bao_thu-20260822T000500Z.json"
    images_path.write_text(
        json.dumps(
            {
                "trope": "trong_sinh_bao_thu",
                "title": "Trọng Sinh Báo Thù",
                "chapters": [
                    {"index": 1, "filename": "anh-1.png", "scene_description": "..."},
                    {"index": 2, "filename": "anh-2.png", "scene_description": "..."},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_dir = repo_root / "output" / "shorts"

    monkeypatch.setattr(shorts_cli, "REPO_ROOT", repo_root)
    monkeypatch.setattr(shorts_cli, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(shorts_cli, "VOICE_CONFIG_PATH", repo_root / "config" / "voice.yaml")
    monkeypatch.setattr(
        shorts_cli.excerpt_module, "generate_short_excerpt", AsyncMock(return_value=_excerpt())
    )

    return script_path, images_path, output_dir


def _fake_render_ok():
    def _run(cmd, **kwargs):
        mp4 = [c for c in cmd if str(c).endswith(".mp4")][0]
        Path(mp4).write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return _run


async def test_chay_tron_ven_sinh_du_bon_file(sandbox, monkeypatch, capsys):
    script_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fake_render_ok())

    await shorts_cli._run(script_path, images_path, model=_FakeModel())

    suffixes = sorted(p.suffix for p in output_dir.iterdir())
    assert suffixes == [".json", ".mp4", ".txt", ".wav"]

    out = capsys.readouterr().out
    assert "Đã render short: " in out
    assert "Metadata short: " in out


async def test_goi_remotion_dung_composition_shortvideo(sandbox, monkeypatch):
    script_path, images_path, output_dir = sandbox
    seen = {}

    def _capture(cmd, **kwargs):
        seen["cmd"] = cmd
        mp4 = [c for c in cmd if str(c).endswith(".mp4")][0]
        Path(mp4).write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)

    await shorts_cli._run(script_path, images_path, model=_FakeModel())

    assert "ShortVideo" in seen["cmd"]
    assert any(str(c).startswith("--public-dir=") for c in seen["cmd"])


async def test_remotion_loi_thi_bao_loi(sandbox, monkeypatch):
    script_path, images_path, _ = sandbox

    def _fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="remotion hỏng")

    monkeypatch.setattr(subprocess, "run", _fail)

    with pytest.raises(shorts_cli.ShortRenderError, match="remotion hỏng"):
        await shorts_cli._run(script_path, images_path, model=_FakeModel())


async def test_remotion_bao_thanh_cong_nhung_khong_co_file(sandbox, monkeypatch):
    script_path, images_path, _ = sandbox

    def _lie(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _lie)

    with pytest.raises(shorts_cli.ShortRenderError, match="không có file"):
        await shorts_cli._run(script_path, images_path, model=_FakeModel())


async def test_moi_cau_duoc_doc_rieng(sandbox, monkeypatch):
    script_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fake_render_ok())

    calls = []

    class _CountingModel(_FakeModel):
        def infer(self, **kwargs):
            calls.append(kwargs.get("text"))
            return super().infer(**kwargs)

    await shorts_cli._run(script_path, images_path, model=_CountingModel())

    # Đoạn trích có đúng 2 câu -> 2 lần gọi TTS, không phải 1 lần cho cả đoạn.
    assert calls == ["Cô ấy bước vào phòng khách.", "Trời đổ mưa rất to."]
