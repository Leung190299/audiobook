# tests/episodes/test_music.py
"""Nhạc nền nhẹ (09/11/2026, thử nghiệm): mặc định TẮT; bật bằng AUDIOBOOK_BGM;
mọi lỗi chỉ cảnh báo và dựng không nhạc như cũ."""
from pathlib import Path

import pytest

from episodes import music


@pytest.fixture
def kho(tmp_path, monkeypatch):
    d = tmp_path / "assets" / "music"
    d.mkdir(parents=True)
    (d / "a.mp3").write_bytes(b"x")
    (d / "b.mp3").write_bytes(b"x")
    (d / ".DS_Store").write_bytes(b"x")
    (d / "ghi-chu.txt").write_bytes(b"x")
    monkeypatch.delenv(music.ENV_FLAG, raising=False)
    monkeypatch.delenv(music.ENV_VOLUME, raising=False)
    return tmp_path, d


def test_mac_dinh_tat_khong_co_nhac(kho):
    root, d = kho
    assert music.choose(seed="s", directory=d, repo_root=root) is None


@pytest.mark.parametrize("flag", ["0", "off", "no", "false"])
def test_gia_tri_tat_ro_rang(kho, monkeypatch, flag):
    root, d = kho
    monkeypatch.setenv(music.ENV_FLAG, flag)
    assert music.choose(seed="s", directory=d, repo_root=root) is None


def test_bat_tu_dong_boc_theo_seed_va_bo_file_la(kho, monkeypatch, capsys):
    root, d = kho
    monkeypatch.setenv(music.ENV_FLAG, "1")

    p1 = music.choose(seed="tap-1", directory=d, repo_root=root)
    p2 = music.choose(seed="tap-1", directory=d, repo_root=root)

    assert p1 == p2  # cùng tập dựng lại -> cùng nhạc
    assert p1["backgroundMusic"] in ("assets/music/a.mp3", "assets/music/b.mp3")
    assert p1["backgroundMusicVolume"] == music.DEFAULT_VOLUME
    assert "Nhạc nền:" in capsys.readouterr().out


def test_bat_ma_thu_muc_trong_thi_canh_bao_va_khong_nhac(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(music.ENV_FLAG, "1")
    rong = tmp_path / "rong"
    rong.mkdir()

    assert music.choose(seed="s", directory=rong, repo_root=tmp_path) is None
    assert "CẢNH BÁO" in capsys.readouterr().out


def test_chi_dinh_file_tuong_doi_va_am_luong(kho, monkeypatch):
    root, d = kho
    monkeypatch.setenv(music.ENV_FLAG, "assets/music/b.mp3")
    monkeypatch.setenv(music.ENV_VOLUME, "0.3")

    assert music.choose(seed="s", directory=d, repo_root=root) == {
        "backgroundMusic": "assets/music/b.mp3",
        "backgroundMusicVolume": 0.3,
    }


def test_file_khong_ton_tai_hoac_ngoai_repo_thi_khong_nhac(kho, monkeypatch, tmp_path, capsys):
    root, d = kho
    monkeypatch.setenv(music.ENV_FLAG, "assets/music/khong-co.mp3")
    assert music.choose(seed="s", directory=d, repo_root=root) is None

    ngoai = tmp_path.parent / f"{tmp_path.name}-ngoai.mp3"
    ngoai.write_bytes(b"x")
    monkeypatch.setenv(music.ENV_FLAG, str(ngoai))
    assert music.choose(seed="s", directory=d, repo_root=root) is None
    assert capsys.readouterr().out.count("CẢNH BÁO") == 2


def test_am_luong_sai_hoac_vuot_khung_duoc_kep(monkeypatch, capsys):
    monkeypatch.setenv(music.ENV_VOLUME, "abc")
    assert music.volume() == music.DEFAULT_VOLUME
    assert "CẢNH BÁO" in capsys.readouterr().out
    monkeypatch.setenv(music.ENV_VOLUME, "7")
    assert music.volume() == 1.0
    monkeypatch.setenv(music.ENV_VOLUME, "0")
    assert music.volume() == 0.01
