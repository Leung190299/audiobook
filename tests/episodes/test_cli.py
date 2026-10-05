import json
import subprocess

import pytest

from episodes import cli as episodes_cli


@pytest.fixture
def patched(sandbox, monkeypatch):
    repo_root = sandbox["repo_root"]
    monkeypatch.setattr(episodes_cli, "REPO_ROOT", repo_root)
    monkeypatch.setattr(episodes_cli, "REMOTION_DIR", repo_root / "remotion")
    monkeypatch.setattr(episodes_cli, "OUTPUT_DIR", repo_root / "output" / "episodes")
    (repo_root / "remotion").mkdir()

    calls: list[list[str]] = []

    def fake_run(cmd, capture_output, text, cwd):
        calls.append(cmd)
        # Remotion thật ghi file mp4 ở tham số thứ 6.
        out = cmd[5]
        with open(out, "wb") as f:
            f.write(b"mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(episodes_cli.subprocess, "run", fake_run)
    return sandbox, calls


def test_cli_render_moi_tap_va_ghi_manifest(patched, capsys):
    sandbox, calls = patched
    manifest_path = episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], sandbox["images_path"])

    out = capsys.readouterr().out
    assert "Đã render tập 1/3:" in out
    assert "Đã render tập 3/3:" in out
    assert f"Manifest: {manifest_path}" in out
    assert "Đã render 3 tập vào" in out

    assert len(calls) == 3
    for cmd in calls:
        assert cmd[:5] == ["npx", "remotion", "render", "src/index.ts", "MainVideo"]
        assert cmd[5].endswith(".mp4")
        assert cmd[6].startswith("--props=") and cmd[6].endswith("-props.json")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["title"] and manifest["hook"] and manifest["comment_question"]
    eps = manifest["episodes"]
    assert [e["number"] for e in eps] == [1, 2, 3]
    assert [(e["first_chapter"], e["last_chapter"]) for e in eps] == [(1, 2), (3, 4), (5, 6)]
    for e in eps:
        assert e["video_path"].endswith(f"-ep-0{e['number']}.mp4")
        assert e["duration_seconds"] > 0
        assert e["chapters"][0]["start_seconds"] == 0.0
        assert len(e["chapters"]) == 3  # Mở đầu + 2 chương
        props = json.loads(open(e["props_path"], encoding="utf-8").read())
        assert props["episodeLabel"] == f"TẬP {e['number']}/3"


def test_cli_remotion_loi_thi_dung(patched, monkeypatch):
    sandbox, _ = patched

    def failing_run(cmd, capture_output, text, cwd):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(episodes_cli.subprocess, "run", failing_run)
    with pytest.raises(episodes_cli.EpisodeRenderError, match="boom"):
        episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], sandbox["images_path"])


def test_cli_thieu_wav_thi_loi(patched):
    sandbox, _ = patched
    sandbox["wav_path"].unlink()
    with pytest.raises(episodes_cli.EpisodeRenderError, match="wav"):
        episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], sandbox["images_path"])


def test_khong_anh_ma_khong_co_video_nen_thi_dung_som(patched):
    """Bỏ stage 3 mà thư mục video nền trống (conftest trỏ nó sang thư mục tạm
    rỗng): render tiếp là ra 40 phút màn hình đen giữa hai tấm thương hiệu."""
    sandbox, calls = patched

    with pytest.raises(episodes_cli.EpisodeRenderError, match="video nền"):
        episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], None)
    assert calls == [], "không được gọi Remotion khi biết chắc sẽ ra màn hình đen"


def test_khong_anh_co_video_nen_thi_render_binh_thuong(patched, monkeypatch):
    sandbox, calls = patched
    monkeypatch.setattr(
        episodes_cli.backgrounds, "choose",
        lambda **kw: {"backgroundVideo": "assets/backgrounds/.prepared/a-h576.mp4",
                      "backgroundVideoSeconds": 300.0, "backgroundVideoAspect": 0.5625},
    )

    manifest_path = episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], None)

    assert manifest_path.exists()
    assert len(calls) >= 1


def test_render_voi_chat_luong_khung_cao(patched):
    """Mặc định Remotion nén khung trung gian JPEG 80, làm nhoè viền chữ."""
    sandbox, calls = patched

    episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], sandbox["images_path"])

    render = [c for c in calls if "render" in c][0]
    assert "--jpeg-quality=95" in render
