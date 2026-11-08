# tests/scripts/test_story_mode.py
"""Stage 1 khi truyện đến từ kho (`data/story_bank.json`).

Khác nhánh --topic: tiêu đề, hook, câu hỏi bình luận và từ khoá thumbnail do
người biên tập quyết, Gemini chỉ viết chương. Không kiểm tra trùng tiêu đề.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.generator import generate_script
from scripts.prompts import build_story_outline_prompt
from scripts.story_bank import Bank, Story

STORY = Story(
    id=7,
    topic="ho_hang_viet",
    series="Nhà Họ Trần",
    title="Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn",
    premise="Thảo về quê giỗ, bác Cả đòi chia đất.",
    twist="Thảo mở điện thoại livestream giữa mâm cơm.",
    hook="Bác Cả vừa đặt chén xuống, tôi bấm nút phát trực tiếp.",
    comment_question="Nhà bạn có ai như bác Cả không?",
    thumb_keywords=("Livestream Luôn",),
    timing="Quanh năm",
    priority="A",
    publish_date=None,
)

BANK = Bank(
    writing_rules=["Ngôi 'tôi'; không chào hỏi."],
    series={"Nhà Họ Trần": {"topic": "ho_hang_viet", "narrator": "Thảo, kế toán",
                            "cast": {"Bác Cả": "sĩ diện"}, "setting": "quê"}},
    stories=[STORY],
)

OUTLINE_JSON = (
    '{"title": "Gemini Tự Đặt Tiêu Đề Khác", "premise": "gemini premise",'
    ' "thumb_text": "Gemini Thumb", "thumb_keywords": ["Gemini"],'
    ' "hook": "gemini hook", "comment_question": "gemini hỏi gì đó?",'
    ' "short_beats": ["b1", "b2", "b3"], "chapters": [%s]}'
)


def _outline(n: int) -> str:
    return OUTLINE_JSON % ", ".join(
        f'{{"heading": "Chương {i}", "summary": "tóm tắt {i}"}}' for i in range(1, n + 1)
    )


def _beats_from(chapter_texts: list[str]) -> str:
    """Trả lời short_beats mặc định: 3 câu đầu tiên có thật trong các chương
    (08/11: stage 1 ép đủ 3 đoạn khớp nguyên văn, thiếu là lỗi)."""
    import json

    from scripts.text_tools import split_sentences

    sentences = [t for c in chapter_texts for t in split_sentences(c)]
    return json.dumps({"short_beats": sentences[:3]}, ensure_ascii=False)


def _client(outline_text: str, chapter_texts: list[str], beats_text: str | None = None):
    responses = [MagicMock(text=outline_text)] + [MagicMock(text=t) for t in chapter_texts]
    if beats_text is None:
        beats_text = _beats_from(chapter_texts)
    responses.append(MagicMock(text=beats_text))
    chat = MagicMock()
    chat.send_message = AsyncMock(side_effect=responses)
    client = MagicMock()
    client.start_chat.return_value = chat
    return client, chat


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch):
    monkeypatch.setattr("scripts.generator.RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr("scripts.generator.MIN_CHAPTER_WORDS", 0)


# --- prompt ---


def test_prompt_co_luat_viet_khoi_series_premise_twist_hook():
    p = build_story_outline_prompt(BANK, STORY, fmt="full")

    assert "Ngôi 'tôi'; không chào hỏi." in p
    assert "Nhà Họ Trần" in p and "Thảo, kế toán" in p and "Bác Cả" in p
    assert STORY.premise in p
    assert STORY.twist in p
    assert STORY.hook in p
    assert STORY.title in p


def test_prompt_truyen_le_khong_co_khoi_series():
    le = Story(**{**STORY.__dict__, "series": "Truyện lẻ"})

    p = build_story_outline_prompt(BANK, le, fmt="full")

    assert "Thảo, kế toán" not in p


def test_prompt_co_outline_thi_yeu_cau_bam_dung_dan_y():
    co = Story(**{**STORY.__dict__, "outline": ("Chương 1: mở", "Chương 2: đóng")})

    p = build_story_outline_prompt(BANK, co, fmt="full")

    assert "Chương 1: mở" in p and "Chương 2: đóng" in p


# --- generate_script ---


async def test_giu_nguyen_tieu_de_hook_cau_hoi_tu_kho_khong_lay_cua_gemini():
    client, _ = _client(_outline(2), ["Nội dung chương một. Bác Cả im bặt.", "Nội dung chương hai."])

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=STORY, bank=BANK)

    assert script.title == STORY.title
    assert script.comment_question == STORY.comment_question
    assert script.thumb_keywords == list(STORY.thumb_keywords)
    assert script.thumb_text == STORY.title
    assert script.premise == STORY.premise
    assert script.topic == STORY.topic


async def test_cau_dau_chuong_1_la_hook_nguyen_van():
    client, _ = _client(_outline(2), ["Gemini quên mất hook. Rồi kể tiếp chuyện.", "Chương hai."])

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=STORY, bank=BANK)

    assert script.chapters[0].text.startswith(STORY.hook)


# Dấu hiệu CHỈ có trong prompt dàn ý chế độ kho. Không dùng chữ "dàn ý": prompt
# viết từng chương cũng có chữ đó, đếm ra 3 thay vì 1.
OUTLINE_MARKER = "TIÊU ĐỀ (cố định"


def _assert_no_dup_check(chat):
    """Chế độ kho không hỏi lại dàn ý vì trùng tiêu đề: đúng 1 lượt dàn ý."""
    outline_calls = [
        c for c in chat.send_message.await_args_list if OUTLINE_MARKER in str(c.args[0])
    ]
    assert len(outline_calls) == 1, f"có {len(outline_calls)} lượt hỏi dàn ý"


async def test_khong_kiem_tra_trung_tieu_de():
    client, chat = _client(_outline(2), ["Chương một. Có thêm câu.", "Chương hai."])
    called = []

    await generate_script("x", "y", "z", client=client, fmt="full", story=STORY,
                          bank=BANK,
                          is_duplicate=lambda t, p: called.append((t, p)) or True)

    # is_duplicate có truyền vào cũng không được gọi ở chế độ kho.
    assert called == []
    _assert_no_dup_check(chat)


async def test_co_outline_thi_so_chuong_bang_so_dong_va_dung_thu_tu():
    co = Story(**{**STORY.__dict__,
                  "outline": ("Bố mất, cả họ về", "Bác Cả đòi đất", "Thảo livestream")})
    client, chat = _client(_outline(3), ["Một.", "Hai.", "Ba."])

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=co, bank=BANK)

    assert len(script.chapters) == 3
    # Dòng dàn ý điều khiển NỘI DUNG chương, theo đúng thứ tự.
    prompts = [str(c.args[0]) for c in chat.send_message.await_args_list]
    for i, line in enumerate(co.outline):
        assert line in prompts[i + 1], f"chương {i + 1} không bám dòng {i + 1}"


async def test_ten_chuong_khong_lay_nguyen_dong_dan_y():
    """Dòng dàn ý là ghi chú nội bộ cho người viết.

    Heading vừa bị đốt lên khung hình (MainVideo.tsx) vừa thành mốc chương
    trong mô tả YouTube. Ngày 25/09 video #2 hiện nguyên câu "Miếng hài: bác
    Cả tự đo đất bằng bước chân" cho người xem. Tên chương phải lấy của
    Gemini, dòng dàn ý chỉ dùng để chỉ đạo nội dung.
    """
    co = Story(**{**STORY.__dict__, "outline": (
        "Lai lịch mảnh đất 120m². Miếng hài: bác Cả tự đo đất bằng bước chân.",
        "Bác Cả leo thang. Cliffhanger: đòi họp gia đình Chủ nhật tới.",
    )})
    client, _ = _client(_outline(2), ["Một. Thêm câu nữa.", "Hai."])

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=co, bank=BANK)

    headings = [c.heading for c in script.chapters]
    assert headings == ["Chương 1", "Chương 2"]  # do _outline() sinh ra
    for h in headings:
        assert "Miếng hài" not in h and "Cliffhanger" not in h


async def test_khong_co_outline_thi_dung_dan_y_cua_gemini():
    client, _ = _client(_outline(4), ["M.", "H.", "B.", "T."])

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=STORY, bank=BANK)

    assert [c.heading for c in script.chapters] == [f"Chương {i}" for i in range(1, 5)]


async def test_short_beats_van_hoi_nguyen_van_nhu_nhanh_chu_de():
    # Kho không có short_beats; stage 4/7 cần NGUYÊN VĂN để dò mốc thời gian,
    # nên chế độ kho vẫn chạy bước hỏi lại như nhánh --topic.
    beats_json = '{"short_beats": ["Bác Cả im bặt.", "Cả mâm quay sang tôi.", "Tôi cười."]}'
    client, _ = _client(
        _outline(2),
        ["Bác Cả im bặt. Không ai nói gì.", "Cả mâm quay sang tôi. Tôi cười."],
        beats_json,
    )

    script = await generate_script("x", "y", "z", client=client, fmt="full",
                                   story=STORY, bank=BANK)

    assert script.short_beats == ["Bác Cả im bặt.", "Cả mâm quay sang tôi.", "Tôi cười."]


# --- scripts/cli.py --story ---


async def test_cli_story_in_chu_de_va_ghi_history_nhung_khong_chan_trung(
    tmp_path, monkeypatch, capsys
):
    """Spec §3: title giữ nguyên, KHÔNG kiểm tra trùng, nhưng vẫn ghi premise
    vào history để nhánh --topic sau này biết truyện đã kể."""
    from scripts import cli
    from scripts.models import Chapter, Script

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "scripts")
    monkeypatch.setattr(cli, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(cli, "validate_script", lambda s: None)
    monkeypatch.setattr(cli.story_bank, "get_story", lambda sid: STORY)
    monkeypatch.setattr(cli.story_bank, "load_bank", lambda: BANK)

    seen = {}

    async def fake_generate(*a, **kw):
        seen.update(kw)
        return Script(trope="ho_hang_viet", title=STORY.title, topic=STORY.topic,
                      premise=STORY.premise, format="full",
                      chapters=[Chapter(index=1, heading="C1", text="x")])

    monkeypatch.setattr(cli, "generate_script", fake_generate)

    await cli._run(None, None, None, None, fmt="full", story_arg="7")

    assert seen["story"] is STORY and seen["bank"] is BANK
    assert seen.get("is_duplicate") is None
    out = capsys.readouterr().out
    assert "Chủ đề: ho_hang_viet" in out  # run_daily đọc dòng này
    assert "Truyện: #7" in out
    from scripts import history

    entries = history.load_history(tmp_path / "history.json")
    assert entries[-1]["premise"] == STORY.premise
    assert entries[-1]["topic"] == STORY.topic
