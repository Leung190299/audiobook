"""Đăng short hằng đêm cho truyện vừa lên sóng (scripts/post_shorts.py)."""
import json
from datetime import date
from pathlib import Path

import pytest

from scripts import post_shorts as ps


def _state(tmp_path, data: dict):
    p = tmp_path / "story_bank_state.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# --- tìm truyện lên sóng hôm nay ---------------------------------------------


def test_tim_dung_truyen_len_song_hom_nay(tmp_path):
    p = _state(tmp_path, {
        "2": {"status": "published", "published_at": "2026-09-28T20:00:00+07:00"},
        "41": {"status": "published", "published_at": "2026-09-29T20:00:00+07:00"},
    })

    assert ps.truyen_len_song(date(2026, 9, 29), p) == 41


def test_khong_co_truyen_nao_hom_nay_thi_none(tmp_path):
    p = _state(tmp_path, {"2": {"published_at": "2026-09-28T20:00:00+07:00"}})

    assert ps.truyen_len_song(date(2026, 10, 7), p) is None


def test_gio_utc_van_quy_dung_ngay_theo_gio_kenh(tmp_path):
    """13:00Z = 20:00 giờ ta cùng ngày; quy nhầm múi giờ là lệch hẳn một ngày."""
    p = _state(tmp_path, {"9": {"published_at": "2026-09-29T13:00:00+00:00"}})

    assert ps.truyen_len_song(date(2026, 9, 29), p) == 9


def test_state_thieu_hoac_hong_thi_khong_vo(tmp_path):
    assert ps.truyen_len_song(date(2026, 9, 29), tmp_path / "chua-co.json") is None
    hong = tmp_path / "h.json"
    hong.write_text("{ hỏng", encoding="utf-8")
    assert ps.truyen_len_song(date(2026, 9, 29), hong) is None


def test_ban_ghi_thieu_published_at_thi_bo_qua(tmp_path):
    p = _state(tmp_path, {"2": {"status": "used"},
                          "3": {"published_at": "2026-09-29T20:00:00+07:00"}})

    assert ps.truyen_len_song(date(2026, 9, 29), p) == 3


# --- tìm chỉ mục và tiền tố --------------------------------------------------


def _index(dir_: Path, name: str, **fields) -> Path:
    p = dir_ / name
    p.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
    return p


def test_chi_muc_tim_theo_story_id(tmp_path):
    _index(tmp_path, "a-full.json", story_id=5)
    mong = _index(tmp_path, "b-full.json", story_id=41)

    assert ps.chi_muc_cua_truyen(41, tmp_path) == mong


def test_nhieu_ban_dung_thi_lay_ban_moi_nhat(tmp_path):
    import os
    import time

    cu = _index(tmp_path, "cu-full.json", story_id=41)
    time.sleep(0.01)
    moi = _index(tmp_path, "moi-full.json", story_id=41)
    os.utime(cu, (1, 1))

    assert ps.chi_muc_cua_truyen(41, tmp_path) == moi


def test_khong_co_chi_muc_khop_thi_none(tmp_path):
    _index(tmp_path, "a-full.json", story_id=5)

    assert ps.chi_muc_cua_truyen(41, tmp_path) is None


def test_file_hong_khong_lam_vo_viec_tim(tmp_path):
    (tmp_path / "hong-full.json").write_text("{ hỏng", encoding="utf-8")
    mong = _index(tmp_path, "ok-full.json", story_id=41)

    assert ps.chi_muc_cua_truyen(41, tmp_path) == mong


def test_doc_va_ghi_shorts_prefix(tmp_path):
    index = _index(tmp_path, "x-full.json", story_id=41, story_title="T")

    assert ps.prefix_cua_chi_muc(index) is None

    ps.ghi_shorts_prefix(index, "output/shorts/abc-20260925T034102Z")

    # Ghi xong không được làm mất trường cũ.
    data = json.loads(index.read_text(encoding="utf-8"))
    assert data["story_id"] == 41 and data["story_title"] == "T"
    assert ps.prefix_cua_chi_muc(index) == ps.ROOT / "output/shorts/abc-20260925T034102Z"


def test_duong_dan_tuyet_doi_giu_nguyen(tmp_path):
    index = _index(tmp_path, "x-full.json", shorts_prefix="/tmp/abc-123")

    assert str(ps.prefix_cua_chi_muc(index)) == "/tmp/abc-123"


# --- main: không có gì thì không làm gì --------------------------------------


def test_ngay_khong_co_truyen_thi_thoat_em(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ps, "DEFAULT_STATE_PATH", tmp_path / "trong.json")
    monkeypatch.setattr(
        ps, "truyen_len_song", lambda ngay, state_path=None: None
    )

    assert ps.main(["--date", "2026-10-07"]) == 0
    assert "không có truyện nào lên sóng" in capsys.readouterr().out


def test_chi_muc_chua_ghi_prefix_thi_bao_ro_chu_khong_doan(tmp_path, monkeypatch, capsys):
    """Dò tiền tố theo giờ là rủi ro đăng nhầm short truyện khác -- thà dừng."""
    _index(tmp_path, "x-full.json", story_id=41, story_title="T")
    monkeypatch.setattr(ps, "METADATA_DIR", tmp_path)
    monkeypatch.setattr(ps, "truyen_len_song", lambda ngay, state_path=None: 41)

    assert ps.main(["--date", "2026-09-29"]) == 4
    assert "chưa ghi shorts_prefix" in capsys.readouterr().err
