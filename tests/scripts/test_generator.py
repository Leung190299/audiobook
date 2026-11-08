# tests/scripts/test_generator.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.generator import (
    CHAPTER_ATTEMPTS,
    OUTLINE_ATTEMPTS,
    ScriptGenerationError,
    generate_script,
)


def _outline_json(num_chapters: int) -> str:
    chapters = ", ".join(
        f'{{"heading": "Chương {i}", "summary": "Tóm tắt chương {i}."}}'
        for i in range(1, num_chapters + 1)
    )
    return f'{{"title": "Tiêu đề test", "chapters": [{chapters}]}}'


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Bỏ khoảng chờ giữa các lần thử lại: nó có ích khi chạy thật, nhưng làm bộ
    test chậm gấp trăm lần mà không kiểm chứng thêm điều gì."""
    monkeypatch.setattr("scripts.generator.RETRY_DELAY_SECONDS", 0)
    # Sàn độ dài chương chỉ có nghĩa với văn thật; các test ở đây dùng chương
    # vài chữ, nên tắt sàn — test riêng cho sàn tự đặt lại giá trị.
    monkeypatch.setattr("scripts.generator.MIN_CHAPTER_WORDS", 0)


def _make_fake_client(
    outline_text: str, chapter_texts: list[str], outline_repeats: int = 1
):
    # outline_repeats > 1 cho các test cố tình đưa dàn ý hỏng: generate_script hỏi lại
    # tới OUTLINE_ATTEMPTS lần, cấp thiếu phản hồi thì test chết vì hết side_effect
    # chứ không phải vì lý do nó muốn kiểm tra.
    responses = [MagicMock(text=outline_text)] * outline_repeats + [
        MagicMock(text=t) for t in chapter_texts
    ]
    fake_chat = MagicMock()
    fake_chat.send_message = AsyncMock(side_effect=responses)
    fake_client = MagicMock()
    fake_client.start_chat.return_value = fake_chat
    return fake_client, fake_chat


async def test_generate_script_builds_script_from_outline_and_chapters():
    outline_text = _outline_json(8)
    chapter_texts = [f"Nội dung đầy đủ chương {i}." for i in range(1, 9)]
    fake_client, fake_chat = _make_fake_client(outline_text, chapter_texts)

    script = await generate_script(
        trope_id="trong_sinh_bao_thu",
        trope_name="Trọng sinh báo thù",
        trope_description="Mô tả test.",
        client=fake_client,
    )

    assert script.title == "Tiêu đề test"
    assert script.trope == "trong_sinh_bao_thu"
    assert len(script.chapters) == 8
    assert script.chapters[0].index == 1
    assert script.chapters[0].heading == "Chương 1"
    assert script.chapters[0].text == "Nội dung đầy đủ chương 1."
    assert script.chapters[7].index == 8
    assert script.chapters[7].heading == "Chương 8"
    assert fake_chat.send_message.call_count == 9  # 1 outline + 8 chapters
    fake_client.start_chat.assert_called_once()


async def test_generate_script_strips_markdown_fence_from_outline():
    outline_text = "```json\n" + _outline_json(2) + "\n```"
    chapter_texts = ["Nội dung chương 1.", "Nội dung chương 2."]
    fake_client, _ = _make_fake_client(outline_text, chapter_texts)

    script = await generate_script("id", "name", "desc", client=fake_client)

    assert script.title == "Tiêu đề test"
    assert len(script.chapters) == 2


async def test_generate_script_raises_on_invalid_outline_json():
    fake_client, _ = _make_fake_client(
        "Xin lỗi, tôi không thể giúp việc này.", [], outline_repeats=OUTLINE_ATTEMPTS
    )

    with pytest.raises(ScriptGenerationError):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_raises_on_missing_outline_fields():
    fake_client, _ = _make_fake_client('{"title": "Thiếu chapters"}', [])

    with pytest.raises(ScriptGenerationError):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_error_includes_raw_response_on_structure_mismatch():
    fake_client, _ = _make_fake_client(
        '{"title": "T", "chapters": [["not", "a dict"]]}', []
    )

    with pytest.raises(ScriptGenerationError, match="Phản hồi thô"):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_wraps_api_error_from_outline():
    fake_chat = MagicMock()
    fake_chat.send_message = AsyncMock(side_effect=APIError("boom"))
    fake_client = MagicMock()
    fake_client.start_chat.return_value = fake_chat

    with pytest.raises(ScriptGenerationError, match="dàn ý"):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_wraps_api_error_from_chapter():
    outline_text = _outline_json(2)
    fake_chat = MagicMock()
    fake_chat.send_message = AsyncMock(
        side_effect=[MagicMock(text=outline_text), APIError("boom mid-chapter")]
    )
    fake_client = MagicMock()
    fake_client.start_chat.return_value = fake_chat

    with pytest.raises(ScriptGenerationError, match="chương 1"):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_dan_y_json_hong_thi_hoi_lai_gemini():
    # Gemini trả JSON hỏng ở lần đầu (nháy kép không escape trong summary), lần hai
    # trả đúng. Hỏng ở đây là mất trắng cả lượt chạy, nên phải thử lại chứ không
    # được ném ngay.
    hong = MagicMock()
    hong.text = '{"title": "T", "chapters": [{"heading": "A", "summary": "có "nháy" lọt"}]}'
    tot = MagicMock()
    tot.text = '{"title": "T", "chapters": [{"heading": "A", "summary": "sạch"}]}'
    chuong = MagicMock()
    chuong.text = "Nội dung chương."

    chat = MagicMock()
    chat.send_message = AsyncMock(side_effect=[hong, tot, chuong])
    client = MagicMock()
    client.start_chat = MagicMock(return_value=chat)

    script = await generate_script("t", "Tên", "Mô tả", client=client)

    assert script.title == "T"
    assert len(script.chapters) == 1
    # 2 lần cho dàn ý + 1 lần cho chương.
    assert chat.send_message.await_count == 3


async def test_dan_y_hong_lien_tuc_thi_bao_loi():
    hong = MagicMock()
    hong.text = "{ hỏng hoàn toàn"

    chat = MagicMock()
    chat.send_message = AsyncMock(return_value=hong)
    client = MagicMock()
    client.start_chat = MagicMock(return_value=chat)

    with pytest.raises(ScriptGenerationError, match="Không parse được JSON"):
        await generate_script("t", "Tên", "Mô tả", client=client)

    assert chat.send_message.await_count == OUTLINE_ATTEMPTS


async def test_gemini_tu_choi_thi_bao_dung_loai_loi():
    # Từ chối trả văn bản thường, không phải JSON hỏng. Thông báo cũ nói "không
    # parse được JSON" khiến người sửa đi vá nhầm chỗ.
    tu_choi = MagicMock()
    tu_choi.text = "Là một mô hình ngôn ngữ, tôi không được thiết kế để trợ giúp về điều đó."

    chat = MagicMock()
    chat.send_message = AsyncMock(return_value=tu_choi)
    client = MagicMock()
    client.start_chat = MagicMock(return_value=chat)

    with pytest.raises(ScriptGenerationError, match="từ chối nội dung"):
        await generate_script("t", "Tên", "Mô tả", client=client)


REFUSAL = "Tôi không thể giúp bạn việc đó, vì tôi chỉ là một mô hình ngôn ngữ."


async def test_chuong_bi_tu_choi_thi_hoi_lai_va_lay_ban_sau():
    # Tập 05/09 thật: chương 4 là nguyên văn lời từ chối của Gemini, 29 từ, và
    # đi thẳng vào TTS. Chương từ chối phải bị hỏi lại, không được nhận.
    outline_text = _outline_json(2)
    fake_client, fake_chat = _make_fake_client(
        outline_text, ["Chương một thật.", REFUSAL, "Chương hai thật."]
    )

    script = await generate_script("t", "T", "mô tả", client=fake_client)

    assert [c.text for c in script.chapters] == ["Chương một thật.", "Chương hai thật."]
    assert fake_chat.send_message.await_count == 1 + 3  # dàn ý + 3 lượt chương


async def test_chuong_tu_choi_het_luot_thi_nem_loi_neu_so_chuong():
    outline_text = _outline_json(2)
    fake_client, fake_chat = _make_fake_client(
        outline_text, ["Chương một thật."] + [REFUSAL] * CHAPTER_ATTEMPTS
    )

    with pytest.raises(ScriptGenerationError, match="chương 2"):
        await generate_script("t", "T", "mô tả", client=fake_client)

    assert fake_chat.send_message.await_count == 1 + 1 + CHAPTER_ATTEMPTS


async def test_chuong_qua_ngan_cung_bi_hoi_lai(monkeypatch):
    monkeypatch.setattr("scripts.generator.MIN_CHAPTER_WORDS", 5)
    outline_text = _outline_json(1)
    fake_client, _ = _make_fake_client(
        outline_text, ["Cụt lủn.", "Một chương đủ năm từ trở lên đây."]
    )

    script = await generate_script("t", "T", "mô tả", client=fake_client)

    assert script.chapters[0].text == "Một chương đủ năm từ trở lên đây."


async def test_dan_y_co_tieu_de_tuc_thi_hoi_lai_dan_y():
    # Tiêu đề tục coi như dàn ý hỏng: hỏi lại trong cùng chat, lấy bản sau.
    bad = '{"title": "Bà Chó Sủa Mỏ Hỗn", "chapters": [{"heading": "C1", "summary": "s"}]}'
    good = '{"title": "Mẹ Chồng Mỏ Hỗn", "chapters": [{"heading": "C1", "summary": "s"}]}'
    responses = [MagicMock(text=bad), MagicMock(text=good), MagicMock(text="Nội dung chương.")]
    fake_chat = MagicMock(); fake_chat.send_message = AsyncMock(side_effect=responses)
    fake_client = MagicMock(); fake_client.start_chat.return_value = fake_chat

    script = await generate_script("t", "T", "mô tả", client=fake_client)

    assert script.title == "Mẹ Chồng Mỏ Hỗn"
    assert fake_chat.send_message.await_count == 3


async def test_dan_y_co_hook_va_cau_hoi_thi_vao_script():
    outline_text = (
        '{"title": "Tiêu đề", "hook": "Cô bị tráo phôi ngay trong đêm cưới", '
        '"comment_question": "Bạn sẽ ký đơn hay tha thứ?", '
        '"chapters": [{"heading": "C1", "summary": "S1"}]}'
    )
    fake_client, _ = _make_fake_client(outline_text, ["Chương một."])

    script = await generate_script("t", "Tên", "Mô tả", client=fake_client)

    assert script.hook == "Cô bị tráo phôi ngay trong đêm cưới"
    assert script.comment_question == "Bạn sẽ ký đơn hay tha thứ?"


async def test_dan_y_thieu_hook_thi_khong_loi_va_hook_rong():
    fake_client, _ = _make_fake_client(_outline_json(1), ["Chương một."])
    script = await generate_script("t", "Tên", "Mô tả", client=fake_client)
    assert script.hook == ""
    assert script.comment_question == ""


async def test_hook_qua_dai_bi_cat_theo_so_tu():
    long_hook = " ".join(f"tu{i}" for i in range(40))
    outline_text = (
        f'{{"title": "T", "hook": "{long_hook}", "comment_question": "",'
        ' "chapters": [{"heading": "C1", "summary": "S1"}]}'
    )
    fake_client, _ = _make_fake_client(outline_text, ["Chương một."])
    script = await generate_script("t", "Tên", "Mô tả", client=fake_client)
    assert len(script.hook.split()) == 20


# --- nhánh chủ đề (24/09/2026) -------------------------------------------------

import json as _json

from scripts.topics import TOPICS


def _topic_outline(title="Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn", n=15, premise="P"):
    return _json.dumps(
        {
            "title": title,
            "premise": premise,
            "thumb_text": title,
            "thumb_keywords": ["Chia Đất", "không có"],
            "hook": "Hook",
            "comment_question": "Nếu là bạn, bạn có cho bác Cả mượn sổ đỏ không? 1 = cho, 2 = không",
            "short_beats": ["đoạn 1 ở chương 2", "đoạn 2", "đoạn 3"],
            "chapters": [{"heading": f"C{i}", "summary": "s"} for i in range(1, n + 1)],
        },
        ensure_ascii=False,
    )


def _topic_client(outlines, chapter_texts, *beats_texts):
    """beats_texts: một trả lời cho mỗi lượt hỏi short_beats (lượt đầu + hỏi lại)."""
    responses = [MagicMock(text=o) for o in outlines] + [MagicMock(text=t) for t in chapter_texts] + [
        MagicMock(text=b) for b in beats_texts
    ]
    chat = MagicMock()
    chat.send_message = AsyncMock(side_effect=responses)
    client = MagicMock()
    client.start_chat.return_value = chat
    return client, chat


async def test_chu_de_full_tra_them_truong_thumbnail_va_short_beats():
    chapters = [f"Chương {i} mở đầu. Bác Cả đập bàn đòi đất số {i}. Tôi bật livestream luôn." for i in range(1, 16)]
    beats = _json.dumps({"short_beats": ["Bác Cả đập bàn đòi đất số 2. Tôi bật livestream luôn.", "câu bịa hoàn toàn không có trong truyện nào cả"]}, ensure_ascii=False)
    # 08/11: thiếu 2 -> hỏi lại, lượt hai trả đủ phần còn thiếu.
    beats_2 = _json.dumps({"short_beats": ["Bác Cả đập bàn đòi đất số 5.", "Bác Cả đập bàn đòi đất số 9."]}, ensure_ascii=False)
    client, chat = _topic_client([_topic_outline()], chapters, beats, beats_2)
    script = await generate_script(
        "ho_hang_viet", "n", "Tết về quê", client=client,
        fmt="full", topic=TOPICS["ho_hang_viet"], setting="Tết về quê",
    )
    assert script.topic == "ho_hang_viet" and script.format == "full"
    assert script.setting == "Tết về quê" and script.premise == "P"
    assert script.thumb_keywords == ["Chia Đất"]
    assert "2 = không" in script.comment_question
    # Đoạn không dò được trong văn bản bị bỏ, phần thiếu lấy từ lượt hỏi lại.
    assert script.short_beats == [
        "Bác Cả đập bàn đòi đất số 2. Tôi bật livestream luôn.",
        "Bác Cả đập bàn đòi đất số 5.",
        "Bác Cả đập bàn đòi đất số 9.",
    ]
    retry_prompt = chat.send_message.call_args_list[-2].args[0]  # [-1] là prompt Mở đầu
    assert "ĐÚNG 2 đoạn KHÁC" in retry_prompt
    assert "Bác Cả đập bàn đòi đất số 2. Tôi bật livestream luôn." in retry_prompt  # đã nhận, không gửi lại
    assert "1 đoạn không khớp nguyên văn" in retry_prompt
    prompt = chat.send_message.call_args_list[0].args[0]
    assert "Tết về quê" in prompt and "cá mặn hậu cung" in prompt
    chapter_prompt = chat.send_message.call_args_list[1].args[0]
    assert "cliffhanger" not in chapter_prompt.lower()


async def test_chu_de_dan_y_trung_thi_hoi_lai():
    chapters = [f"Nội dung {i}." for i in range(1, 16)]
    client, chat = _topic_client(
        [_topic_outline(title="Cũ"), _topic_outline(title="Mới")], chapters,
        '{"short_beats": ["Nội dung 1.", "Nội dung 2.", "Nội dung 3."]}',
    )
    script = await generate_script(
        "ho_hang_viet", "n", "s", client=client, fmt="full", topic=TOPICS["ho_hang_viet"],
        setting="s", is_duplicate=lambda title, premise: title == "Cũ",
    )
    assert script.title == "Mới"
    assert "KHÔNG dùng được" in chat.send_message.call_args_list[1].args[0]


async def test_chu_de_tieu_de_dai_hon_60_ky_tu_thi_hoi_lai():
    long_title = "Tôi " + "Rất " * 30 + "Dài"
    chapters = [f"Nội dung {i}." for i in range(1, 16)]
    client, chat = _topic_client(
        [_topic_outline(title=long_title), _topic_outline(title="Ngắn Gọn")], chapters,
        '{"short_beats": ["Nội dung 1.", "Nội dung 2.", "Nội dung 3."]}',
    )
    script = await generate_script(
        "ho_hang_viet", "n", "s", client=client, fmt="full", topic=TOPICS["ho_hang_viet"], setting="s"
    )
    assert script.title == "Ngắn Gọn"
    assert len(script.short_beats) == 3


async def test_short_beats_thieu_sau_3_luot_hoi_thi_stage_1_loi():
    """08/11: kênh yêu cầu ép đủ 3 short_beats. Truyện #114 từng ra 2 Short vì
    Gemini trả thiếu mà bộ sinh cho qua. Giờ 3 lượt vẫn thiếu -> lỗi, không
    dựng 40 phút ra truyện thiếu Short."""
    from scripts.generator import ScriptGenerationError

    chapters = [f"Nội dung {i}." for i in range(1, 16)]
    client, chat = _topic_client(
        [_topic_outline()], chapters,
        "không phải json",
        '{"short_beats": ["Nội dung 4."]}',
        '{"short_beats": ["Nội dung 4.", "câu bịa không có trong truyện"]}',
    )

    with pytest.raises(ScriptGenerationError, match=r"1/3 short_beats"):
        await generate_script(
            "ho_hang_viet", "n", "s", client=client, fmt="full", topic=TOPICS["ho_hang_viet"], setting="s"
        )
    beats_prompts = [str(c.args[0]) for c in chat.send_message.call_args_list[-3:]]
    assert "Hãy chọn 3 đoạn" in beats_prompts[0]
    assert "không phải JSON" in beats_prompts[1] and "ĐÚNG 3 đoạn KHÁC" in beats_prompts[1]
    assert "ĐÚNG 2 đoạn KHÁC" in beats_prompts[2] and "Nội dung 4." in beats_prompts[2]


async def test_chuong_qua_dai_thi_viet_gon_va_nhac_chuong_sau(monkeypatch):
    """08/10: Claude viết 895-1.008 từ/chương dù prompt bảo tối đa 770."""
    monkeypatch.setattr("scripts.generator.chapter_words_range", lambda fmt: (10, 20))
    dai = " ".join(["chữ"] * 40)
    gon = " ".join(["gọn"] * 15)
    vua = " ".join(["vừa"] * 21)  # vượt trần nhưng dưới 1,15 lần: không viết lại
    fake_client, fake_chat = _make_fake_client(_outline_json(3), [dai, gon, vua, gon])

    script = await generate_script("t", "T", "m", client=fake_client)

    assert [c.text for c in script.chapters] == [gon, vua, gon]
    prompts = [call.args[0] for call in fake_chat.send_message.call_args_list]
    assert "Viết lại CHÍNH chương đó" in prompts[2]
    assert "LƯU Ý ĐỘ DÀI" not in prompts[3], "chương 1 sau khi viết gọn đã vừa"
    assert "dài 21 từ, VƯỢT trần 20" in prompts[4]


async def test_ban_full_co_chuong_mo_dau_ke_truoc_doan_gay_can():
    """26/10: truyện mở bằng đoạn gay cấn nhất rồi mới quay lại kể từ đầu.
    Viết SAU khi xong truyện để khớp cao trào; thành chương 1 'Mở đầu'."""
    from scripts.models import PROLOGUE_HEADING

    prologue = " ".join(["gay"] * 120) + " Nhưng để hiểu vì sao, phải kể lại từ đầu."
    chapters = [f"Nội dung chương {i}." for i in range(1, 4)]
    fake_client, fake_chat = _make_fake_client(_outline_json(3), chapters + [prologue])

    script = await generate_script("t", "T", "m", client=fake_client, fmt="full")

    assert [c.heading for c in script.chapters][0] == PROLOGUE_HEADING
    assert [c.index for c in script.chapters] == [1, 2, 3, 4]
    assert script.chapters[0].text == prologue
    assert script.chapters[1].text == "Nội dung chương 1."
    last_prompt = fake_chat.send_message.call_args_list[-1].args[0]
    assert "KHÔNG viết bất cứ điều gì xảy ra SAU khi bằng chứng được mở" in last_prompt


async def test_mo_dau_hong_thi_bo_qua_khong_lam_hong_truyen(capsys):
    chapters = [f"Nội dung chương {i}." for i in range(1, 4)]
    fake_client, _ = _make_fake_client(_outline_json(3), chapters + ["ngắn", "vẫn ngắn"])

    script = await generate_script("t", "T", "m", client=fake_client, fmt="full")

    assert len(script.chapters) == 3 and script.chapters[0].heading == "Chương 1"
    assert "CẢNH BÁO" in capsys.readouterr().out


async def test_ban_tap_khong_co_mo_dau():
    chapters = [f"Nội dung chương {i}." for i in range(1, 4)]
    fake_client, fake_chat = _make_fake_client(_outline_json(3), chapters)
    script = await generate_script("t", "T", "m", client=fake_client, fmt="episodes")
    assert fake_chat.send_message.call_count == 4 and len(script.chapters) == 3


# --- force_hook: câu đầu chương 1 (08/11/2026) ---------------------------------

from scripts.generator import force_hook

HOOK = "Giữa mâm cỗ giỗ bố, mẹ gõ đũa tuyên bố: 'Nhà này mẹ chỉ có thằng Đạt là con.'"


def test_force_hook_giu_nguyen_khi_da_mo_dung_hook():
    text = HOOK + "\n\nCả mâm im."
    assert force_hook(text, HOOK) == text


def test_force_hook_thay_cau_gan_giong_thay_vi_ghep_doi():
    text = (
        "Giữa mâm cỗ giỗ hết tang bố, mẹ gõ đũa tuyên bố: 'Nhà này mẹ chỉ có thằng Đạt là con.'"
        " Cả mâm cỗ khựng lại.\n\nMẹ hất hàm."
    )
    out = force_hook(text, HOOK)
    assert out.startswith(HOOK + " Cả mâm cỗ khựng lại.")
    assert out.count("mẹ gõ đũa tuyên bố") == 1
    assert out.endswith("\n\nMẹ hất hàm.")


def test_force_hook_ghep_len_truoc_khi_mo_bang_cau_dan_khac():
    text = "Hôm ấy trời mưa. Mẹ nhìn tôi.\n\nTôi im."
    assert force_hook(text, HOOK) == f"{HOOK} {text}"


def test_force_hook_hook_rong_khong_dong_den_van():
    assert force_hook("Văn.", "") == "Văn."
