# tests/shorts/test_beats.py
"""3 Shorts từ short_beats (24/09/2026): 30-55s, mở bằng câu thoại, tiêu đề <= 50 ký tự + #Shorts."""

from shorts.planner import plan_beat_shorts, short_title_from_line
from shorts.storage import save_short_metadata

LINES = {
    (2, 3): "'Bác nói to lên, cháu đang livestream!'",
    (4, 5): "'Mợ ơi, sổ đỏ này photo màu đấy ạ.'",
}


def _tts(chapters=6, per_chapter=40, sec=2.5):
    sentences, chaps, t = [], [], 0.0
    for ci in range(1, chapters + 1):
        start = t
        for si in range(1, per_chapter + 1):
            text = LINES.get((ci, si), f"Câu thường số {ci} chấm {si} trong truyện.")
            sentences.append({"chapter_index": ci, "index": si, "text": text,
                              "start_seconds": t, "end_seconds": t + sec})
            t += sec
        chaps.append({"index": ci, "heading": f"Chương {ci}", "start_seconds": start, "end_seconds": t})
        t += 0.5
    return {"trope": "x", "title": "T", "chapters": chaps, "sentences": sentences}


def test_beat_thanh_short_30_55s_mo_bang_cau_thoai():
    tts = _tts()
    parts = plan_beat_shorts(tts, [
        "'Mợ ơi, sổ đỏ này photo màu đấy ạ.' Câu thường số 4 chấm 6 trong truyện.",
        "'Bác nói to lên, cháu đang livestream!' Câu thường số 2 chấm 4 trong truyện.",
    ])
    assert len(parts) == 3  # 2 beat + 1 trích đoạn bù
    assert [p.number for p in parts] == [1, 2, 3]
    beat_parts = [p for p in parts if p.hook_line]
    assert {p.hook_line for p in beat_parts} == set(LINES.values())
    for p in beat_parts:
        assert 30.0 <= p.duration_seconds <= 55.0
        assert p.captions[0].text == p.hook_line
    # Không chồng lấn nhau.
    spans = sorted((p.source_start_seconds, p.source_end_seconds) for p in parts)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))


def test_khong_do_duoc_beat_nao_thi_rai_trich_doan_cu():
    parts = plan_beat_shorts(_tts(), ["không có đoạn này đâu nhé bạn ơi thật đấy"])
    assert len(parts) == 3 and not any(p.hook_line for p in parts)


def test_tieu_de_short_la_cau_thoai_toi_da_50_ky_tu():
    t = short_title_from_line("'Bác nói to lên, cháu đang livestream!'")
    assert t == "'Bác nói to lên, cháu đang livestream!' #Shorts"
    long = short_title_from_line("Một câu thoại rất dài " * 6)
    assert long.endswith(" #Shorts")
    assert len(long.removesuffix(" #Shorts")) <= 50


def test_metadata_short_dung_tieu_de_cau_thoai(tmp_path):
    import json

    _, js = save_short_metadata(
        "s-part-01", "ho_hang_viet", "Bác Cả Đòi Đất", 1, 3, tmp_path,
        title_override="'Bác nói to lên!' #Shorts",
    )
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["title"] == "'Bác nói to lên!' #Shorts"
    assert "Nghe trọn" in data["description"]
