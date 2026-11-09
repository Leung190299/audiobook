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


# --- đánh dấu đã dựng (02/10/2026) -------------------------------------------


def test_cli_mark_used_danh_dau_truyen_da_dung(tmp_path):
    """Dựng xong mà chưa đăng thì kho vẫn coi là chưa dùng, nên hôm sau
    `--story auto` chọn lại đúng truyện đó và dựng lại từ đầu. Lượt 28/09 đã
    mất gần 2 tiếng như thế rồi đổ ở bước đổi tên file trùng."""
    from scripts import story_bank

    state = tmp_path / "state.json"

    assert story_bank.main(["--mark-used", "7", "--state", str(state)]) == 0

    assert story_bank.used_ids(state) == {7}
    assert story_bank.load_state(state)["7"]["status"] == "built"


def test_mark_used_khong_de_len_trang_thai_da_dang(tmp_path):
    """Đăng rồi thì giữ nguyên 'published' kèm video_id, đừng hạ cấp."""
    from scripts import story_bank

    state = tmp_path / "state.json"
    story_bank.mark_used(7, state_path=state, status="published", video_id="abc")

    story_bank.main(["--mark-used", "7", "--state", str(state)])

    ban_ghi = story_bank.load_state(state)["7"]
    assert ban_ghi["status"] == "published"
    assert ban_ghi["video_id"] == "abc"


# --- dựng trước tối trống gần nhất (05/10/2026) -------------------------------
#
# Lịch biên tập kín mọi tối tới 25/10. pick_story(ngày phát sóng kế tiếp) cũ
# thấy 06/10 đã có #42 rồi thì vớ một truyện KHÔNG hẹn (#46), dựng mất một tiếng
# mà không có tối nào để chiếu. Việc đúng là dựng truyện đã hẹn cho tối gần nhất
# chưa có video.


def _state(path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_ngay_da_co_video_gom_ca_da_dang_lan_da_dung_dung_ngay_hen(bank, tmp_path):
    st = _state(tmp_path / "s.json", {
        "1": {"status": "published", "published_at": "2026-10-10T20:00:00+07:00"},
        "5": {"status": "built"},  # hẹn 16/10, dựng xong chưa đăng: 16/10 coi như đã có
    })

    days = story_bank.occupied_days(path=bank, state_path=st)

    assert date(2026, 10, 10) in days
    assert date(2026, 10, 16) in days


def test_truyen_hen_chua_dung_thi_ngay_do_chua_co_video(bank, tmp_path):
    st = _state(tmp_path / "s.json", {})

    assert date(2026, 10, 16) not in story_bank.occupied_days(path=bank, state_path=st)


def test_chon_truyen_hen_cho_toi_trong_gan_nhat(bank, tmp_path):
    """15/10 trống mà không ai hẹn -> chọn theo vòng xoay; nhưng nếu tối gần
    nhất chưa có video là tối có truyện hẹn thì phải dựng đúng truyện đó."""
    st = _state(tmp_path / "s.json", {})

    ngay, s = story_bank.pick_next_unfilled(
        date(2026, 10, 16), path=bank, state_path=st, rotation=ROT
    )

    assert ngay == date(2026, 10, 16) and s.id == 5


def test_bo_qua_toi_da_co_video_di_tiep_toi_toi_sau(bank, tmp_path):
    st = _state(tmp_path / "s.json", {
        "5": {"status": "built"},  # 16/10 đã có video
    })

    ngay, s = story_bank.pick_next_unfilled(
        date(2026, 10, 16), path=bank, state_path=st, rotation=ROT
    )

    # 16/10 có rồi -> sang 17/10, không ai hẹn -> theo vòng xoay, ưu tiên A.
    assert ngay == date(2026, 10, 17)
    assert s.id == 1


def test_toi_trong_khong_hen_thi_khong_lay_truyen_hen_ngay_khac(bank, tmp_path):
    """Truyện hẹn ngày khác phải để dành đúng ngày đó, không lấy sớm."""
    st = _state(tmp_path / "s.json", {})

    ngay, s = story_bank.pick_next_unfilled(
        date(2026, 10, 1), path=bank, state_path=st, rotation=ROT
    )

    assert ngay == date(2026, 10, 1)
    assert s.id != 5


def test_free_evening_bo_qua_ca_ngay_da_dang_va_ngay_bien_tap_hen(bank, tmp_path):
    """Truyện không hẹn lúc đăng: trước đây mặc định 'tối mai' bất kể tối mai
    đã có video -- phải tự chỉ ngày bằng tay cho #6/#75 hôm 28/09 và #9 hôm 05/10."""
    st = _state(tmp_path / "s.json", {
        "1": {"status": "published", "published_at": "2026-10-15T20:00:00+07:00"},
    })

    # 15/10 đã đăng, 16/10 biên tập hẹn #5 -> tối trống đầu tiên là 17/10.
    assert story_bank.first_free_evening(
        date(2026, 10, 15), path=bank, state_path=st
    ) == date(2026, 10, 17)


def test_cli_pick_dung_truoc_toi_trong(bank, tmp_path, capsys):
    st = _state(tmp_path / "s.json", {"5": {"status": "built"}})

    rc = story_bank.main(["--pick", "--date", "2026-10-16", "--bank", str(bank),
                          "--state", str(st), "--rotation", ",".join(ROT)])

    assert rc == 0
    assert capsys.readouterr().out.strip() == "1"  # 16/10 có rồi -> dựng cho 17/10


def test_set_air_time_dat_va_xoa_gio_chieu(tmp_path):
    from scripts.story_bank import load_state, set_air_time

    state = tmp_path / "state.json"
    set_air_time(5, "2026-11-12T20:00:00+07:00", state_path=state)
    assert load_state(state)["5"] == {"status": "published", "published_at": "2026-11-12T20:00:00+07:00"}
    # Bỏ hẹn (về kho): xoá hẳn giờ, mark_used không làm được việc này.
    set_air_time(5, None, state_path=state)
    assert load_state(state)["5"] == {"status": "published"}


def test_het_truyen_dung_chu_de_thi_lay_chu_de_khac_chu_khong_bo_trong(bank, tmp_path):
    # 10/11: kho thay 50 truyện từ doc, hoc_duong chỉ còn 2 -> thứ Bảy không
    # được trống. Chủ đề của ngày không có truyện nào -> vẫn ra truyện A của
    # chủ đề khác (bỏ qua Tết ngoài mùa và truyện đã hẹn ngày).
    s = story_bank.pick_story(date(2026, 9, 28), path=bank,
                              state_path=tmp_path / "st.json", rotation=("hoc_duong",) * 7)

    assert s is not None and s.id == 1
