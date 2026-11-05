# tests/shorts/test_planner.py
import pytest

from shorts.planner import (
    MAX_PART_SECONDS,
    TEASER_COUNT,
    TEASER_POSITIONS,
    ShortPlanError,
    plan_parts,
    plan_teasers,
)


def _sentence(chapter_index: int, index: int, start: float, end: float, text: str | None = None) -> dict:
    return {
        "chapter_index": chapter_index,
        "index": index,
        "text": text or f"Câu {chapter_index}.{index}",
        "start_seconds": start,
        "end_seconds": end,
    }


def _chapter(index: int, heading: str) -> dict:
    return {"index": index, "heading": heading, "start_seconds": 0.0, "end_seconds": 0.0}


def _metadata(sentences: list[dict], chapters: list[dict]) -> dict:
    return {
        "trope": "t",
        "title": "T",
        "sample_rate": 24000,
        "chapters": chapters,
        "sentences": sentences,
    }


def _make_chapter_sentences(chapter_index: int, count: int, sentence_seconds: float = 3.0) -> list[dict]:
    """Dựng `count` câu liên tiếp, mỗi câu dài `sentence_seconds`, không nghỉ giữa câu."""
    out = []
    t = 0.0
    for i in range(1, count + 1):
        out.append(_sentence(chapter_index, i, t, t + sentence_seconds))
        t += sentence_seconds
    return out


def test_chuong_ngan_hon_ngan_sach_ra_dung_mot_phan():
    sentences = _make_chapter_sentences(1, 5, sentence_seconds=3.0)  # tổng 15s << 165s
    metadata = _metadata(sentences, [_chapter(1, "Chương 1: Mở đầu")])

    parts = plan_parts(metadata)

    assert len(parts) == 1
    assert parts[0].number == 1
    assert parts[0].chapter_index == 1
    assert parts[0].heading == "Chương 1: Mở đầu"
    assert parts[0].duration_seconds == pytest.approx(15.0)


def test_chuong_dai_hon_ngan_sach_bi_chia_khong_phan_nao_vuot_165s():
    # 100 câu x 3s = 300s, chắc chắn phải chia làm nhiều phần.
    sentences = _make_chapter_sentences(1, 100, sentence_seconds=3.0)
    metadata = _metadata(sentences, [_chapter(1, "Chương 1")])

    parts = plan_parts(metadata)

    assert len(parts) > 1
    for part in parts:
        assert part.duration_seconds <= MAX_PART_SECONDS


def test_ranh_gioi_chuong_luon_mo_phan_moi_ke_ca_khi_con_thua_cho():
    # Chương 1 chỉ có 10s (còn thừa rất nhiều so với ngân sách 165s), chương 2
    # phải bắt đầu phần mới, không được ghép vào phần của chương 1.
    sentences = _make_chapter_sentences(1, 2, sentence_seconds=5.0) + _make_chapter_sentences(
        2, 2, sentence_seconds=5.0
    )
    metadata = _metadata(
        sentences,
        [_chapter(1, "Chương 1"), _chapter(2, "Chương 2")],
    )

    parts = plan_parts(metadata)

    assert len(parts) == 2
    assert parts[0].chapter_index == 1
    assert parts[1].chapter_index == 2
    assert parts[1].number == 2


def test_danh_so_phan_lien_tuc_toan_tap_khong_danh_lai_theo_chuong():
    # 3 chương, mỗi chương đủ dài để tự chia làm 2 phần -> tổng 6 phần, đánh số 1..6.
    sentences = []
    for chapter_index in (1, 2, 3):
        sentences += _make_chapter_sentences(chapter_index, 60, sentence_seconds=3.0)  # 180s/chương
    metadata = _metadata(
        sentences,
        [_chapter(1, "C1"), _chapter(2, "C2"), _chapter(3, "C3")],
    )

    parts = plan_parts(metadata)

    assert [p.number for p in parts] == list(range(1, len(parts) + 1))
    # mỗi chương phải bị chia ra ít nhất 2 phần vì 180s > 165s
    assert len(parts) >= 6


def test_captions_moi_phan_bat_dau_tu_0_va_khong_am():
    sentences = _make_chapter_sentences(1, 60, sentence_seconds=3.0)
    metadata = _metadata(sentences, [_chapter(1, "Chương 1")])

    parts = plan_parts(metadata)

    for part in parts:
        assert part.captions[0].start_seconds == pytest.approx(0.0)
        for caption in part.captions:
            assert caption.start_seconds >= 0.0
            assert caption.end_seconds >= 0.0
            assert caption.end_seconds >= caption.start_seconds


def test_moi_cau_xuat_hien_dung_mot_lan_khong_sot_khong_lap():
    # Test quan trọng nhất: so sánh toàn bộ chuỗi text câu theo thứ tự giữa
    # input và output — không chỉ đếm số lượng — để bắt được lỗi off-by-one
    # trong vòng lặp đóng gói (ví dụ bỏ sót câu đầu/cuối mỗi phần, hoặc lặp
    # câu biên giữa hai phần liên tiếp).
    sentences = []
    for chapter_index in (1, 2, 3):
        sentences += _make_chapter_sentences(chapter_index, 37, sentence_seconds=4.1)
    metadata = _metadata(
        sentences,
        [_chapter(1, "C1"), _chapter(2, "C2"), _chapter(3, "C3")],
    )

    parts = plan_parts(metadata)

    expected_texts = [s["text"] for s in sentences]
    actual_texts = [caption.text for part in parts for caption in part.captions]

    assert actual_texts == expected_texts


def test_cau_dai_hon_ngan_sach_van_ra_dung_mot_phan_khong_treo():
    long_sentence = _sentence(1, 1, 0.0, MAX_PART_SECONDS + 50.0, text="câu siêu dài")
    normal_sentence = _sentence(1, 2, MAX_PART_SECONDS + 50.0, MAX_PART_SECONDS + 55.0)
    metadata = _metadata([long_sentence, normal_sentence], [_chapter(1, "Chương 1")])

    parts = plan_parts(metadata)

    assert len(parts) == 2
    assert parts[0].captions[0].text == "câu siêu dài"
    assert parts[0].duration_seconds == pytest.approx(MAX_PART_SECONDS + 50.0)
    assert parts[1].captions[0].text == "Câu 1.2"


def test_thieu_mang_sentences_thi_bao_loi():
    metadata = {"trope": "t", "title": "T", "sample_rate": 24000, "chapters": []}

    with pytest.raises(ShortPlanError, match="stage 2"):
        plan_parts(metadata)


def test_mang_sentences_rong_thi_bao_loi():
    metadata = _metadata([], [_chapter(1, "Chương 1")])

    with pytest.raises(ShortPlanError, match="stage 2"):
        plan_parts(metadata)


def test_cau_co_end_nho_hon_bang_start_thi_bao_loi():
    sentences = [_sentence(1, 1, 5.0, 5.0)]
    metadata = _metadata(sentences, [_chapter(1, "Chương 1")])

    with pytest.raises(ShortPlanError):
        plan_parts(metadata)


def test_cau_trong_chuong_khong_tang_dan_thoi_gian_thi_bao_loi():
    sentences = [
        _sentence(1, 1, 5.0, 8.0),
        _sentence(1, 2, 3.0, 6.0),  # lùi lại so với câu trước
    ]
    metadata = _metadata(sentences, [_chapter(1, "Chương 1")])

    with pytest.raises(ShortPlanError):
        plan_parts(metadata)


def test_quy_mo_thuc_te_mot_tap_50_phut_ra_so_phan_hop_ly():
    # 16 chương, mỗi chương 10-20 câu, câu dài trung bình ~11-13s (gần với văn
    # nói tiếng Việt đọc chậm) -> tổng gần ~50 phút giống một tập thật.
    import random

    rng = random.Random(42)
    sentences = []
    chapters = []
    for chapter_index in range(1, 17):
        chapters.append(_chapter(chapter_index, f"Chương {chapter_index}"))
        count = rng.randint(10, 20)
        t = 0.0
        for i in range(1, count + 1):
            dur = rng.uniform(8.0, 16.0)
            sentences.append(_sentence(chapter_index, i, t, t + dur))
            t += dur

    metadata = _metadata(sentences, chapters)
    total_seconds = sum(s["end_seconds"] - s["start_seconds"] for s in sentences)

    parts = plan_parts(metadata)

    assert 45 * 60 <= total_seconds <= 55 * 60
    assert 20 <= len(parts) <= 35


def test_chuong_thieu_trong_mang_chapters_thi_bao_loi():
    # Hai mảng lệch nhau là dấu hiệu metadata hỏng. Trả heading rỗng thì short ra
    # đời với hook trống mà không ai biết — thà dừng lại và nói rõ.
    metadata = {
        "chapters": [{"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": 5.0}],
        "sentences": [
            {"chapter_index": 1, "index": 1, "text": "Câu một.", "start_seconds": 0.0, "end_seconds": 5.0},
            {"chapter_index": 2, "index": 1, "text": "Câu hai.", "start_seconds": 5.5, "end_seconds": 9.0},
        ],
    }

    with pytest.raises(ShortPlanError, match="chương 2"):
        plan_parts(metadata)


def test_chuong_dai_chia_deu_khong_de_lai_mau_vun():
    # Kiểu tham lam "nhồi đầy 165s rồi mở lô mới" cho ra 160s + 30s: một short tử
    # tế kèm một mẩu gần như chỉ có card hook và card CTA. Phải chia đều.
    sentences = []
    t = 0.0
    for i in range(1, 39):  # 38 câu x 5s = 190s
        sentences.append({
            "chapter_index": 1, "index": i, "text": f"Câu {i}.",
            "start_seconds": t, "end_seconds": t + 5.0,
        })
        t += 5.0
    metadata = {
        "chapters": [{"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": t}],
        "sentences": sentences,
    }

    parts = plan_parts(metadata)

    assert len(parts) == 2
    durations = [p.duration_seconds for p in parts]
    assert all(d <= MAX_PART_SECONDS for d in durations)
    # Hai phần không được lệch nhau quá 20% — đây mới là điều test cũ bỏ sót.
    assert max(durations) - min(durations) <= 0.2 * max(durations), durations


# --- Trích đoạn: 5 short rải đều cả tập, dùng để kéo người xem về video dài ---


def _episode(chapter_count: int = 16, sentences_per_chapter: int = 60,
             sentence_seconds: float = 3.0, chapter_gap: float = 0.5) -> dict:
    """Tập nhiều chương trên MỘT trục thời gian liên tục, giống metadata thật."""
    sentences: list[dict] = []
    chapters: list[dict] = []
    t = 0.0
    for c in range(1, chapter_count + 1):
        chapter_start = t
        for i in range(1, sentences_per_chapter + 1):
            sentences.append(_sentence(c, i, t, t + sentence_seconds))
            t += sentence_seconds
        chapters.append(
            {"index": c, "heading": f"Chương {c}",
             "start_seconds": chapter_start, "end_seconds": t}
        )
        t += chapter_gap
    return _metadata(sentences, chapters)


def test_plan_teasers_tra_dung_5_phan_danh_so_lai_tu_1():
    teasers = plan_teasers(_episode())

    assert len(teasers) == TEASER_COUNT
    assert [t.number for t in teasers] == list(range(1, TEASER_COUNT + 1))


def test_plan_teasers_rai_deu_ca_tap_theo_dung_moc_mong_muon():
    metadata = _episode()
    episode_end = metadata["sentences"][-1]["end_seconds"]

    teasers = plan_teasers(metadata)

    # Mỗi trích đoạn phải nằm gần mốc của nó; sai số cho phép nửa khoảng cách
    # giữa hai mốc liền nhau, đủ rộng để không phụ thuộc cách chia phần.
    from shorts.planner import _teaser_fractions

    fractions = _teaser_fractions(TEASER_COUNT)
    tolerance = (fractions[1] - fractions[0]) / 2 * episode_end
    for teaser, fraction in zip(teasers, fractions):
        midpoint = (teaser.source_start_seconds + teaser.source_end_seconds) / 2
        assert abs(midpoint - fraction * episode_end) <= tolerance, (
            f"trích đoạn {teaser.number} ở {midpoint:.0f}s, lệch quá xa mốc "
            f"{fraction:.0%} ({fraction * episode_end:.0f}s)"
        )


def test_plan_teasers_theo_thu_tu_thoi_gian_va_khong_trung_nhau():
    teasers = plan_teasers(_episode())

    starts = [t.source_start_seconds for t in teasers]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)


def test_plan_teasers_khong_bao_gio_lay_doan_ket_thuc_tap():
    # Mốc cuối 85%: cố ý chừa đoạn kết để short không tiết lộ cái kết.
    metadata = _episode()
    episode_end = metadata["sentences"][-1]["end_seconds"]

    teasers = plan_teasers(metadata)

    assert teasers[-1].source_end_seconds < episode_end


def test_plan_teasers_tap_it_phan_hon_5_thi_lay_het():
    # Tập ngắn chia được ít phần hơn TEASER_COUNT: trả hết, không bịa thêm.
    metadata = _episode(chapter_count=1, sentences_per_chapter=8)
    assert len(plan_parts(metadata)) < TEASER_COUNT

    teasers = plan_teasers(metadata)

    assert len(teasers) == len(plan_parts(metadata))
    assert [t.number for t in teasers] == list(range(1, len(teasers) + 1))


def test_plan_teasers_giu_nguyen_moc_caption_quy_ve_goc_phan():
    teasers = plan_teasers(_episode())

    for teaser in teasers:
        assert teaser.captions[0].start_seconds == 0.0
        assert teaser.captions[-1].end_seconds <= teaser.duration_seconds + 0.01
