# tests/trend/test_idea_generator.py
from trend.idea_generator import (
    STORY_FRAMES,
    TIME_TRAVEL_FRAME,
    banned_frames,
    build_idea_prompt,
    clean_title,
    uses_time_travel,
)
from trend.sources import TrendSignals

TS = [f"Trọng sinh tôi mặc kệ mẹ chồng lần {i} (slug_{i})" for i in range(22)]


def _signals() -> TrendSignals:
    return TrendSignals(
        feeds={
            "Tâm sự (VnExpress)": ["Mẹ chồng đòi giữ sổ đỏ", "Chồng giấu quỹ đen"],
            "Kênh YouTube UCabc": ["THIÊN KIM THẬT TRỞ VỀ VẢ MẶT TRÀ XANH", "Tiếng lòng cá mặn"],
        },
        google_trends=["bóng đá"],
    )


# --- nhận diện và cấm khuôn xuyên không ---


def test_uses_time_travel_bat_cac_bien_the():
    assert uses_time_travel("Trọng sinh tôi mặc kệ chồng")
    assert uses_time_travel("Xuyên không về làm thiên kim")
    assert uses_time_travel("Sống lại một đời, tôi…")
    assert not uses_time_travel("Thiên kim thật trở về từ làng chài")


def test_ba_tap_gan_nhat_co_xuyen_khong_thi_hom_nay_cam():
    assert banned_frames(TS) == [TIME_TRAVEL_FRAME]


def test_ba_tap_gan_nhat_sach_thi_khong_cam():
    recent = TS[:5] + ["Thiên kim thật (a)", "Trà xanh (b)", "Ly hôn xong phất (c)"]
    assert banned_frames(recent) == []


def test_chi_mot_trong_ba_tap_gan_nhat_cung_du_cam():
    recent = ["Thiên kim thật (a)", "Trọng sinh tôi (b)", "Ly hôn (c)"]
    assert banned_frames(recent) == [TIME_TRAVEL_FRAME]


def test_lich_su_rong_thi_khong_cam():
    assert banned_frames([]) == []


# --- prompt ---


def test_prompt_khong_tu_khai_the_loai_trong_sinh():
    prompt = build_idea_prompt(_signals(), TS)
    first_lines = "\n".join(prompt.splitlines()[:4]).lower()
    assert "trọng sinh" not in first_lines


def test_prompt_tach_kenh_youtube_ra_muc_khuon_dang_hot():
    prompt = build_idea_prompt(_signals(), TS)
    news_idx = prompt.index("Mẹ chồng đòi giữ sổ đỏ")
    frames_header = prompt.index("KHUÔN")
    yt_idx = prompt.index("THIÊN KIM THẬT TRỞ VỀ VẢ MẶT TRÀ XANH")
    # Tiêu đề kênh đối thủ nằm trong mục khuôn, sau tin báo, không lẫn với tin báo.
    assert news_idx < frames_header < yt_idx


def test_prompt_liet_ke_cac_khuon_va_neu_khuon_bi_cam():
    prompt = build_idea_prompt(_signals(), TS)
    for frame in STORY_FRAMES:
        assert frame in prompt
    assert "CẤM" in prompt
    assert TIME_TRAVEL_FRAME in prompt


def test_prompt_khong_neu_cam_khi_lich_su_sach():
    prompt = build_idea_prompt(_signals(), ["Thiên kim (a)", "Trà xanh (b)", "Ly hôn (c)"])
    assert "không bị cấm khuôn nào" in prompt.lower()
    assert "CẤM hôm nay" not in prompt


def test_prompt_noi_ro_tieu_de_trung_mo_dau_la_loi():
    prompt = build_idea_prompt(_signals(), TS)
    assert "không được bắt đầu bằng" in prompt.lower()
    # Danh sách đã làm chỉ đưa 8 cái gần nhất, không phải 15: đưa nhiều chỉ dạy mẫu.
    assert prompt.count("Trọng sinh tôi mặc kệ mẹ chồng lần") == 8


# --- tiêu đề không được mang vỏ bọc / tên kênh đối thủ ---


def test_clean_title_bo_vo_boc_va_ten_kenh_doi_thu():
    raw = "[Truyện Audio Full] | TRÀ XANH ÉP THIÊN KIM TRẢ VÀNG, BỊ BÓC PHỐT | Vả Mặt Audio"
    assert clean_title(raw) == "TRÀ XANH ÉP THIÊN KIM TRẢ VÀNG, BỊ BÓC PHỐT"


def test_clean_title_bo_hau_to_kenh_dang_hai_gach_dung():
    raw = "Truyện Audio || Trúc Mã Cưng Vợ Từ Bé || ChuChu Audio"
    assert clean_title(raw) == "Trúc Mã Cưng Vợ Từ Bé"


def test_clean_title_giu_nguyen_tieu_de_sach():
    raw = "Mẹ chồng sang tên căn nhà 9 tỷ, đọc xong hợp đồng tôi bóc phốt cả hào môn"
    assert clean_title(raw) == raw


def test_clean_title_giu_dau_phay_va_dau_hai_cham_trong_noi_dung():
    raw = "Thiên Kim Mỏ Hỗn Trở Về: Vạch Mặt Trà Xanh, Đáp Trả Cả Hào Môn"
    assert clean_title(raw) == raw


def test_prompt_cam_vo_boc_tieu_de():
    prompt = build_idea_prompt(_signals(), TS)
    assert "tên kênh" in prompt.lower()
    assert "[Truyện Audio Full]" in prompt
