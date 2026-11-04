"""Test cho các mảnh mới của lượt chạy hằng ngày: trend, upload, notify.

Chỉ test phần thuần logic (parse, sanitize, slug, lịch sử) — không gọi mạng.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from trend.idea_generator import IdeaGenerationError, StoryIdea, _parse_json_response, slugify
from trend.storage import append_history, load_recent_titles, save_idea
from upload.uploader import (
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
    sanitize_description,
    sanitize_tags,
    sanitize_title,
)

# --- slugify -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Mẹ chồng giấu của", "me_chong_giau_cua"),
        ("Trọng sinh báo thù", "trong_sinh_bao_thu"),
        ("đứa con bị bỏ rơi", "dua_con_bi_bo_roi"),
        ("Vả mặt  —  công sở!!!", "va_mat_cong_so"),
    ],
)
def test_slugify_bo_dau_va_ky_tu_dac_biet(raw, expected):
    assert slugify(raw) == expected


def test_slugify_chuoi_khong_con_ky_tu_nao_thi_dung_fallback():
    assert slugify("!!!???", fallback="trend") == "trend"


def test_slugify_gioi_han_do_dai():
    assert len(slugify("a" * 100)) <= 40


# --- parse JSON từ Gemini ----------------------------------------------------


def test_parse_json_boc_trong_code_fence():
    raw = '```json\n{"slug": "abc", "idea": "x"}\n```'
    assert _parse_json_response(raw) == {"slug": "abc", "idea": "x"}


def test_parse_json_khong_hop_le_thi_bao_loi_ro_rang():
    with pytest.raises(IdeaGenerationError, match="Không parse được JSON"):
        _parse_json_response("Xin chào, đây không phải JSON")


# --- lưu ý tưởng + lịch sử ---------------------------------------------------


def _idea(slug="me_chong_giau_cua") -> StoryIdea:
    return StoryIdea(
        slug=slug,
        title_hint="Mẹ chồng giấu sổ đỏ",
        trend_hook="Chủ đề tài sản gia đình đang lên",
        idea="Một câu chuyện hư cấu về tranh chấp tài sản trong gia đình.",
    )


def test_save_idea_ghi_file_txt_chi_chua_noi_dung_truyen(tmp_path: Path):
    txt_path, json_path = save_idea(_idea(), tmp_path)

    content = txt_path.read_text(encoding="utf-8")
    # File .txt đi thẳng vào prompt Gemini ở stage 1 — không được lẫn nhãn kỹ thuật.
    assert "trend_hook" not in content
    assert "slug" not in content
    assert "Mẹ chồng giấu sổ đỏ" in content

    assert json.loads(json_path.read_text(encoding="utf-8"))["slug"] == "me_chong_giau_cua"


def test_lich_su_duoc_doc_lai_de_tranh_lam_trung(tmp_path: Path):
    append_history(tmp_path, _idea("tap_mot"))
    append_history(tmp_path, _idea("tap_hai"))

    recent = load_recent_titles(tmp_path)
    assert len(recent) == 2
    assert "tap_hai" in recent[-1]


def test_lich_su_hong_thi_coi_nhu_rong_chu_khong_lam_vo_luot_chay(tmp_path: Path):
    (tmp_path / "history.json").write_text("{ khong phai json", encoding="utf-8")
    assert load_recent_titles(tmp_path) == []


def test_lich_su_bi_cat_bot_khong_phinh_vo_han(tmp_path: Path):
    for i in range(40):
        append_history(tmp_path, _idea(f"tap_{i}"))
    entries = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert len(entries) == 30
    assert entries[-1]["slug"] == "tap_39"


# --- sanitize trước khi gọi YouTube API --------------------------------------


def test_title_bi_cat_dung_gioi_han_youtube():
    assert len(sanitize_title("A" * 200)) == MAX_TITLE_CHARS


def test_title_bo_xuong_dong_va_ngoac_nhon():
    # YouTube từ chối '<' và '>' trong snippet.
    assert sanitize_title("Trọng sinh <báo thù>\nphần 2") == "Trọng sinh (báo thù) phần 2"


def test_description_dai_bi_cat_o_ranh_gioi_dong():
    description = "\n".join(f"{i:02d}:00 Chương {i}" for i in range(500))
    result = sanitize_description(description)
    assert len(result) <= MAX_DESCRIPTION_CHARS
    # Không được đứt giữa một mốc chương.
    assert not result.endswith(" ")
    assert result.count("\n") > 0


def test_description_ngan_giu_nguyen():
    assert sanitize_description("  Mô tả ngắn  ") == "Mô tả ngắn"


def test_tags_bi_cat_khi_vuot_tong_do_dai():
    tags = [f"tu_khoa_rat_dai_so_{i}" for i in range(100)]
    result = sanitize_tags(tags)
    assert sum(len(t) + 1 for t in result) <= 450
    assert result[0] == tags[0]


def test_tags_bo_qua_chuoi_rong():
    assert sanitize_tags(["  ", "truyện audio", ""]) == ["truyện audio"]


# --- parse RSS Google Trends -------------------------------------------------


def test_parse_rss_google_trends_lay_ca_ngu_canh_tin_tuc():
    from trend.sources import _HT_NS

    rss = f"""<?xml version="1.0"?>
    <rss xmlns:ht="{_HT_NS[1:-1]}"><channel>
      <item>
        <title>giá vàng</title>
        <ht:news_item><ht:news_item_title>Vàng lập đỉnh mới</ht:news_item_title></ht:news_item>
      </item>
      <item><title>bão số 5</title></item>
    </channel></rss>"""

    root = ET.fromstring(rss)
    items = root.findall("./channel/item")
    assert len(items) == 2
    assert items[0].findtext(f"{_HT_NS}news_item/{_HT_NS}news_item_title") == "Vàng lập đỉnh mới"
