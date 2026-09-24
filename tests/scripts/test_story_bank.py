# tests/scripts/test_story_bank.py
import json
from datetime import date

import pytest

from scripts import story_bank


@pytest.fixture
def bank(tmp_path):
    """Kho rút gọn nhưng đủ các trường hợp spec nêu."""
    data = {
        "version": "test",
        "writing_rules": ["Ngôi 'tôi'."],
        "series": {"Nhà Họ Trần": {"topic": "ho_hang_viet", "narrator": "Thảo", "cast": {}, "setting": "quê"}},
        "stories": [
            {"id": 1, "topic": "ho_hang_viet", "series": "Nhà Họ Trần", "title": "A1",
             "premise": "p", "twist": "t", "hook": "h", "comment_question": "q",
             "thumb_keywords": ["A1"], "timing": "Quanh năm", "priority": "A", "publish_date": None},
            {"id": 2, "topic": "ho_hang_viet", "series": "Truyện lẻ", "title": "B1",
             "premise": "p", "twist": "t", "hook": "h", "comment_question": "q",
             "thumb_keywords": ["B1"], "timing": "Quanh năm", "priority": "B", "publish_date": None},
            {"id": 3, "topic": "ho_hang_viet", "series": "Truyện lẻ", "title": "C1",
             "premise": "p", "twist": "t", "hook": "h", "comment_question": "q",
             "thumb_keywords": ["C1"], "timing": "Quanh năm", "priority": "C", "publish_date": None},
            {"id": 4, "topic": "ho_hang_viet", "series": "Truyện lẻ", "title": "Tết",
             "premise": "p", "twist": "t", "hook": "h", "comment_question": "q",
             "thumb_keywords": ["Tết"], "timing": "Trước Tết (T1/2027)", "priority": "A",
             "publish_date": None},
            {"id": 5, "topic": "nghe_la_hong_bien", "series": "Truyện lẻ", "title": "Hẹn ngày",
             "premise": "p", "twist": "t", "hook": "h", "comment_question": "q",
             "thumb_keywords": ["Hẹn"], "timing": "Quanh năm", "priority": "B",
             "publish_date": "2026-10-16"},
        ],
    }
    path = tmp_path / "story_bank.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


ROT = ("ho_hang_viet",) * 7


def test_load_bank_doc_duoc_luat_viet_va_series(bank):
    b = story_bank.load_bank(bank)

    assert b.writing_rules == ["Ngôi 'tôi'."]
    assert b.series["Nhà Họ Trần"]["narrator"] == "Thảo"
    assert len(b.stories) == 5


def test_get_story_theo_id(bank):
    s = story_bank.get_story(3, path=bank)

    assert s.title == "C1" and s.priority == "C"


def test_get_story_id_khong_co_thi_bao_loi(bank):
    with pytest.raises(story_bank.StoryBankError, match="99"):
        story_bank.get_story(99, path=bank)


def test_publish_date_trung_ngay_thi_uu_tien_tuyet_doi(bank, tmp_path):
    # Truyện 5 hẹn đúng 16/10 dù hôm đó vòng xoay là ho_hang_viet và nó ưu tiên B.
    s = story_bank.pick_story(date(2026, 10, 16), path=bank,
                              state_path=tmp_path / "st.json", rotation=ROT)

    assert s.id == 5


def test_khong_hen_ngay_thi_lay_uu_tien_A_dung_chu_de(bank, tmp_path):
    s = story_bank.pick_story(date(2026, 9, 28), path=bank,
                              state_path=tmp_path / "st.json", rotation=ROT)

    assert s.id == 1


def test_bo_qua_truyen_da_dung(bank, tmp_path):
    st = tmp_path / "st.json"
    story_bank.mark_used(1, state_path=st)

    s = story_bank.pick_story(date(2026, 9, 28), path=bank, state_path=st, rotation=ROT)

    assert s.id == 2  # A đã dùng -> sang B


def test_chi_lay_C_khi_het_A_va_B(bank, tmp_path):
    st = tmp_path / "st.json"
    for i in (1, 2):
        story_bank.mark_used(i, state_path=st)

    s = story_bank.pick_story(date(2026, 9, 28), path=bank, state_path=st, rotation=ROT)

    assert s.id == 3


def test_truyen_tet_bi_bo_qua_ngoai_mua(bank, tmp_path):
    st = tmp_path / "st.json"
    for i in (1, 2, 3):
        story_bank.mark_used(i, state_path=st)

    # Chỉ còn truyện Tết (id 4), nhưng 28/09 ngoài mùa -> hết truyện.
    assert story_bank.pick_story(date(2026, 9, 28), path=bank, state_path=st, rotation=ROT) is None


def test_truyen_tet_duoc_chon_trong_mua(bank, tmp_path):
    s = story_bank.pick_story(date(2027, 1, 10), path=bank,
                              state_path=tmp_path / "st.json", rotation=ROT)

    # Trong mùa Tết, truyện 1 và 4 cùng ưu tiên A -> lấy id nhỏ hơn cho ổn định.
    assert s.id in (1, 4)
    assert story_bank.in_tet_window(date(2027, 1, 10))
    assert not story_bank.in_tet_window(date(2026, 9, 28))
    assert story_bank.in_tet_window(date(2027, 1, 4))
    assert story_bank.in_tet_window(date(2027, 2, 5))
    assert not story_bank.in_tet_window(date(2027, 2, 6))


def test_het_truyen_thi_tra_none(bank, tmp_path):
    st = tmp_path / "st.json"
    for i in (1, 2, 3, 4, 5):
        story_bank.mark_used(i, state_path=st)

    assert story_bank.pick_story(date(2026, 9, 28), path=bank, state_path=st, rotation=ROT) is None


def test_mark_used_ghi_state_va_khong_dung_story_bank_json(bank, tmp_path):
    st = tmp_path / "st.json"
    story_bank.mark_used(1, state_path=st, video_id="abc", published_at="2026-09-28")

    data = json.loads(st.read_text(encoding="utf-8"))
    assert data["1"]["status"] == "used"
    assert data["1"]["video_id"] == "abc"
    # Kho gốc không bị sửa.
    assert json.loads(bank.read_text(encoding="utf-8"))["stories"][0]["publish_date"] is None


def test_pick_upcoming_tra_lich_nhieu_ngay(bank, tmp_path):
    lich = story_bank.pick_upcoming(date(2026, 9, 28), days=3, path=bank,
                                    state_path=tmp_path / "st.json", rotation=ROT)

    assert [d for d, _ in lich] == [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)]
    # Không lặp truyện giữa các ngày trong cùng một lần xem trước.
    ids = [s.id for _, s in lich if s]
    assert len(ids) == len(set(ids))


# --- ngày phát sóng kế tiếp + CLI xem trước ---


def test_next_air_date_truoc_20h_thi_la_hom_nay():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 9, 28, 14, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    assert story_bank.next_air_date(now) == date(2026, 9, 28)


def test_next_air_date_sau_20h_thi_la_ngay_mai():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 9, 28, 20, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    assert story_bank.next_air_date(now) == date(2026, 9, 29)


def test_cli_upcoming_in_lich_va_thoat_0(bank, tmp_path, capsys):
    code = story_bank.main(
        ["--upcoming", "2", "--from", "2026-09-28",
         "--bank", str(bank), "--state", str(tmp_path / "st.json"),
         "--rotation", "ho_hang_viet"]
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "2026-09-28" in out and "A1" in out


def test_cli_pick_in_dung_mot_id(bank, tmp_path, capsys):
    code = story_bank.main(
        ["--pick", "--date", "2026-10-16", "--bank", str(bank),
         "--state", str(tmp_path / "st.json"), "--rotation", "ho_hang_viet"]
    )

    assert code == 0
    assert capsys.readouterr().out.strip() == "5"


def test_cli_pick_het_truyen_thi_in_rong_va_thoat_khac_0(bank, tmp_path, capsys):
    st = tmp_path / "st.json"
    for i in (1, 2, 3, 4, 5):
        story_bank.mark_used(i, state_path=st)

    code = story_bank.main(
        ["--pick", "--date", "2026-09-28", "--bank", str(bank),
         "--state", str(st), "--rotation", "ho_hang_viet"]
    )

    assert code != 0
    assert capsys.readouterr().out.strip() == ""
