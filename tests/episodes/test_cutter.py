import pytest

from episodes.cutter import (
    COLD_OPEN_GAP_SECONDS,
    COLD_OPEN_MAX_SECONDS,
    COLD_OPEN_MIN_SECONDS,
    COLD_OPEN_RESERVED_TAIL_SENTENCES,
    OUTRO_SECONDS,
    EpisodeCutError,
    pick_cold_open,
    plan_cuts,
)
from episodes.plan import plan_episodes
from tests.episodes.conftest import SENTENCE_SECONDS, make_tts_metadata


def test_plan_cuts_moi_tap_dung_mot_khoang_chuong():
    tts = make_tts_metadata()
    cuts = plan_cuts(tts, plan_episodes(6))
    assert len(cuts) == 3
    by_index = {c["index"]: c for c in tts["chapters"]}
    for cut in cuts:
        ep = cut.episode
        assert cut.body_source_start_seconds == by_index[ep.first_chapter]["start_seconds"]
        assert cut.body_source_end_seconds == by_index[ep.last_chapter]["end_seconds"]
        assert cut.outro_seconds == OUTRO_SECONDS


def test_cold_open_lay_tu_chuong_cuoi_tap_khong_dung_cau_cuoi():
    tts = make_tts_metadata()
    cuts = plan_cuts(tts, plan_episodes(6))
    for cut in cuts:
        co = cut.cold_open
        assert co is not None
        assert co.chapter_index == cut.episode.last_chapter
        chapter_sentences = [s for s in tts["sentences"] if s["chapter_index"] == co.chapter_index]
        reserved_start = chapter_sentences[-COLD_OPEN_RESERVED_TAIL_SENTENCES]["start_seconds"]
        assert co.source_end_seconds <= reserved_start
        assert COLD_OPEN_MIN_SECONDS <= co.duration_seconds <= COLD_OPEN_MAX_SECONDS
        # Khớp ranh giới câu.
        starts = {s["start_seconds"] for s in chapter_sentences}
        ends = {s["end_seconds"] for s in chapter_sentences}
        assert co.source_start_seconds in starts and co.source_end_seconds in ends


def test_body_offset_va_chuyen_truc():
    tts = make_tts_metadata()
    cut = plan_cuts(tts, plan_episodes(6))[1]
    assert cut.body_offset_seconds == pytest.approx(cut.cold_open.duration_seconds + COLD_OPEN_GAP_SECONDS)
    assert cut.to_episode_time(cut.body_source_start_seconds) == pytest.approx(cut.body_offset_seconds)
    assert cut.total_seconds == pytest.approx(
        cut.body_offset_seconds + cut.body_duration_seconds + OUTRO_SECONDS
    )


def test_chuong_qua_ngan_thi_khong_co_cold_open():
    sentences = [
        {"chapter_index": 1, "index": i, "text": "x", "start_seconds": i * 3.0, "end_seconds": i * 3.0 + 3.0}
        for i in range(4)
    ]
    assert pick_cold_open(sentences, 1) is None


def test_thieu_moc_cau_thi_loi():
    tts = make_tts_metadata()
    tts["sentences"] = []
    with pytest.raises(EpisodeCutError):
        plan_cuts(tts, plan_episodes(6))


def test_thieu_chuong_thi_loi_neu_ro_tap():
    tts = make_tts_metadata()
    tts["chapters"] = [c for c in tts["chapters"] if c["index"] != 4]
    with pytest.raises(EpisodeCutError, match="Tập 2/3"):
        plan_cuts(tts, plan_episodes(6))


def test_cold_open_toi_da_khong_vuot_max():
    # Chương dài 40 câu x 3s: cửa sổ phải dừng ở <= 35s.
    sentences = [
        {"chapter_index": 1, "index": i, "text": "x", "start_seconds": i * SENTENCE_SECONDS, "end_seconds": (i + 1) * SENTENCE_SECONDS}
        for i in range(40)
    ]
    co = pick_cold_open(sentences, 1)
    assert co.duration_seconds <= COLD_OPEN_MAX_SECONDS
    assert co.duration_seconds >= COLD_OPEN_MIN_SECONDS
