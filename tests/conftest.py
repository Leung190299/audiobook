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
