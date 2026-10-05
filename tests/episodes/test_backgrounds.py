"""Video nền thay ảnh tĩnh cho video dài (episodes/backgrounds.py)."""
import os
from pathlib import Path

import pytest

from episodes import backgrounds as bg


def _mp4(dir_: Path, name: str) -> Path:
    p = dir_ / name
    p.write_bytes(b"mp4")
    return p


# --- liệt kê nguồn -----------------------------------------------------------


def test_liet_ke_chi_lay_mp4_va_bo_qua_thu_muc_cache(tmp_path):
    _mp4(tmp_path, "b.mp4")
    _mp4(tmp_path, "a.MP4")
    (tmp_path / "ghi-chu.txt").write_text("x")
    cache = tmp_path / bg.CACHE_DIRNAME
    cache.mkdir()
    _mp4(cache, "a-1024x576.mp4")

    assert [p.name for p in bg.list_sources(tmp_path)] == ["a.MP4", "b.mp4"]


def test_thu_muc_khong_ton_tai_thi_rong(tmp_path):
    assert bg.list_sources(tmp_path / "chua-co") == []


def test_bo_qua_file_an_cua_macos(tmp_path):
    """Finder rải file '._ten.mp4' khi chép từ ổ ngoài; ffmpeg đọc là lỗi."""
    _mp4(tmp_path, "._a.mp4")
    _mp4(tmp_path, "a.mp4")

    assert [p.name for p in bg.list_sources(tmp_path)] == ["a.mp4"]


# --- chọn ngẫu nhiên ---------------------------------------------------------


def test_chon_cung_seed_thi_cung_video(tmp_path):
    """Cùng tập dựng lại phải ra cùng nền, không thì đổi nền giữa chừng."""
    nguon = [_mp4(tmp_path, f"{c}.mp4") for c in "abcd"]

    assert bg.pick(nguon, "truyen-x-full") == bg.pick(nguon, "truyen-x-full")


def test_seed_khac_nhau_thi_rai_deu_nhieu_video(tmp_path):
    """Mỗi tập một nền ngẫu nhiên: 40 tập phải chạm đủ cả 4 video."""
    nguon = [_mp4(tmp_path, f"{c}.mp4") for c in "abcd"]

    da_chon = {bg.pick(nguon, f"tap-{i}").name for i in range(40)}

    assert da_chon == {"a.mp4", "b.mp4", "c.mp4", "d.mp4"}


def test_them_video_moi_thi_duoc_chon(tmp_path):
    """Người dùng sẽ bổ sung video dần vào thư mục: phải tự nhận, không sửa code."""
    nguon = [_mp4(tmp_path, f"{c}.mp4") for c in "ab"]
    nguon.append(_mp4(tmp_path, "moi.mp4"))

    assert "moi.mp4" in {bg.pick(nguon, f"tap-{i}").name for i in range(60)}


def test_khong_co_nguon_thi_none():
    assert bg.pick([], "x") is None


# --- cache bản đã chuẩn bị ---------------------------------------------------


def test_duong_dan_cache_mang_kich_thuoc(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")

    out = bg.prepared_path(src, 1024, 576)

    assert out.parent.name == bg.CACHE_DIRNAME
    assert out.name == "abc-1024x576.mp4"


def test_cache_cu_hon_nguon_thi_phai_lam_lai(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")
    out = bg.prepared_path(src, 1024, 576)
    out.parent.mkdir(parents=True)
    out.write_bytes(b"cu")
    os.utime(out, (1, 1))

    assert bg.needs_prepare(src, out) is True


def test_cache_moi_hon_nguon_thi_dung_lai(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")
    os.utime(src, (1, 1))
    out = bg.prepared_path(src, 1024, 576)
    out.parent.mkdir(parents=True)
    out.write_bytes(b"moi")

    assert bg.needs_prepare(src, out) is False


def test_chua_co_cache_thi_phai_lam(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")

    assert bg.needs_prepare(src, bg.prepared_path(src, 1024, 576)) is True


# --- lệnh ffmpeg -------------------------------------------------------------


def test_lenh_ffmpeg_bo_tieng_goc_va_dem_mo_hai_ben(tmp_path):
    """Video Douyin có nhạc nền riêng: lọt vào là đè lên giọng đọc."""
    cmd = bg.ffmpeg_command(Path("in.mp4"), Path("out.mp4"), 1024, 576, 30)

    assert "-an" in cmd
    filtre = cmd[cmd.index("-filter_complex") + 1]
    # Lớp nền phủ kín rồi làm mờ, lớp trước giữ nguyên tỉ lệ đặt giữa.
    assert "force_original_aspect_ratio=increase" in filtre
    assert "boxblur" in filtre
    assert "force_original_aspect_ratio=decrease" in filtre
    # libx264 đòi kích thước chẵn; 576x1036 thu về 320,2px là lẻ.
    assert "force_divisible_by=2" in filtre
    assert "overlay=(W-w)/2:(H-h)/2" in filtre
    assert "fps=30" in filtre


# --- chọn cho một tập --------------------------------------------------------


def test_choose_khong_co_video_thi_none_de_dung_anh_nhu_cu(tmp_path):
    assert bg.choose(tmp_path, "x", prepare=lambda *a, **k: pytest.fail("không được gọi")) is None


def test_choose_tra_duong_dan_tuong_doi_repo_va_thoi_luong(tmp_path):
    repo = tmp_path
    nen = repo / "assets" / "backgrounds"
    nen.mkdir(parents=True)
    _mp4(nen, "a.mp4")

    def fake_prepare(src, width, height, fps):
        out = bg.prepared_path(src, width, height)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"ok")
        return out, 312.6

    ra = bg.choose(nen, "tap-1", repo_root=repo, prepare=fake_prepare)

    assert ra == {
        "backgroundVideo": "assets/backgrounds/.prepared/a-1024x576.mp4",
        "backgroundVideoSeconds": 312.6,
    }


def test_choose_chuan_bi_hong_thi_none_khong_lam_vo_luot_dung(tmp_path):
    """Một video nền hỏng không đáng làm mất cả lượt dựng 1 tiếng: rơi về ảnh."""
    _mp4(tmp_path, "a.mp4")

    def hong(*a, **k):
        raise bg.BackgroundError("ffmpeg chết")

    assert bg.choose(tmp_path, "x", repo_root=tmp_path, prepare=hong) is None
