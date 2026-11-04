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


def test_duong_dan_cache_mang_chieu_cao(tmp_path):
    """Khoá cache khác bản đệm mờ cũ (abc-1024x576.mp4), để bản cũ không bị
    dùng nhầm sau khi đổi sang bố cục tấm thương hiệu."""
    src = _mp4(tmp_path, "abc.mp4")

    out = bg.prepared_path(src, 576)

    assert out.parent.name == bg.CACHE_DIRNAME
    assert out.name == "abc-h576.mp4"


def test_cache_cu_hon_nguon_thi_phai_lam_lai(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")
    out = bg.prepared_path(src, 576)
    out.parent.mkdir(parents=True)
    out.write_bytes(b"cu")
    os.utime(out, (1, 1))

    assert bg.needs_prepare(src, out) is True


def test_cache_moi_hon_nguon_thi_dung_lai(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")
    os.utime(src, (1, 1))
    out = bg.prepared_path(src, 576)
    out.parent.mkdir(parents=True)
    out.write_bytes(b"moi")

    assert bg.needs_prepare(src, out) is False


def test_chua_co_cache_thi_phai_lam(tmp_path):
    src = _mp4(tmp_path, "abc.mp4")

    assert bg.needs_prepare(src, bg.prepared_path(src, 576)) is True


# --- lệnh ffmpeg -------------------------------------------------------------


def test_lenh_ffmpeg_bo_tieng_goc_giu_kho_dua_ve_chieu_cao(tmp_path):
    """Video Douyin có nhạc nền riêng: lọt vào là đè lên giọng đọc. Giữ nguyên
    khổ (không đệm mờ, không cắt): ô giữa của Remotion co giãn theo khổ, hai
    bên là tấm thương hiệu."""
    cmd = bg.ffmpeg_command(Path("in.mp4"), Path("out.mp4"), 576, 30)

    assert "-an" in cmd
    vf = cmd[cmd.index("-vf") + 1]
    # -2: bề rộng tự tính theo khổ VÀ làm tròn về số chẵn (libx264 đòi chẵn;
    # 576x1036 thu về 320,2px là lẻ).
    assert "scale=-2:576" in vf
    assert "fps=30" in vf
    assert "boxblur" not in vf


# --- chọn cho một tập --------------------------------------------------------


def test_choose_khong_co_video_thi_none_de_dung_anh_nhu_cu(tmp_path):
    assert bg.choose(tmp_path, "x", prepare=lambda *a, **k: pytest.fail("không được gọi")) is None


def test_choose_tra_duong_dan_tuong_doi_repo_va_thoi_luong(tmp_path):
    repo = tmp_path
    nen = repo / "assets" / "backgrounds"
    nen.mkdir(parents=True)
    _mp4(nen, "a.mp4")

    def fake_prepare(src, height, fps):
        out = bg.prepared_path(src, height)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"ok")
        return out, 312.6, 324 / 576

    ra = bg.choose(nen, "tap-1", repo_root=repo, prepare=fake_prepare)

    assert ra == {
        # Chiều cao khung video dài (1080p từ 05/10) nằm trong tên cache.
        "backgroundVideo": f"assets/backgrounds/.prepared/a-h{bg.HEIGHT}.mp4",
        "backgroundVideoSeconds": 312.6,
        # Remotion dùng tỉ lệ này để tính bề rộng ô giữa.
        "backgroundVideoAspect": 0.5625,
    }


def test_choose_chuan_bi_hong_thi_none_khong_lam_vo_luot_dung(tmp_path):
    """Một video nền hỏng không đáng làm mất cả lượt dựng 1 tiếng: rơi về ảnh."""
    _mp4(tmp_path, "a.mp4")

    def hong(*a, **k):
        raise bg.BackgroundError("ffmpeg chết")

    assert bg.choose(tmp_path, "x", repo_root=tmp_path, prepare=hong) is None


# --- video nền cho short (05/10/2026) ----------------------------------------


def _fake_prepare(src, height, fps):
    out = bg.prepared_path(src, height)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"ok")
    return out, 300.0, 0.5625


def test_short_uu_tien_video_doc(tmp_path):
    """Short khổ 1080x1920: video dọc vừa khít, video ngang ép vào thì chỉ còn
    dải giữa ~32% bề ngang."""
    for name in ("ngang.mp4", "doc.mp4"):
        _mp4(tmp_path, name)
    khuon = {"ngang.mp4": 1.778, "doc.mp4": 0.5625}

    for seed in ("a", "b", "c", "d", "e"):
        ra = bg.choose_for_short(
            tmp_path, seed, repo_root=tmp_path, prepare=_fake_prepare,
            aspect_of=lambda p: khuon[p.name],
        )
        assert "doc-h1920" in ra["backgroundVideo"]


def test_short_khong_co_video_doc_thi_dung_video_ngang(tmp_path):
    _mp4(tmp_path, "ngang.mp4")

    ra = bg.choose_for_short(
        tmp_path, "x", repo_root=tmp_path, prepare=_fake_prepare, aspect_of=lambda p: 1.778,
    )

    assert "ngang-h1920" in ra["backgroundVideo"]


def test_short_chuan_bi_o_do_cao_khung_short(tmp_path):
    """Bản 576px của video dài mà phóng 3,3 lần lên 1920px thì nhoè."""
    _mp4(tmp_path, "doc.mp4")
    goi = {}

    def prep(src, height, fps):
        goi["height"] = height
        return _fake_prepare(src, height, fps)

    bg.choose_for_short(tmp_path, "x", repo_root=tmp_path, prepare=prep, aspect_of=lambda p: 0.56)

    assert goi["height"] == bg.SHORT_HEIGHT == 1920


def test_short_thu_muc_trong_thi_none(tmp_path):
    assert bg.choose_for_short(tmp_path, "x", repo_root=tmp_path, prepare=_fake_prepare) is None
