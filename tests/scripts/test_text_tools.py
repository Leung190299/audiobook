# tests/scripts/test_text_tools.py
from scripts.text_tools import locate_quote, span_within


def _s(durations, chapter=1):
    out, t = [], 0.0
    for i, d in enumerate(durations):
        out.append({"text": f"Câu số {i} của truyện này.", "start_seconds": t, "end_seconds": t + d, "chapter_index": chapter})
        t += d
    return out


def test_span_mo_rong_toi_min_khong_qua_max():
    s = _s([5] * 20)
    assert span_within(s, 3, 20, 30) == (3, 6)


def test_span_vuong_cau_dai_thi_lui_diem_dau():
    s = _s([5, 5, 5, 5, 5, 25, 5])
    # từ câu 3: 3+4 = 10s, thêm câu 5 (25s) vượt 30 -> lùi về câu 1: 20s
    assert span_within(s, 3, 20, 30) == (1, 4)


def test_span_khong_bac_qua_chuong():
    s = _s([5, 5]) + _s([5, 5, 5, 5, 5], chapter=2)
    for i, x in enumerate(s[2:], start=2):
        x["start_seconds"] += 10; x["end_seconds"] += 10
    assert span_within(s, 0, 20, 30) is None


def test_locate_quote_chiu_sai_khac_nho():
    s = _s([3] * 10)
    s[4]["text"] = "Bác Cả đập bàn: 'Đất này của tao!'"
    s[5]["text"] = "Tôi cười: 'Bác nói to lên, em đang livestream.'"
    assert locate_quote("Bác Cả đập bàn: Đất này của tao! Tôi cười: Bác nói to lên, em đang livestream.", s) == (4, 5)
    assert locate_quote("một câu hoàn toàn không liên quan gì hết", s) is None
