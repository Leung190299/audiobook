from datetime import date

from keywords.matching import find_bank_story
from scripts.story_bank import Story


def _story(i, title, priority="A", publish_date=None, premise="p"):
    return Story(id=i, topic="ho_hang_viet", series="Truyện lẻ", title=title, premise=premise, twist="t",
                 hook="h", comment_question="q", thumb_keywords=(), timing="Quanh năm",
                 priority=priority, publish_date=publish_date)


def test_khop_tieu_de_theo_uu_tien_roi_id():
    stories = [_story(3, "Mẹ Chồng Giữ Sổ Đỏ Nhà Tôi", "B"), _story(2, "Mẹ Chồng Giấu Sổ Đỏ", "A"), _story(1, "Chuyện khác")]
    assert find_bank_story("mẹ chồng sổ đỏ", stories, set()).id == 2


def test_bo_truyen_da_dung_va_truyen_da_hen_ngay():
    stories = [_story(1, "Mẹ Chồng Giữ Sổ Đỏ"), _story(2, "Mẹ Chồng Đòi Sổ Đỏ", publish_date=date(2026, 12, 1))]
    assert find_bank_story("mẹ chồng sổ đỏ", stories, {1}) is None


def test_khong_khop_premise_de_tranh_khop_nham():
    stories = [_story(1, "Chuyện làm dâu", premise="con rể ở nhà vợ ba năm")]
    assert find_bank_story("con rể ở nhà vợ", stories, set()) is None
