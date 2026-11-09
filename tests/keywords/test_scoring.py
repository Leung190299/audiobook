from keywords.scoring import (
    Cluster, content_words, demand_level, novelty_level, phrase_in_text, score_clusters,
    strip_accents, view_level, voice_level,
)
from keywords.sources import CompetitorVideo


def test_bo_dau_ke_ca_chu_d_gach():
    assert strip_accents("Sổ Đỏ Mẹ Chồng") == "so do me chong"


def test_tu_mang_nghia_bo_truyen_audio_va_tu_chuc_nang():
    assert content_words("truyện audio mẹ chồng giữ sổ đỏ full") == ["me", "chong", "giu", "so", "do"]


def test_cum_co_mat_trong_tieu_de_khi_du_tu_khong_phan_biet_dau_hoa():
    title = "Mẹ Chồng Giữ Sổ Đỏ Tôi Mua, Tôi Mời Công Chứng Đến Bàn Ăn"
    assert phrase_in_text("mẹ chồng sổ đỏ", title)
    assert phrase_in_text("truyện audio mẹ chồng giữ sổ đỏ", title)
    assert not phrase_in_text("mẹ chồng vàng cưới", title)


def test_cum_dai_duoc_thieu_mot_tu_cum_ngan_thi_khong():
    assert phrase_in_text("mẹ chồng giữ sổ đỏ nhà", "Mẹ Chồng Giữ Sổ Đỏ Tôi Mua", slack=1)
    assert not phrase_in_text("mẹ chồng vàng", "Mẹ Chồng Giữ Sổ Đỏ", slack=1)


def test_cau_theo_ti_le_voi_cum_manh_nhat():
    assert demand_level(100, 100) == 3
    assert demand_level(30, 100) == 2
    assert demand_level(5, 100) == 1
    assert demand_level(0, 100) == 0


def _video(title, ratio, channel="Kênh A"):
    return CompetitorVideo(channel=channel, title=title, views=1000, age_days=3.0, ratio=ratio)


def test_view_theo_video_doi_thu_khop_noi_nhat():
    videos = [_video("Mẹ Chồng Giữ Sổ Đỏ Của Tôi", 2.5), _video("Mẹ Chồng Giữ Sổ Đỏ Nhà Con", 0.4), _video("Truyện khác", 9)]
    level, evidence = view_level("mẹ chồng sổ đỏ", videos)
    assert level == 3
    assert evidence[0].startswith("Kênh A: Mẹ Chồng Giữ Sổ Đỏ Của Tôi (x2.5)")
    assert view_level("con rể ở rể", videos) == (0, [])


def test_giong_chan_tu_cam_va_uu_tien_tu_gia_dinh():
    block = ["ma", "xuyên không"]
    allow = ["mẹ chồng", "sổ đỏ"]
    assert voice_level("truyện ma mẹ chồng", block, allow) == 0
    assert voice_level("mẹ chồng xuyên không", block, allow) == 0
    assert voice_level("mẹ chồng giữ sổ đỏ", block, allow) == 3
    assert voice_level("thuê nhà mùa mưa", block, allow) == 1


def test_moi_bang_0_khi_vua_dung_1_khi_kho_da_co_3_khi_chua_ai_lam():
    titles = ["Mẹ Chồng Giữ Sổ Đỏ Tôi Mua"]
    assert novelty_level("mẹ chồng giữ sổ đỏ", titles, ["mẹ chồng giữ sổ đỏ"]) == 0
    assert novelty_level("mẹ chồng sổ đỏ", titles, []) == 1
    assert novelty_level("em chồng vay app đen", titles, []) == 3


def test_xep_hang_theo_tong_va_bo_cum_duoi_2_tu():
    suggest = {"truyện audio mẹ chồng giữ sổ đỏ": 90, "truyện audio ma": 100, "truyện audio em chồng": 40}
    clusters = score_clusters(suggest, [], [], [], ["ma"], ["mẹ chồng", "em chồng"])
    assert [c.phrase for c in clusters][0] == "truyện audio mẹ chồng giữ sổ đỏ"
    assert all(c.phrase != "truyện audio ma" for c in clusters)  # chỉ còn 1 từ mang nghĩa
    top = clusters[0]
    assert isinstance(top, Cluster) and top.total == top.demand + top.view + top.voice + top.novelty
