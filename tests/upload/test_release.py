# tests/upload/test_release.py
"""Kho video riêng tư và lịch nhả 7 ngày (05/11/2026). Không gọi API."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from scripts import story_bank
from upload import release
from upload.episodes_cli import LOCAL_TZ
from upload.release import Video, attach_status, load_index, pick_stock, plan, rewrite_publish_at

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=LOCAL_TZ)
TODAY = NOW.date()


def _v(vid: str, topic: str, air: date | None = None, privacy: str | None = None, story_id: int = 0) -> Video:
    publish_at = datetime.combine(air, datetime.min.time().replace(hour=20), tzinfo=LOCAL_TZ) if air else None
    row = {"video_id": vid, "topic": topic, "story_title": f"Truyện {vid}", "url": f"https://youtu.be/{vid}",
           "story_id": story_id}
    return Video(row=row, privacy=privacy or ("private" if air is None or air >= TODAY else "public"),
                 publish_at=publish_at)


def _scheduled(days: int, topic: str = "ho_hang_viet") -> list[Video]:
    """Tối nay và `days - 1` tối tiếp theo đều đã có video."""
    return [_v(f"s{d}", topic, TODAY + timedelta(days=d)) for d in range(days)]


# --- kế hoạch -----------------------------------------------------------------


def test_bo_hen_video_hen_qua_7_ngay_va_hen_1_video_cho_toi_trong_gan_nhat():
    videos = _scheduled(7) + [
        _v("xa1", "nghe_la_hong_bien", TODAY + timedelta(days=8)),
        _v("xa2", "bo_me_trong_sinh", TODAY + timedelta(days=20)),
        _v("kho1", "bo_me_trong_sinh"),
    ]
    p = plan(videos, NOW)
    assert [v.video_id for v in p.unschedule] == ["xa1", "xa2"]
    assert p.hole == TODAY + timedelta(days=7)
    assert p.chosen.video_id == "kho1"
    assert p.stock_left == 2  # xa1, xa2 về kho


def test_lich_7_ngay_kin_thi_khong_hen_gi():
    p = plan(_scheduled(8) + [_v("kho1", "ho_hang_viet")], NOW)
    assert p.hole is None and p.chosen is None and not p.stock_empty
    assert p.stock_left == 1


def test_kho_trong_ma_con_toi_trong_thi_bao_de_dung_truyen_moi():
    p = plan(_scheduled(3), NOW)
    assert p.hole == TODAY + timedelta(days=3)
    assert p.chosen is None and p.stock_empty


def test_sau_19h30_thi_toi_nay_khong_con_la_toi_trong():
    late = NOW.replace(hour=19, minute=45)
    p = plan([_v("kho1", "ho_hang_viet")], late)
    assert p.hole == TODAY + timedelta(days=1)


def test_video_cong_khai_da_chieu_khong_bi_bo_hen_va_khong_vao_kho():
    old = _v("cu", "ho_hang_viet", TODAY - timedelta(days=30), privacy="public")
    p = plan([old], NOW)
    assert p.unschedule == [] and p.chosen is None and p.stock_empty


def test_video_hen_xa_vua_bo_hen_cung_duoc_lay_khi_kho_san_trong():
    videos = _scheduled(7) + [_v("xa", "ho_hang_viet", TODAY + timedelta(days=15))]
    p = plan(videos, NOW)
    assert p.chosen.video_id == "xa" and p.chosen.is_stock
    assert p.stock_left == 0


def test_video_upload_hong_khong_tinh_la_kho():
    bad = Video(row={"video_id": "h", "topic": "ho_hang_viet"}, privacy="private", publish_at=None, upload_status="failed")
    assert not bad.is_stock
    assert plan([bad], NOW).chosen is None


# --- chọn từ kho ----------------------------------------------------------------


def test_uu_tien_chu_de_thang_va_xen_ke_hai_chu_de():
    videos = [
        _v("a1", "ho_hang_viet", TODAY + timedelta(days=1)),       # họ hàng vừa lên gần nhất
        _v("b0", "bo_me_trong_sinh", TODAY - timedelta(days=3), privacy="public"),
        _v("n1", "nghe_la_hong_bien"), _v("h1", "ho_hang_viet"), _v("b1", "bo_me_trong_sinh"),
        _v("d1", "hoc_duong"),
    ]
    assert pick_stock(videos).video_id == "b1"  # bố mẹ trọng sinh lên sóng xa hơn -> tới lượt
    videos.append(_v("b1x", "bo_me_trong_sinh", TODAY + timedelta(days=2)))
    assert pick_stock(videos).video_id == "h1"


def test_het_chu_de_thang_thi_toi_hoc_duong_roi_nghe_la():
    videos = [_v("n1", "nghe_la_hong_bien"), _v("d1", "hoc_duong"), _v("n0", "nghe_la_hong_bien")]
    assert pick_stock(videos).video_id == "d1"
    assert pick_stock([_v("n1", "nghe_la_hong_bien"), _v("n0", "nghe_la_hong_bien")]).video_id == "n1"


def test_cung_chu_de_thi_vao_kho_truoc_di_truoc():
    assert pick_stock([_v("h1", "ho_hang_viet"), _v("h2", "ho_hang_viet")]).video_id == "h1"


def test_kho_trong_tra_none():
    assert pick_stock(_scheduled(2)) is None


# --- ghép status API -------------------------------------------------------------


def test_attach_status_doc_publish_at_utc_ra_gio_viet_nam():
    rows = [{"video_id": "a"}, {"video_id": "mat"}]
    st = {"a": {"privacyStatus": "private", "publishAt": "2026-11-12T13:00:00Z", "uploadStatus": "processed"}}
    (v,) = attach_status(rows, st)
    assert v.publish_at == datetime(2026, 11, 12, 20, 0, tzinfo=LOCAL_TZ)
    assert v.air_date == date(2026, 11, 12) and not v.is_stock


def test_load_index_bo_dong_hong_va_giu_dong_sau_khi_trung_id(tmp_path):
    p = tmp_path / "index.jsonl"
    p.write_text('{"video_id":"a","topic":"x"}\nhỏng\n{"video_id":"a","topic":"y"}\n{"video_id":"b","format":"episodes"}\n')
    rows = load_index(p)
    assert [(r["video_id"], r["topic"]) for r in rows] == [("a", "y")]


def test_rewrite_publish_at_chi_sua_dung_dong(tmp_path):
    p = tmp_path / "index.jsonl"
    p.write_text('{"video_id":"a","publishAt":"2026-12-01T20:00:00+07:00"}\n{"video_id":"b","publishAt":null}\n')
    rewrite_publish_at(p, "a", None)
    rewrite_publish_at(p, "b", datetime(2026, 11, 12, 20, tzinfo=LOCAL_TZ))
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    assert rows[0]["publishAt"] is None
    assert rows[1]["publishAt"] == "2026-11-12T20:00:00+07:00"


# --- thực hiện -------------------------------------------------------------------


def _story_files(tmp_path: Path, vid: str, shorts: list[str]) -> dict:
    """Chỉ mục metadata + state short đã đăng, như stage 6/8 để lại trên đĩa."""
    prefix = tmp_path / "shorts" / f"{vid}-20261101T000000Z"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    (prefix.parent / f"{prefix.name}-upload-state.json").write_text(json.dumps(
        {"uploaded": {str(n): {"video_id": s} for n, s in enumerate(shorts, 1)}}))
    index = tmp_path / "metadata" / f"{vid}-full.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({"shorts_prefix": str(prefix)}))
    return {"video_id": vid, "topic": "ho_hang_viet", "story_title": f"Truyện {vid}", "index": str(index),
            "story_id": 7, "url": f"https://youtu.be/{vid}"}


def test_apply_hen_video_va_2_short_dau_giu_short_3(tmp_path, capsys):
    row = _story_files(tmp_path, "k1", ["s1", "s2", "s3"])
    index_jsonl = tmp_path / "index.jsonl"
    index_jsonl.write_text(json.dumps({**row, "publishAt": None}) + "\n")
    state = tmp_path / "state.json"
    calls = []

    def updater(credentials, video_id, publish_at):
        calls.append((video_id, publish_at))
        return True

    p = plan([Video(row=row, privacy="private", publish_at=None)], NOW)
    release.apply(None, p, updater=updater, index_jsonl=index_jsonl, state_path=state)

    at = datetime(2026, 11, 5, 20, 0, tzinfo=LOCAL_TZ)
    assert calls == [("k1", at), ("s1", at + timedelta(minutes=5)), ("s2", at + timedelta(minutes=5))]
    assert json.loads(index_jsonl.read_text())["publishAt"] == at.isoformat()
    assert story_bank.load_state(state)["7"] == {"status": "published", "published_at": at.isoformat()}
    out = capsys.readouterr().out
    assert "Đã hẹn: Truyện k1 — https://youtu.be/k1 (lên sóng 2026-11-05 20:00, giữ lại 1 short)" in out


def test_apply_bo_hen_ca_video_lan_short_va_xoa_gio_local(tmp_path, capsys):
    row = _story_files(tmp_path, "xa", ["s1", "s2", "s3"])
    index_jsonl = tmp_path / "index.jsonl"
    index_jsonl.write_text(json.dumps({**row, "publishAt": "2026-12-01T20:00:00+07:00"}) + "\n")
    state = tmp_path / "state.json"
    story_bank.set_air_time(7, "2026-12-01T20:00:00+07:00", state_path=state)
    calls = []
    far = Video(row=row, privacy="private", publish_at=datetime(2026, 12, 1, 20, tzinfo=LOCAL_TZ))

    p = plan(_scheduled(8) + [far], NOW)
    release.apply(None, p, updater=lambda c, vid, at: calls.append((vid, at)) or True,
                  index_jsonl=index_jsonl, state_path=state)

    assert calls == [("xa", None), ("s1", None), ("s2", None), ("s3", None)]
    assert json.loads(index_jsonl.read_text())["publishAt"] is None
    assert "published_at" not in story_bank.load_state(state)["7"]
    assert "Bỏ hẹn (về kho): Truyện xa" in capsys.readouterr().out


def test_apply_hen_hong_thi_bao_loi_va_khong_ghi_local(tmp_path):
    row = _story_files(tmp_path, "k1", [])
    index_jsonl = tmp_path / "index.jsonl"
    index_jsonl.write_text(json.dumps({**row, "publishAt": None}) + "\n")
    p = plan([Video(row=row, privacy="private", publish_at=None)], NOW)
    with pytest.raises(release.ReleaseError, match="Không hẹn được"):
        release.apply(None, p, updater=lambda *a: False, index_jsonl=index_jsonl, state_path=tmp_path / "s.json")
    assert json.loads(index_jsonl.read_text())["publishAt"] is None


def test_main_ma_thoat_3_khi_kho_trong_de_run_daily_dung(monkeypatch, capsys):
    monkeypatch.setattr(release, "load_index", lambda: [{"video_id": "a", "topic": "x"}])
    monkeypatch.setattr(release, "load_credentials", lambda: object())
    monkeypatch.setattr(release, "list_status", lambda c, ids: {"a": {"privacyStatus": "public"}})
    assert release.main(["--dry-run"]) == 3
    assert "KHO TRỐNG" in capsys.readouterr().out


def test_main_ma_thoat_0_khi_da_hen(monkeypatch, capsys):
    monkeypatch.setattr(release, "load_index", lambda: [{"video_id": "a", "topic": "ho_hang_viet", "story_title": "A"}])
    monkeypatch.setattr(release, "load_credentials", lambda: object())
    monkeypatch.setattr(release, "list_status", lambda c, ids: {"a": {"privacyStatus": "private"}})
    monkeypatch.setattr(release, "update_status", lambda c, vid, at: True)
    monkeypatch.setattr(release, "rewrite_publish_at", lambda *a: None)
    assert release.main([]) == 0
    assert "Đã hẹn: A" in capsys.readouterr().out
