# tests/trend/test_parse_json.py
import pytest

from trend.idea_generator import IdeaGenerationError, _parse_json_response

GOOD = {"slug": "a", "title_hint": "T", "trend_hook": "h", "idea": "i"}


def test_json_trong_code_fence():
    text = '```json\n{"slug":"a","title_hint":"T","trend_hook":"h","idea":"i"}\n```'
    assert _parse_json_response(text) == GOOD


def test_ky_tu_xuong_dong_tho_trong_chuoi():
    text = '{"slug":"a","title_hint":"T","trend_hook":"h","idea":"dòng 1\ndòng 2"}'
    assert _parse_json_response(text)["idea"] == "dòng 1\ndòng 2"


def test_hai_khoi_json_dinh_nhau_lay_khoi_co_du_field():
    text = '{"note":"rác"}{"slug":"a","title_hint":"T","trend_hook":"h","idea":"i"}'
    assert _parse_json_response(text) == GOOD


def test_van_ban_thua_bao_quanh_khoi_json():
    text = 'Đây là ý tưởng:\n{"slug":"a","title_hint":"T","trend_hook":"h","idea":"i"}\nHết.'
    assert _parse_json_response(text) == GOOD


def test_json_cut_cut_giua_chung_van_cuu_duoc_field_dau():
    text = '{"slug":"a","title_hint":"T","trend_hook":"h","idea":"i","extra":"bị cắt'
    data = _parse_json_response(text)
    assert data["idea"] == "i" and data["title_hint"] == "T"


def test_loi_tu_choi_khong_co_json_thi_nem_loi_kem_nguyen_van():
    with pytest.raises(IdeaGenerationError, match="mô hình ngôn ngữ"):
        _parse_json_response("Tôi không thể giúp, vì tôi chỉ là một mô hình ngôn ngữ.")
