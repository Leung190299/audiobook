"""Chặn test gọi ra YouTube thật.

Ngày 01/10 một unit test của scripts/post_shorts.py đã gọi thẳng API thật: nó
monkeypatch `ps.METADATA_DIR` nhưng hàm lại gắn thư mục đó làm tham số mặc định
lúc import, nên patch không ăn và test đi quét output/metadata thật, tìm ra
truyện #41 rồi chạy tiếp tới bước chuẩn hoá short trên kênh. Lần đó may là mọi
short đã đúng sẵn nên không có lệnh ghi nào, nhưng không có gì bảo đảm lần sau
cũng may.

Test nào cần đối tượng YouTube thì tự truyền bản giả vào hàm.
"""

import pytest


class GoiYouTubeTrongTest(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _chan_goi_youtube(monkeypatch):
    def _no(*args, **kwargs):
        raise GoiYouTubeTrongTest(
            "Test vừa cố gọi YouTube thật. Hãy truyền một đối tượng yt giả vào "
            "hàm, hoặc monkeypatch _yt của module đang test."
        )

    for ten in ("scripts.catchup_shorts", "scripts.post_shorts"):
        try:
            mod = __import__(ten, fromlist=["x"])
        except ImportError:
            continue
        for thuoc_tinh in ("_yt", "load_credentials"):
            if hasattr(mod, thuoc_tinh):
                monkeypatch.setattr(mod, thuoc_tinh, _no)
    yield


@pytest.fixture(autouse=True)
def _khong_dung_video_nen_that(monkeypatch, tmp_path_factory):
    """assets/backgrounds/ chứa video thật (hàng trăm MB). Không chặn thì mọi
    test của stage 4 đều thấy chúng và cố chạy ffmpeg -- đúng chuyện xảy ra
    05/10 khi vừa chép video vào. Test nào cần thì tự truyền thư mục riêng."""
    try:
        from episodes import backgrounds
    except ImportError:
        yield
        return
    monkeypatch.setattr(backgrounds, "BACKGROUND_DIR", tmp_path_factory.mktemp("nen-trong"))
    yield


@pytest.fixture(autouse=True)
def _khong_dung_trang_thai_kho_that(monkeypatch, tmp_path_factory):
    """output/story_bank_state.json điều khiển lịch tự động 09:00: truyện nào đã
    dựng, đã đăng, tối nào đã có video. Test đọc nó thì kết quả phụ thuộc lịch
    kênh hôm đó; test GHI vào nó thì lượt chạy sáng mai chọn sai truyện. Kho
    biên tập (data/story_bank.json) chỉ đọc nên vẫn để test dùng bản thật."""
    from scripts import story_bank

    monkeypatch.setattr(
        story_bank, "DEFAULT_STATE_PATH", tmp_path_factory.mktemp("kho") / "state.json"
    )
    yield


class GoiMoHinhTrongTest(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _chan_goi_mo_hinh(monkeypatch):
    """.env có ANTHROPIC_API_KEY thật từ 08/10: test nào lỡ để generate_script
    tự tạo client là gọi Claude thật, mỗi lượt vài đô. Test nào cần thì truyền
    client giả (có start_chat) vào generate_script, hoặc ClaudeChat giả."""

    def _no(*args, **kwargs):
        raise GoiMoHinhTrongTest(
            "Test vừa cố gọi mô hình thật (Claude/Gemini). Truyền client giả vào hàm."
        )

    from scripts import generator, llm

    monkeypatch.setattr(generator, "make_client", _no)
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _no)
    yield
