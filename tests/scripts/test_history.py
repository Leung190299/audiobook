# tests/scripts/test_history.py
from datetime import date

from scripts import history
from scripts.topics import TOPICS

TODAY = date(2026, 9, 24)


def _entry(days_ago, topic="ho_hang_viet", setting="s1", title="T", premise="P"):
    d = date.fromordinal(TODAY.toordinal() - days_ago)
    return {"date": d.isoformat(), "topic": topic, "setting": setting, "title": title, "premise": premise}


def test_trung_tieu_de_trong_30_ngay_bi_chan_du_khac_dau_va_hoa_thuong():
    entries = [_entry(5, title="Bác Cả Đòi Chia Đất, Tôi Livestream Luôn")]
    assert history.is_duplicate(entries, "ho_hang_viet", "bac ca doi chia dat tôi LIVESTREAM luôn!", "", TODAY)


def test_trung_premise_bi_chan():
    entries = [_entry(10, premise="Bác cả đòi chia lại đất hương hoả trong đám giỗ.")]
    assert history.is_duplicate(entries, "ho_hang_viet", "Tiêu đề mới", "bác cả đòi chia lại đất hương hoả trong đám giỗ", TODAY)


def test_qua_30_ngay_hoac_khac_chu_de_thi_khong_tinh_trung():
    entries = [_entry(31, title="A"), _entry(1, topic="bo_me_trong_sinh", title="B")]
    assert not history.is_duplicate(entries, "ho_hang_viet", "A", "", TODAY)
    assert not history.is_duplicate(entries, "ho_hang_viet", "B", "", TODAY)


def test_premise_rong_khong_bao_gio_trung():
    entries = [_entry(1, title="X", premise="")]
    assert not history.is_duplicate(entries, "ho_hang_viet", "Y", "", TODAY)


def test_chon_boi_canh_chua_dung():
    settings = TOPICS["ho_hang_viet"].settings
    used = [_entry(i, setting=s) for i, s in enumerate(settings[:-1])]
    assert history.pick_setting(settings, used, "ho_hang_viet", TODAY) == settings[-1]


def test_het_boi_canh_thi_lay_cai_dung_lau_nhat():
    settings = ("a", "b", "c")
    used = [_entry(1, setting="a"), _entry(20, setting="b"), _entry(3, setting="c")]
    assert history.pick_setting(settings, used, "ho_hang_viet", TODAY) == "b"


def test_ghi_va_doc_lai(tmp_path):
    path = tmp_path / "topics_history.json"
    history.record("ho_hang_viet", "s", "Tiêu đề", "Premise", "x.json", TODAY, path)
    entries = history.load_history(path)
    assert entries[0]["topic"] == "ho_hang_viet"
    assert history.recent_premises(entries, "ho_hang_viet", TODAY) == ["Tiêu đề — Premise"]
