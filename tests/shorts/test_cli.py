# tests/shorts/test_cli.py
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from shorts import cli as shorts_cli

TROPE = "trong_sinh_bao_thu"
TITLE = "Trọng Sinh Báo Thù"
SAMPLE_RATE = 24000


def _sentence(chapter_index: int, index: int, start: float, end: float) -> dict:
    return {
        "chapter_index": chapter_index,
        "index": index,
        "text": f"Câu {chapter_index}.{index}.",
        "start_seconds": start,
        "end_seconds": end,
    }


def _make_sentences(chapter_index: int, count: int, sentence_seconds: float, t0: float) -> list[dict]:
    out = []
    t = t0
    for i in range(1, count + 1):
        out.append(_sentence(chapter_index, i, t, t + sentence_seconds))
        t += sentence_seconds
    return out


def _tts_metadata(chapters_and_sentences: list[tuple[str, list[dict]]]) -> dict:
    chapters = []
    sentences = []
    for chapter_index, (heading, chapter_sentences) in enumerate(
        chapters_and_sentences, start=1
    ):
        chapters.append(
            {
                "index": chapter_index,
                "heading": heading,
                "start_seconds": chapter_sentences[0]["start_seconds"],
                "end_seconds": chapter_sentences[-1]["end_seconds"],
            }
        )
        sentences.extend(chapter_sentences)
    return {
        "trope": TROPE,
        "title": TITLE,
        "sample_rate": SAMPLE_RATE,
        "chapters": chapters,
        "sentences": sentences,
    }


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch):
    repo_root = tmp_path

    # Hai chương ngắn -> plan_teasers ra đúng 2 phần, mỗi chương một phần (không
    # bắc cầu qua ranh giới chương, xem shorts/planner.py).
    c1_sentences = _make_sentences(1, 3, sentence_seconds=3.0, t0=0.0)
    c2_sentences = _make_sentences(2, 3, sentence_seconds=3.0, t0=10.0)
    tts_metadata = _tts_metadata(
        [("Chương 1: Mở đầu", c1_sentences), ("Chương 2: Cao trào", c2_sentences)]
    )

    audio_dir = repo_root / "output" / "audio"
    audio_dir.mkdir(parents=True)
    tts_metadata_path = audio_dir / f"{TROPE}-20260822T000000Z.json"
    tts_metadata_path.write_text(
        json.dumps(tts_metadata, ensure_ascii=False), encoding="utf-8"
    )

    # File wav nguồn phải đủ dài để chứa mốc thời gian lớn nhất trong metadata
    # (chương 2 kết thúc ở 19s) -- suy ra từ .with_suffix(".wav") của đường dẫn
    # metadata, giống hệt video/cli.py.
    source_wav = tts_metadata_path.with_suffix(".wav")
    total_seconds = 20.0
    t = np.arange(int(total_seconds * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    audio = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(source_wav, audio, SAMPLE_RATE)

    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-1-1.png").write_bytes(b"x")
    (images_dir / "anh-2-1.png").write_bytes(b"x")
    images_metadata_path = images_dir / f"{TROPE}-20260822T000500Z.json"
    images_metadata_path.write_text(
        json.dumps(
            {
                "trope": TROPE,
                "title": TITLE,
                "chapters": [
                    {"index": 1, "scenes": [
                        {"number": 1, "start_seconds": 0.0, "end_seconds": 9.0,
                         "filename": "anh-1-1.png", "scene_description": "..."},
                    ]},
                    {"index": 2, "scenes": [
                        {"number": 1, "start_seconds": 10.0, "end_seconds": 19.0,
                         "filename": "anh-2-1.png", "scene_description": "..."},
                    ]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_dir = repo_root / "output" / "shorts"

    monkeypatch.setattr(shorts_cli, "REPO_ROOT", repo_root)
    monkeypatch.setattr(shorts_cli, "OUTPUT_DIR", output_dir)

    return tts_metadata_path, images_metadata_path, output_dir


def _fake_render_ok():
    def _run(cmd, **kwargs):
        # Cả lệnh render (.mp4) lẫn lệnh still (.jpg) đều đi qua đây -- ghi ra
        # đúng file mà lệnh đó nhắm tới, suy từ đuôi file trong cmd.
        for suffix in (".mp4", ".jpg"):
            matches = [c for c in cmd if str(c).endswith(suffix)]
            if matches:
                Path(matches[0]).write_bytes(f"fake {suffix}".encode())
                break
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return _run


def test_render_du_nam_file_cho_moi_phan(sandbox, monkeypatch):
    tts_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fake_render_ok())

    shorts_cli._run(tts_path, images_path)

    for n in ("01", "02"):
        stem = f"{TROPE}-"  # timestamp sinh động, chỉ kiểm tra hậu tố
        matches = list(output_dir.glob(f"*-part-{n}.wav"))
        assert len(matches) == 1
        assert list(output_dir.glob(f"*-part-{n}.mp4"))
        assert list(output_dir.glob(f"*-part-{n}-props.json"))
        assert list(output_dir.glob(f"*-part-{n}.txt"))
        assert list(output_dir.glob(f"*-part-{n}.json"))
        assert list(output_dir.glob(f"*-part-{n}.jpg"))


def test_in_du_ba_dong_cho_moi_phan_va_dong_tong_ket(sandbox, monkeypatch, capsys):
    tts_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fake_render_ok())

    shorts_cli._run(tts_path, images_path)

    out = capsys.readouterr().out
    lines = out.strip().splitlines()

    render_lines = [l for l in lines if l.startswith("Đã render short: ")]
    metadata_lines = [l for l in lines if l.startswith("Metadata short: ")]
    metadata_json_lines = [l for l in lines if l.startswith("Metadata JSON short: ")]
    thumbnail_lines = [l for l in lines if l.startswith("Ảnh bìa short: ")]
    assert len(render_lines) == 2
    assert len(metadata_lines) == 2
    assert len(metadata_json_lines) == 2
    assert len(thumbnail_lines) == 2
    # Thứ tự trong mỗi phần: render, metadata, metadata JSON rồi ảnh bìa --
    # không dồn lại cuối. Hai dòng đầu (render, metadata) là hợp đồng với
    # run_daily.sh/n8n, dòng metadata JSON thêm ngay sau đó.
    assert lines[0].startswith("Đã render short: ")
    assert lines[1].startswith("Metadata short: ")
    assert lines[2].startswith("Metadata JSON short: ")
    assert lines[3].startswith("Ảnh bìa short: ")
    assert lines[4].startswith("Đã render short: ")
    assert lines[5].startswith("Metadata short: ")
    assert lines[6].startswith("Metadata JSON short: ")
    assert lines[7].startswith("Ảnh bìa short: ")
    assert lines[-1] == "Đã render 2 short vào output/shorts"


def test_goi_remotion_hai_lan_moi_phan_render_roi_still(sandbox, monkeypatch):
    tts_path, images_path, output_dir = sandbox
    seen_cmds = []

    def _capture(cmd, **kwargs):
        seen_cmds.append(cmd)
        for suffix in (".mp4", ".jpg"):
            matches = [c for c in cmd if str(c).endswith(suffix)]
            if matches:
                Path(matches[0]).write_bytes(f"fake {suffix}".encode())
                break
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)

    shorts_cli._run(tts_path, images_path)

    # Mỗi phần gọi đúng hai lệnh Remotion: render (.mp4, ShortVideo) rồi still
    # (.jpg, ShortThumbnail), theo đúng thứ tự đó.
    assert len(seen_cmds) == 4
    for cmd in (seen_cmds[0], seen_cmds[2]):
        assert "render" in cmd
        assert "ShortVideo" in cmd
        assert any(str(c).startswith("--public-dir=") for c in cmd)
    for cmd in (seen_cmds[1], seen_cmds[3]):
        assert "still" in cmd
        assert "ShortThumbnail" in cmd
        assert any(str(c).startswith("--public-dir=") for c in cmd)


def test_trope_title_lech_giua_hai_metadata_thi_bao_loi(sandbox, monkeypatch):
    tts_path, images_path, _ = sandbox
    images_metadata = json.loads(images_path.read_text(encoding="utf-8"))
    images_metadata["title"] = "Một Tập Khác"
    images_path.write_text(json.dumps(images_metadata, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(shorts_cli.ShortRenderError, match=TITLE):
        shorts_cli._run(tts_path, images_path)


def _fail_on_call(n_target: int, stderr: str):
    """Hai lệnh Remotion mỗi phần (render rồi still) -- lệnh thứ `n_target`
    tính trên toàn bộ các lượt gọi subprocess.run sẽ báo lỗi, các lệnh trước đó
    thành công và ghi file như thật."""
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == n_target:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=stderr)
        for suffix in (".mp4", ".jpg"):
            matches = [c for c in cmd if str(c).endswith(suffix)]
            if matches:
                Path(matches[0]).write_bytes(f"fake {suffix}".encode())
                break
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return _run


def test_remotion_loi_thi_bao_loi_neu_ro_so_phan(sandbox, monkeypatch):
    tts_path, images_path, _ = sandbox
    # Lệnh thứ 3 (render .mp4 của phần 2 -- phần 1 đã xong cả render lẫn still)
    # báo lỗi.
    monkeypatch.setattr(subprocess, "run", _fail_on_call(3, "remotion hỏng"))

    with pytest.raises(shorts_cli.ShortRenderError, match="phần 2") as exc_info:
        shorts_cli._run(tts_path, images_path)
    assert "remotion hỏng" in str(exc_info.value)


def test_remotion_bao_thanh_cong_nhung_khong_co_file_thi_bao_loi_ro_so_phan(
    sandbox, monkeypatch
):
    tts_path, images_path, _ = sandbox

    def _lie(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _lie)

    with pytest.raises(shorts_cli.ShortRenderError, match="phần 1") as exc_info:
        shorts_cli._run(tts_path, images_path)
    assert "không có file" in str(exc_info.value)


def test_loi_neu_thong_bao_ro_so_phan_da_hoan_tat_truoc_do(sandbox, monkeypatch):
    tts_path, images_path, _ = sandbox
    # Lệnh thứ 3 (render .mp4 của phần 2) báo lỗi -- phần 1 đã hoàn tất trọn
    # vẹn (render + still + in log) trước đó.
    monkeypatch.setattr(subprocess, "run", _fail_on_call(3, "remotion hỏng"))

    with pytest.raises(shorts_cli.ShortRenderError, match="1 phần trước đó"):
        shorts_cli._run(tts_path, images_path)


def test_phan_loi_bi_xoa_file_do_dang_con_phan_da_xong_thi_giu_nguyen(sandbox, monkeypatch):
    # Phần 1 render trót lọt cả mp4 lẫn ảnh bìa. Phần 2 lỗi giữa chừng ở bước
    # render mp4 nhưng kịp để lại wav đã cắt, props.json đã lưu, và (mô phỏng
    # Remotion crash giữa chừng) một mp4 dở dang -- cả ba phải bị dọn sạch, còn
    # 5 file của phần 1 (gồm cả ảnh bìa) phải nguyên vẹn.
    tts_path, images_path, output_dir = sandbox
    calls = {"n": 0}

    def _fail_third_leaves_partial_mp4(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] in (1, 2):
            for suffix in (".mp4", ".jpg"):
                matches = [c for c in cmd if str(c).endswith(suffix)]
                if matches:
                    Path(matches[0]).write_bytes(f"fake {suffix}".encode())
                    break
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        mp4 = [c for c in cmd if str(c).endswith(".mp4")][0]
        Path(mp4).write_bytes(b"mp4 do dang")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="remotion crash")

    monkeypatch.setattr(subprocess, "run", _fail_third_leaves_partial_mp4)

    with pytest.raises(shorts_cli.ShortRenderError):
        shorts_cli._run(tts_path, images_path)

    assert list(output_dir.glob("*-part-01.wav"))
    assert list(output_dir.glob("*-part-01.mp4"))
    assert list(output_dir.glob("*-part-01-props.json"))
    assert list(output_dir.glob("*-part-01.txt"))
    assert list(output_dir.glob("*-part-01.json"))
    assert list(output_dir.glob("*-part-01.jpg"))

    assert not list(output_dir.glob("*-part-02.wav"))
    assert not list(output_dir.glob("*-part-02.mp4"))
    assert not list(output_dir.glob("*-part-02-props.json"))
    assert not list(output_dir.glob("*-part-02.txt"))
    assert not list(output_dir.glob("*-part-02.json"))
    assert not list(output_dir.glob("*-part-02.jpg"))


def test_anh_bia_loi_thi_don_ca_mp4_lan_png_va_neu_so_phan_da_xong(sandbox, monkeypatch):
    # Phần 1 render mp4 trót lọt nhưng lỗi ngay ở bước render ảnh bìa -- mp4 đã
    # tạo ra của chính phần đó cũng phải bị dọn, không chỉ ảnh bìa dở dang.
    tts_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fail_on_call(2, "remotion still hỏng"))

    with pytest.raises(shorts_cli.ShortRenderError, match="phần 1") as exc_info:
        shorts_cli._run(tts_path, images_path)
    assert "remotion still hỏng" in str(exc_info.value)
    assert "0 phần trước đó" in str(exc_info.value)

    assert not list(output_dir.glob("*-part-01.mp4"))
    assert not list(output_dir.glob("*-part-01.jpg"))
    assert not list(output_dir.glob("*-part-01.wav"))
    assert not list(output_dir.glob("*-part-01-props.json"))
    assert not list(output_dir.glob("*-part-01.txt"))
    assert not list(output_dir.glob("*-part-01.json"))


def test_qua_99_phan_thi_bao_loi_ngay_khong_render_gi(sandbox, monkeypatch):
    # part_stem() vốn chỉ ném lỗi khi thật sự chạm tới phần ngoài khoảng, tức
    # là sau khi đã lỡ render một mớ phần trước đó. Kiểm tra số phần ngay từ
    # đầu để không phí công render rồi mới vỡ giữa chừng.
    tts_path, images_path, output_dir = sandbox
    monkeypatch.setattr(shorts_cli, "plan_teasers", lambda tts_metadata: [object()] * 100)

    render_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: render_calls.append(1))

    with pytest.raises(shorts_cli.ShortRenderError, match="100"):
        shorts_cli._run(tts_path, images_path)

    assert render_calls == []
    assert not output_dir.exists()


def test_thieu_file_wav_nguon_thi_bao_loi_ro_duong_dan(sandbox):
    tts_path, images_path, _ = sandbox
    source_wav = tts_path.with_suffix(".wav")
    source_wav.unlink()

    with pytest.raises(shorts_cli.ShortRenderError) as exc_info:
        shorts_cli._run(tts_path, images_path)
    assert str(source_wav) in str(exc_info.value)
