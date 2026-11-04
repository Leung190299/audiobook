# tests/scripts/test_story_bank_real.py
"""Kiểm trên KHO THẬT (data/story_bank.json) đúng các mốc spec 24/09 §7 nêu.

Test ở đây cố ý không dựng kho giả: chúng bảo vệ chính dữ liệu biên tập — nếu
ai sửa publish_date hay topic trong kho mà quên hậu quả, test đỏ ngay.
"""
from datetime import date

import pytest

from scripts import story_bank
from scripts.story_bank import DEFAULT_BANK_PATH, in_tet_window, load_bank, pick_story


@pytest.fixture
def state(tmp_path):
    """State rỗng trong tmp: không đụng output/story_bank_state.json thật."""
    return tmp_path / "state.json"


def test_kho_that_dung_113_truyen_va_topic_khop_registry():
    from scripts.topics import TOPICS

    bank = load_bank()

    assert len(bank.stories) == 113
    assert {s.topic for s in bank.stories} <= set(TOPICS)


def test_moi_tu_khoa_thumbnail_la_chuoi_con_cua_tieu_de():
    # Stage 5 báo lỗi nếu không khớp -> kho phải sạch từ đầu.
    bank = load_bank()

    sai = [(s.id, k) for s in bank.stories for k in s.thumb_keywords if k not in s.title]

    assert sai == []


def test_28_09_ra_truyen_da_hen_dung_ngay(state):
    s = pick_story(date(2026, 9, 28), state_path=state)

    assert s is not None
    assert s.publish_date == date(2026, 9, 28)


def test_16_10_ra_truyen_70(state):
    # Mốc spec nêu đích danh.
    s = pick_story(date(2026, 10, 16), state_path=state)

    assert s is not None and s.id == 70


def test_10_01_2027_nam_trong_mua_tet(state):
    assert in_tet_window(date(2027, 1, 10))
    assert pick_story(date(2027, 1, 10), state_path=state) is not None


def test_truyen_tet_khong_bao_gio_ra_ngoai_mua(state):
    bank = load_bank()
    tet_ids = {s.id for s in bank.stories if story_bank.TET_TIMING_MARK in (s.timing or "")}
    assert tet_ids, "kho phải có truyện gắn nhãn Trước Tết"

    # Quét 60 ngày ngoài mùa Tết: không ngày nào được chọn truyện Tết.
    ra = {
        s.id
        for _, s in story_bank.pick_upcoming(date(2026, 10, 1), days=60, state_path=state)
        if s is not None
    }

    assert ra & tet_ids == set()


def test_kho_that_du_truyen_cho_hon_hai_thang(state):
    lich = story_bank.pick_upcoming(date(2026, 9, 28), days=60, state_path=state)

    assert all(s is not None for _, s in lich)
    assert len({s.id for _, s in lich}) == 60  # không lặp truyện nào


def test_moi_truyen_co_hook_premise_va_cau_hoi():
    thieu = [
        s.id
        for s in load_bank().stories
        if not (s.hook.strip() and s.premise.strip() and s.comment_question.strip())
    ]

    assert thieu == []


def test_duong_dan_kho_mac_dinh_ton_tai():
    assert DEFAULT_BANK_PATH.exists()


async def test_stage_1_truyen_that_co_outline_ra_dung_16_chuong_va_hook_dau(monkeypatch):
    """Spec §7: truyện có outline -> đúng số chương của outline, câu đầu = hook."""
    from unittest.mock import AsyncMock, MagicMock

    from scripts.generator import generate_script

    monkeypatch.setattr("scripts.generator.RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr("scripts.generator.MIN_CHAPTER_WORDS", 0)

    bank = load_bank()
    story = next(s for s in bank.stories if len(s.outline) == 16)

    chapters_json = ", ".join(
        f'{{"heading": "C{i}", "summary": "s{i}"}}' for i in range(1, 17)
    )
    outline_json = f'{{"title": "khac", "short_beats": ["a","b","c"], "chapters": [{chapters_json}]}}'
    responses = [MagicMock(text=outline_json)] + [
        MagicMock(text=f"Nội dung chương {i}.") for i in range(1, 17)
    ]
    chat = MagicMock()
    chat.send_message = AsyncMock(side_effect=responses)
    client = MagicMock()
    client.start_chat.return_value = chat

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=story, bank=bank)

    assert len(script.chapters) == 16
    # Tên chương lấy của Gemini, KHÔNG phải nguyên dòng dàn ý: dòng dàn ý là ghi
    # chú nội bộ, mà heading thì hiện trên khung hình và trong mô tả YouTube.
    assert [c.heading for c in script.chapters] == [f"C{i}" for i in range(1, 17)]
    # Nội dung vẫn bám đúng dòng dàn ý theo thứ tự.
    prompts = [str(c.args[0]) for c in chat.send_message.await_args_list]
    for i, line in enumerate(story.outline):
        assert line in prompts[i + 1], f"chương {i + 1} không bám dòng {i + 1}"
    assert script.chapters[0].text.startswith(story.hook)
    assert script.title == story.title


def test_truyen_hoc_duong_co_luat_cam_rieng_trong_prompt():
    """Series Lớp 11A2 có nhân vật vị thành niên: dàn ý (nhánh kho) phải mang
    điều cấm riêng của chủ đề, không chỉ luật viết chung."""
    from scripts.prompts import build_story_outline_prompt
    from scripts.story_bank import get_story

    prompt = build_story_outline_prompt(load_bank(), get_story(109), "full")
    assert "TUYỆT ĐỐI KHÔNG: yêu đương" in prompt
    assert "Minh Anh (tôi)" in prompt  # khối series được chèn


def test_truyen_cu_khong_doi_prompt_vi_chu_de_moi():
    from scripts.prompts import build_story_outline_prompt
    from scripts.story_bank import get_story

    assert "- TUYỆT ĐỐI KHÔNG:" not in build_story_outline_prompt(load_bank(), get_story(1), "full")
