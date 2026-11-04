"""Lịch đăng short ba tối 30/09-02/10 (scripts/catchup_shorts.py)."""
import json
from unittest.mock import MagicMock

import pytest

from scripts import catchup_shorts as cs


def _video(vid: str, privacy: str, title: str, publish_at: str | None = None) -> dict:
    status = {"privacyStatus": privacy}
    if publish_at:
        status["publishAt"] = publish_at
    return {"id": vid, "status": status,
            "snippet": {"title": title, "description": "mô tả", "tags": ["a"],
                        "categoryId": "24"}}


def _yt(videos: list[dict]):
    """Giả googleapiclient: nhớ lại mọi lượt update để test soi."""
    yt = MagicMock()
    yt.videos.return_value.list.return_value.execute.return_value = {"items": videos}
    yt.updates = []

    def _update(part, body):
        yt.updates.append((part, body))
        return MagicMock(execute=MagicMock(return_value={}))

    yt.videos.return_value.update.side_effect = _update
    return yt


# --- đọc state ---------------------------------------------------------------


def test_ids_short_da_dang_doc_dung_thu_tu(tmp_path):
    prefix = tmp_path / "abc-20260926T024901Z"
    (tmp_path / "abc-20260926T024901Z-upload-state.json").write_text(json.dumps({
        "uploaded": {"3": {"video_id": "c"}, "1": {"video_id": "a"}, "2": {"video_id": "b"}}
    }), encoding="utf-8")

    assert cs.ids_short_da_dang(prefix) == ["a", "b", "c"]


def test_chua_dang_thi_rong(tmp_path):
    assert cs.ids_short_da_dang(tmp_path / "chua-co") == []


def test_state_hong_khong_lam_vo_ca_luot(tmp_path):
    prefix = tmp_path / "x"
    (tmp_path / "x-upload-state.json").write_text("{ hỏng", encoding="utf-8")

    assert cs.ids_short_da_dang(prefix) == []


def test_id_video_dai_lay_tu_state_cua_chi_muc(tmp_path):
    index = tmp_path / "abc-full.json"
    (tmp_path / "abc-full-upload-state.json").write_text(json.dumps({
        "uploaded": {"1": {"video_id": "DAI1"}}
    }), encoding="utf-8")

    assert cs.id_video_dai(index) == "DAI1"


# --- chặn đăng sớm -----------------------------------------------------------


def test_video_dai_con_private_thi_dung_lai():
    """Sự cố 30/09: chạy --date 2026-10-02 sớm ba ngày, short công khai trỏ
    vào video còn private -> link chết hai ngày rưỡi."""
    yt = _yt([_video("DAI1", "private", "T", publish_at="2026-10-02T13:00:00Z")])

    with pytest.raises(cs.ShortsError) as exc:
        cs.kiem_video_dai_cong_khai(yt, "DAI1")

    assert "private" in str(exc.value)
    assert "2026-10-02T13:00:00Z" in str(exc.value)
    assert yt.updates == []


def test_video_dai_da_cong_khai_thi_cho_qua():
    yt = _yt([_video("DAI1", "public", "T")])

    cs.kiem_video_dai_cong_khai(yt, "DAI1")  # không ném


def test_khong_doc_duoc_video_dai_thi_bao_loi():
    yt = _yt([])

    with pytest.raises(cs.ShortsError):
        cs.kiem_video_dai_cong_khai(yt, "DAI1")


# --- chuẩn hoá short ---------------------------------------------------------


def test_short_private_thi_bat_cong_khai_va_doi_tieu_de():
    yt = _yt([
        _video("s1", "private", "Câu cụt một… #Shorts"),
        _video("s2", "private", "Câu cụt hai… #Shorts"),
    ])

    cs.chuan_hoa_short(yt, "Bà Nội 80 Tuổi", ["s1", "s2"])

    assert len(yt.updates) == 2
    part, body = yt.updates[0]
    assert "status" in part and "snippet" in part
    assert body["status"]["privacyStatus"] == "public"
    assert body["snippet"]["title"] == "Bà Nội 80 Tuổi — Trích đoạn 1/2"
    # Mô tả chứa link sang video dài: không được mất khi đổi tiêu đề.
    assert body["snippet"]["description"] == "mô tả"
    assert body["snippet"]["tags"] == ["a"]


def test_da_dung_roi_thi_khong_goi_update():
    yt = _yt([_video("s1", "public", "Truyện X — Trích đoạn 1/1")])

    cs.chuan_hoa_short(yt, "Truyện X", ["s1"])

    assert yt.updates == []


def test_chi_thieu_cong_khai_thi_khong_dung_toi_snippet():
    yt = _yt([_video("s1", "private", "Truyện X — Trích đoạn 1/1")])

    cs.chuan_hoa_short(yt, "Truyện X", ["s1"])

    part, body = yt.updates[0]
    assert part == "status" and "snippet" not in body


def test_short_bien_mat_thi_bo_qua_chu_khong_vo(capsys):
    yt = _yt([_video("s1", "private", "x")])

    cs.chuan_hoa_short(yt, "Truyện X", ["s1", "mat-tieu"])

    assert "mat-tieu" in capsys.readouterr().out
    assert len(yt.updates) == 1


# --- bảng lịch ---------------------------------------------------------------


def test_ngay_ngoai_lich_thi_khong_lam_gi(capsys):
    assert cs.main(["--date", "2026-10-09"]) == 0
    assert "không có truyện nào trong lịch" in capsys.readouterr().out


def test_ba_ngay_trong_lich_khong_dung_chung_tien_to_short():
    prefixes = [v[1] for v in cs.LICH.values()]
    assert len(set(prefixes)) == 3, "hai ngày trỏ cùng bộ short là đăng nhầm truyện"
    indexes = [v[0] for v in cs.LICH.values()]
    assert len(set(indexes)) == 3


def test_doc_id_short_ca_khi_dong_co_gio_cong_khai_phia_sau():
    out = (
        "Phần 1: Truyện X — Trích đoạn 1/3 — https://youtu.be/AbC-1_x (công khai 07/10 20:05)\n"
        "Phần 2: Truyện X — Trích đoạn 2/3 — https://youtu.be/DeF2\n"
    )

    assert cs.DONG_SHORT.findall(out) == [("1", "AbC-1_x"), ("2", "DeF2")]
