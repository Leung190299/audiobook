import json
from datetime import date, datetime

from director import state
from director.paths import VN
from director.state import channel_weekdays, next_free_evening, refresh, taken_evenings


class FakeYouTube:
    def __init__(self, statuses):
        self.statuses = statuses

    def videos(self):
        return self

    def list(self, part, id):
        self._ids = id.split(",")
        return self

    def execute(self):
        return {"items": [{"id": i, "status": self.statuses[i]} for i in self._ids if i in self.statuses]}


def test_channel_weekdays_mac_dinh_tung_kenh():
    assert channel_weekdays("main", {}) == {2, 6}
    assert channel_weekdays("xomque", {}) == {0, 3, 5}
    assert channel_weekdays("main", {"AUDIOBOOK_RELEASE_WEEKDAYS": "0,2,4,6"}) == {0, 2, 4, 6}


def test_channel_weekdays_sai_thi_mac_dinh_va_canh_bao():
    w = []
    assert channel_weekdays("xomque", {"AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE": "a,9"}, warnings=w) == {0, 3, 5}
    assert w and "AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE" in w[0]


def test_taken_evenings_chi_video_rieng_tu_co_hen():
    st = {"a": {"privacyStatus": "private", "publishAt": "2026-11-29T13:00:00Z"},
          "b": {"privacyStatus": "public"},
          "c": {"privacyStatus": "private"}}
    assert taken_evenings(st) == {date(2026, 11, 29)}


def test_next_free_evening_bo_qua_toi_da_chiem():
    now = datetime(2026, 11, 28, 8, 0, tzinfo=VN)  # thứ Bảy
    assert next_free_evening("xomque", {date(2026, 11, 28)}, now, {0, 3, 5}) == datetime(2026, 11, 30, 20, 0, tzinfo=VN)


def test_next_free_evening_truoc_18h_lay_hom_nay():
    now = datetime(2026, 11, 28, 8, 0, tzinfo=VN)
    assert next_free_evening("xomque", set(), now, {5}) == datetime(2026, 11, 28, 20, 0, tzinfo=VN)


def test_next_free_evening_sau_18h_khong_lay_hom_nay():
    now = datetime(2026, 11, 28, 18, 30, tzinfo=VN)
    assert next_free_evening("xomque", set(), now, {5}).date() == date(2026, 12, 5)


def test_next_free_evening_het_cua_so_tra_none():
    now = datetime(2026, 11, 28, 8, 0, tzinfo=VN)
    taken = {date(2026, 11, 28) + __import__("datetime").timedelta(days=i) for i in range(8)}
    assert next_free_evening("main", taken, now, {0, 1, 2, 3, 4, 5, 6}) is None


def test_refresh_kenh_hong_van_co_kenh_kia(monkeypatch, tmp_path):
    def yt(ch):
        if ch == "main":
            raise RuntimeError("invalid_grant")
        return FakeYouTube({"v1": {"privacyStatus": "private", "publishAt": "2026-11-29T13:00:00Z"}})

    monkeypatch.setattr(state, "video_ids_for", lambda ch: [("v1", "t")])
    s = refresh(datetime(2026, 11, 28, 8, 0, tzinfo=VN), youtube_for=yt, env={})
    assert "invalid_grant" in s["kenh"]["main"]["loi"][0]
    assert s["kenh"]["xomque"]["toi_da_chiem"] == ["2026-11-29"]
    assert s["kenh"]["xomque"]["toi_trong_ke_tiep"] == "2026-11-28T20:00:00+07:00"  # thứ Bảy 08:00, tối nay còn trống
    assert s["kenh"]["xomque"]["nhip"] == [0, 3, 5]
    state.save(s, tmp_path / "t.json")
    assert state.load(tmp_path / "t.json")["kenh"]["xomque"]["nhip"] == [0, 3, 5]


def test_load_khong_co_tep_tra_trang_thai_rong(tmp_path):
    s = state.load(tmp_path / "khong-co.json")
    assert s["kenh"] == {} and s["ban_giao"] == {} and s["thu_nghiem"] == []
