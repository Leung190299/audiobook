# tests/shorts/test_audio_cut.py
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from shorts.audio_cut import AudioCutError, cut_wav

SAMPLE_RATE = 24000


def _write_source(tmp_path: Path, total_seconds: float) -> Path:
    source = tmp_path / "source.wav"
    t = np.arange(int(total_seconds * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    audio = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(source, audio, SAMPLE_RATE)
    return source


def test_cat_dung_so_mau_va_doc_lai_duoc(tmp_path: Path):
    source = _write_source(tmp_path, total_seconds=10.0)
    dest = tmp_path / "part.wav"

    written = cut_wav(source, start_seconds=2.0, end_seconds=3.0, dest=dest)

    data, sample_rate = sf.read(dest)
    assert sample_rate == SAMPLE_RATE
    assert len(data) == written
    assert written == pytest.approx(SAMPLE_RATE * 1.0, abs=1)


def test_chi_doc_dung_doan_can_khong_phai_ca_file_nguon(tmp_path: Path):
    # File nguồn dài 10s nhưng chỉ cắt 1s -- file ra phải dài ~1s, không phải 10s.
    # Đây là bằng chứng hành vi cho thấy hàm không nạp cả file vào rồi mới cắt.
    source = _write_source(tmp_path, total_seconds=10.0)
    dest = tmp_path / "part.wav"

    cut_wav(source, start_seconds=2.0, end_seconds=3.0, dest=dest)

    info = sf.info(dest)
    assert info.duration == pytest.approx(1.0, abs=0.01)


def test_goi_soundfile_read_voi_start_stop_dtype_float32(tmp_path: Path, monkeypatch):
    # Khẳng định trực tiếp lời gọi soundfile.read dùng start=/stop=/dtype="float32"
    # -- đúng cách duy nhất để không nạp cả file 50 phút vào bộ nhớ mỗi lần cắt.
    source = _write_source(tmp_path, total_seconds=10.0)
    dest = tmp_path / "part.wav"

    import shorts.audio_cut as audio_cut_module

    real_read = audio_cut_module.sf.read
    seen_kwargs = {}

    def _spy_read(*args, **kwargs):
        seen_kwargs.update(kwargs)
        return real_read(*args, **kwargs)

    monkeypatch.setattr(audio_cut_module.sf, "read", _spy_read)

    cut_wav(source, start_seconds=2.0, end_seconds=3.0, dest=dest)

    assert seen_kwargs["start"] == 2.0 * SAMPLE_RATE
    assert seen_kwargs["stop"] == 3.0 * SAMPLE_RATE
    assert seen_kwargs["dtype"] == "float32"


def test_sample_rate_doc_tu_file_nguon(tmp_path: Path):
    source = tmp_path / "source_48k.wav"
    t = np.arange(48000, dtype=np.float32) / 48000.0
    audio = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(source, audio, 48000)
    dest = tmp_path / "part.wav"

    cut_wav(source, start_seconds=0.0, end_seconds=0.5, dest=dest)

    info = sf.info(dest)
    assert info.samplerate == 48000


def test_khoang_cat_rong_thi_bao_loi(tmp_path: Path):
    source = _write_source(tmp_path, total_seconds=10.0)
    dest = tmp_path / "part.wav"

    with pytest.raises(AudioCutError, match="rỗng"):
        cut_wav(source, start_seconds=3.0, end_seconds=3.0, dest=dest)


def test_khoang_cat_dao_nguoc_thi_bao_loi(tmp_path: Path):
    source = _write_source(tmp_path, total_seconds=10.0)
    dest = tmp_path / "part.wav"

    with pytest.raises(AudioCutError, match="rỗng"):
        cut_wav(source, start_seconds=5.0, end_seconds=2.0, dest=dest)


def test_khoang_cat_vuot_qua_do_dai_file_thi_bao_loi(tmp_path: Path):
    source = _write_source(tmp_path, total_seconds=10.0)
    dest = tmp_path / "part.wav"

    with pytest.raises(AudioCutError, match="ngoài độ dài"):
        cut_wav(source, start_seconds=9.0, end_seconds=11.0, dest=dest)


def test_tu_tao_thu_muc_dich_neu_chua_co(tmp_path: Path):
    source = _write_source(tmp_path, total_seconds=5.0)
    dest = tmp_path / "chua" / "ton" / "tai" / "part.wav"

    cut_wav(source, start_seconds=0.0, end_seconds=1.0, dest=dest)

    assert dest.exists()
