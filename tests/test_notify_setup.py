"""Test cho notify/setup.py — phần ghi .env và dò chat id, không gọi mạng."""

import pytest

from notify.setup import SetupError, detect_chat_id, set_env_value


# --- ghi .env ----------------------------------------------------------------


def test_thay_gia_tri_key_dang_de_trong():
    content = "SECURE_1PSID=abc\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n"
    result = set_env_value(content, "TELEGRAM_BOT_TOKEN", "123:XYZ")
    assert "TELEGRAM_BOT_TOKEN=123:XYZ\n" in result
    # Không được đụng vào các dòng khác.
    assert "SECURE_1PSID=abc\n" in result
    assert "TELEGRAM_CHAT_ID=\n" in result


def test_thay_gia_tri_key_da_co_san():
    result = set_env_value("TELEGRAM_CHAT_ID=cu\n", "TELEGRAM_CHAT_ID", "moi")
    assert result == "TELEGRAM_CHAT_ID=moi\n"


def test_them_key_chua_ton_tai():
    result = set_env_value("SECURE_1PSID=abc\n", "TELEGRAM_CHAT_ID", "999")
    assert result == "SECURE_1PSID=abc\nTELEGRAM_CHAT_ID=999\n"


def test_them_key_khi_file_khong_ket_thuc_bang_xuong_dong():
    result = set_env_value("SECURE_1PSID=abc", "TELEGRAM_CHAT_ID", "999")
    assert result == "SECURE_1PSID=abc\nTELEGRAM_CHAT_ID=999\n"


def test_them_key_vao_file_rong():
    assert set_env_value("", "TELEGRAM_CHAT_ID", "999") == "TELEGRAM_CHAT_ID=999\n"


def test_giu_nguyen_comment_va_dong_trong():
    content = "# Cookie Gemini\nSECURE_1PSID=abc\n\n# Telegram\nTELEGRAM_CHAT_ID=\n"
    result = set_env_value(content, "TELEGRAM_CHAT_ID", "42")
    assert result == "# Cookie Gemini\nSECURE_1PSID=abc\n\n# Telegram\nTELEGRAM_CHAT_ID=42\n"


def test_khong_thay_nham_key_co_ten_la_hau_to_cua_key_khac():
    # "CHAT_ID" là hậu tố của "TELEGRAM_CHAT_ID" — regex neo ^ phải chặn nhầm lẫn này.
    content = "TELEGRAM_CHAT_ID=nguyen_ven\n"
    result = set_env_value(content, "CHAT_ID", "moi")
    assert "TELEGRAM_CHAT_ID=nguyen_ven\n" in result
    assert "CHAT_ID=moi\n" in result


# --- dò chat id --------------------------------------------------------------


def _patch_call(monkeypatch, response):
    import notify.setup as setup

    monkeypatch.setattr(setup, "_call", lambda token, method, params=None: response)


def test_do_duoc_chat_id_tu_tin_nhan_gan_nhat(monkeypatch):
    _patch_call(
        monkeypatch,
        {"ok": True, "result": [{"message": {"chat": {"id": 12345, "username": "lee"}}}]},
    )
    assert detect_chat_id("token") == ("12345", "lee")


def test_chua_nhan_tin_cho_bot_thi_huong_dan_ro_viec_can_lam(monkeypatch):
    _patch_call(monkeypatch, {"ok": True, "result": []})
    with pytest.raises(SetupError, match="bấm Start"):
        detect_chat_id("token")


def test_nhieu_cuoc_tro_chuyen_thi_bao_de_chon_tay(monkeypatch):
    _patch_call(
        monkeypatch,
        {
            "ok": True,
            "result": [
                {"message": {"chat": {"id": 1, "first_name": "Lee"}}},
                {"message": {"chat": {"id": 2, "title": "Nhóm kênh"}}},
            ],
        },
    )
    with pytest.raises(SetupError, match="nhiều hơn một"):
        detect_chat_id("token")


def test_bo_qua_update_khong_phai_tin_nhan(monkeypatch):
    _patch_call(
        monkeypatch,
        {
            "ok": True,
            "result": [
                {"edited_message": {"chat": {"id": 999}}},
                {"message": {"chat": {"id": 7, "username": "lee"}}},
            ],
        },
    )
    # edited_message không được tính, nếu không sẽ thành "nhiều cuộc trò chuyện" giả.
    assert detect_chat_id("token") == ("7", "lee")
