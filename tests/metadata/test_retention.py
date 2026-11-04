# tests/metadata/test_retention.py
import json

import pytest

from metadata.retention import (
    RetentionError,
    analyze,
    find_props,
    load_retention_csv,
    render_markdown,
    spoken_between,
    video_duration,
)

DURATION = 1000.0  # 1% vị trí = 10 giây


def _curve(cliff_at: int | None = 50, hook_drop: float = 20.0) -> list[tuple[float, float]]:
    """100% -> rơi `hook_drop` trong 30s đầu -> trượt 0.2/điểm -> vực 6 điểm ở `cliff_at`%."""
    points, y = [], 100.0
    for x in range(101):
        if 0 < x <= 3:
            y -= hook_drop / 3
        elif x > 3:
            y -= 0.2
            if x == cliff_at:
                y -= 6.0
        points.append((float(x), y))
    return points


def _write(tmp_path, text: str):
    path = tmp_path / "r.csv"
    path.write_text(text, encoding="utf-8")
    return path


# --- đọc CSV ------------------------------------------------------------------


def test_chon_cot_tuyet_doi_bo_cot_tuong_doi(tmp_path):
    rows = ["Video position (%),Relative audience retention,Absolute audience retention (%)"]
    rows += [f"{x},0.5,{100 - x / 2}" for x in range(0, 101, 10)]
    points = load_retention_csv(_write(tmp_path, "\n".join(rows)))
    assert points[0] == (0.0, 100.0)
    assert points[-1] == (100.0, 50.0)


def test_csv_tieng_viet_dau_phay_thap_phan_va_ti_le_0_1(tmp_path):
    rows = ["Vị trí trong video,Tỷ lệ giữ chân khán giả tuyệt đối"]
    rows += [f'"0,{x:02d}","0,{90 - x // 2:02d}"' for x in range(0, 100, 10)]
    points = load_retention_csv(_write(tmp_path, "\n".join(rows)))
    # 0-1 được đổi ra phần trăm ở cả hai cột.
    assert points[1] == pytest.approx((10.0, 85.0))


def test_csv_khong_tieu_de_lay_hai_cot_so_dau(tmp_path):
    rows = [f"{x}%,{100 - x}%" for x in range(0, 100, 10)]
    points = load_retention_csv(_write(tmp_path, "\n".join(rows)))
    assert points[2] == (20.0, 80.0)


def test_csv_qua_it_diem_thi_bao_loi_ro(tmp_path):
    with pytest.raises(RetentionError, match="ít nhất 8"):
        load_retention_csv(_write(tmp_path, "position,retention\n0,100\n50,60\n"))


# --- phân tích ----------------------------------------------------------------


def test_roi_dau_tinh_trong_30_giay_dau():
    report = analyze(_curve(hook_drop=30.0), DURATION)
    assert report.hook_leak == pytest.approx(30.0)
    assert report.hook_verdict == "rò"


def test_tim_dung_vuc_va_khong_tinh_vao_truot():
    report = analyze(_curve(cliff_at=50), DURATION)
    assert len(report.cliffs) == 1
    c = report.cliffs[0]
    assert (c.start_seconds, c.end_seconds) == (490.0, 500.0)
    assert c.lost == pytest.approx(6.2)
    # 0.2 điểm mỗi 10 giây = 1.2 điểm/phút; vực không kéo con số này lên.
    assert report.slide_per_minute == pytest.approx(1.2)


def test_vuc_o_doan_ket_khong_tinh():
    # Card kết / người nghe biết truyện hết: luôn tụt, không phải lỗi truyện.
    report = analyze(_curve(cliff_at=99), DURATION)
    assert report.cliffs == []


def test_duong_tron_tru_khong_co_vuc():
    report = analyze(_curve(cliff_at=None, hook_drop=10.0), DURATION)
    assert report.cliffs == []
    assert "giữ chân ổn" in render_markdown(report)


# --- nối với mốc câu ----------------------------------------------------------

PROPS = {
    "title": "Mẹ Chồng Ký Hợp Đồng",
    "outroSeconds": 8.0,
    "chapters": [
        {"heading": "Mở đầu", "startSeconds": 0.0, "endSeconds": 24.0,
         "sentences": [{"text": "Ký đây.", "startSeconds": 0.0, "endSeconds": 24.0}]},
        {"heading": "Lương tháng đầu", "startSeconds": 25.0, "endSeconds": 992.0,
         "sentences": [
             {"text": "Câu trước vực.", "startSeconds": 480.0, "endSeconds": 489.0},
             {"text": "Bà nội đình công.", "startSeconds": 489.5, "endSeconds": 495.0},
             {"text": "Cả nhà im lặng.", "startSeconds": 495.5, "endSeconds": 501.0},
             {"text": "Câu sau.", "startSeconds": 502.0, "endSeconds": 992.0},
         ]},
    ],
}


def test_do_dai_video_gom_ca_card_ket():
    assert video_duration(PROPS) == 1000.0


def test_cau_dang_doc_trong_doan_vuc():
    heading, said = spoken_between(PROPS, 490.0, 500.0)
    assert heading == "Lương tháng đầu"
    assert said == ["Bà nội đình công.", "Cả nhà im lặng."]


def test_bao_cao_in_cau_dang_doc_o_vuc():
    text = render_markdown(analyze(_curve(cliff_at=50), DURATION), PROPS["title"], PROPS)
    assert "8:10–8:20" in text
    assert "“Bà nội đình công. Cả nhà im lặng.”" in text


def test_tim_props_qua_index_theo_video_id(tmp_path):
    episodes = tmp_path / "episodes"
    episodes.mkdir()
    (episodes / "bo_me-20261101T0000Z-full-props.json").write_text(json.dumps(PROPS))
    index = tmp_path / "index.jsonl"
    index.write_text(
        json.dumps({"video_id": "khac", "index": "/x/khac-full.json"}) + "\n"
        + json.dumps({"video_id": "abc", "index": "/x/output/metadata/bo_me-20261101T0000Z-full.json"}) + "\n"
    )
    assert find_props("abc", index, episodes) == episodes / "bo_me-20261101T0000Z-full-props.json"
    assert find_props("khong-co", index, episodes) is None
