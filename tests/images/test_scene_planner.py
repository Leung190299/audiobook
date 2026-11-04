import pytest

from images.scene_planner import ScenePlan, ScenePlanError, plan_scenes


def _sentence(chapter_index, index, start, end, text=None):
    return {
        "chapter_index": chapter_index,
        "index": index,
        "text": text or f"Câu {chapter_index}.{index}.",
        "start_seconds": start,
        "end_seconds": end,
    }


def _metadata(chapters, sentences):
    return {"trope": "t", "title": "T", "sample_rate": 24000,
            "chapters": chapters, "sentences": sentences}


def test_chuong_200s_chia_thanh_4_canh_phu_kin_chuong():
    # 20 câu, mỗi câu 10s (có 0.15s nghỉ giữa câu như thật) -> mục tiêu 50s -> 4 cảnh.
    sentences = [_sentence(1, i + 1, i * 10.0, i * 10.0 + 9.85) for i in range(20)]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 200.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert [s.number for s in scenes] == [1, 2, 3, 4]
    assert scenes[0].start_seconds == 0.0
    assert scenes[-1].end_seconds == 200.0
    for prev, nxt in zip(scenes, scenes[1:]):
        assert nxt.start_seconds == prev.end_seconds  # không hở, không chồng
    # Mỗi cảnh xấp xỉ 50s: cắt tại ranh giới câu nên lệch tối đa một câu.
    for s in scenes:
        assert 40.0 <= s.end_seconds - s.start_seconds <= 60.0


def test_cat_dung_ranh_gioi_cau_va_ghep_text():
    sentences = [
        _sentence(1, 1, 0.0, 30.0, "Một."),
        _sentence(1, 2, 30.0, 60.0, "Hai."),
        _sentence(1, 3, 60.0, 90.0, "Ba."),
        _sentence(1, 4, 90.0, 120.0, "Bốn."),
    ]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 120.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=60.0)

    assert len(scenes) == 2
    assert scenes[0].text == "Một. Hai."
    assert scenes[1].text == "Ba. Bốn."
    assert scenes[1].start_seconds == 60.0


def test_chuong_ngan_hon_muc_tieu_thanh_mot_canh():
    sentences = [_sentence(1, 1, 0.0, 10.0), _sentence(1, 2, 10.0, 30.0)]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 30.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert scenes == [ScenePlan(1, 1, 0.0, 30.0, "Câu 1.1. Câu 1.2.")]


def test_it_cau_hon_so_canh_mong_muon_thi_moi_canh_mot_cau():
    # 3 câu rất dài trong chương 200s: muốn 4 cảnh nhưng chỉ có 3 câu.
    sentences = [_sentence(1, 1, 0.0, 70.0), _sentence(1, 2, 70.0, 140.0), _sentence(1, 3, 140.0, 200.0)]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 200.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert [s.number for s in scenes] == [1, 2, 3]
    assert [s.start_seconds for s in scenes] == [0.0, 70.0, 140.0]


def test_nhieu_chuong_giu_thu_tu_va_danh_so_lai_tu_1():
    sentences = [
        _sentence(1, 1, 0.0, 50.0), _sentence(1, 2, 50.0, 100.0),
        _sentence(2, 1, 100.5, 150.0), _sentence(2, 2, 150.0, 200.5),
    ]
    meta = _metadata(
        [{"index": 1, "start_seconds": 0.0, "end_seconds": 100.0},
         {"index": 2, "start_seconds": 100.5, "end_seconds": 200.5}],
        sentences,
    )

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert [(s.chapter_index, s.number) for s in scenes] == [(1, 1), (1, 2), (2, 1), (2, 2)]
    assert scenes[2].start_seconds == 100.5  # cảnh đầu chương 2 bám start của chương, không phải end chương 1


def test_thieu_mang_sentences_thi_bao_chay_lai_stage_2():
    meta = {"trope": "t", "title": "T", "sample_rate": 24000,
            "chapters": [{"index": 1, "start_seconds": 0.0, "end_seconds": 10.0}]}

    with pytest.raises(ScenePlanError, match="chạy lại stage 2"):
        plan_scenes(meta)


def test_chuong_khong_co_cau_nao_thi_bao_ro_chuong():
    meta = _metadata(
        [{"index": 1, "start_seconds": 0.0, "end_seconds": 10.0},
         {"index": 2, "start_seconds": 10.0, "end_seconds": 20.0}],
        [_sentence(1, 1, 0.0, 10.0)],
    )

    with pytest.raises(ScenePlanError, match="Chương 2"):
        plan_scenes(meta)
