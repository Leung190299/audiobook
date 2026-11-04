"""Test cho trend/sources.py và notify/dispatch.py — không gọi mạng thật."""

import gzip
import io
import xml.etree.ElementTree as ET

import pytest

from notify.dispatch import MACOS, NONE, TELEGRAM, resolve_channel
from notify.macos import _escape
from trend.sources import TrendConfig, _parse_titles, collect_signals, fetch_feed

RSS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Tam su</title>
  <item><title>Vo tinh thay vo nhan 50 trieu dong</title></item>
  <item><title>Me chong giau so do suot 10 nam</title></item>
  <item><title>   </title></item>
  <item><title>Chi dau lanh nhat vi chuyen rua bat</title></item>
</channel></rss>"""

ATOM_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Kenh truyen audio</title>
  <entry><title>Trong sinh bao thu nha chong</title></entry>
  <entry><title>Va mat ke phu bac</title></entry>
</feed>"""


# --- parse feed ---------------------------------------------------------------


def test_parse_rss_2_0_lay_dung_tieu_de():
    titles = _parse_titles(RSS_XML, limit=10)
    assert titles == [
        "Vo tinh thay vo nhan 50 trieu dong",
        "Me chong giau so do suot 10 nam",
        "Chi dau lanh nhat vi chuyen rua bat",
    ]


def test_parse_atom_cho_feed_youtube():
    # Feed kênh YouTube là Atom, không phải RSS 2.0 — namespace khác hẳn.
    assert _parse_titles(ATOM_XML, limit=10) == [
        "Trong sinh bao thu nha chong",
        "Va mat ke phu bac",
    ]


def test_parse_ton_trong_gioi_han_so_muc():
    assert len(_parse_titles(RSS_XML, limit=2)) == 2


def test_parse_feed_rong_tra_ve_danh_sach_rong():
    assert _parse_titles(b'<?xml version="1.0"?><rss><channel></channel></rss>', 10) == []


def test_xml_hong_thi_nem_parse_error():
    with pytest.raises(ET.ParseError):
        _parse_titles(b"<rss><channel><item>chua dong the", 10)


# --- gzip ---------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict):
        self._body, self.headers = body, headers

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _patch_urlopen(monkeypatch, body: bytes, headers: dict | None = None):
    import trend.sources as sources

    monkeypatch.setattr(
        sources.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(body, headers or {}),
    )


def test_giai_nen_gzip_theo_header(monkeypatch):
    # VnExpress trả gzip; không giải nén là ET.fromstring vỡ với lỗi khó hiểu.
    _patch_urlopen(monkeypatch, gzip.compress(RSS_XML), {"Content-Encoding": "gzip"})
    assert fetch_feed("https://vi-du/rss")[0] == "Vo tinh thay vo nhan 50 trieu dong"


def test_giai_nen_gzip_ca_khi_header_khong_khai_bao(monkeypatch):
    # Một số máy chủ gzip mà quên đặt header — nhận diện bằng magic bytes.
    _patch_urlopen(monkeypatch, gzip.compress(RSS_XML), {})
    assert len(fetch_feed("https://vi-du/rss")) == 3


def test_khong_gzip_van_doc_binh_thuong(monkeypatch):
    _patch_urlopen(monkeypatch, RSS_XML, {})
    assert len(fetch_feed("https://vi-du/rss")) == 3


# --- gom tín hiệu -------------------------------------------------------------


def test_mot_nguon_hong_khong_lam_hong_ca_luot(monkeypatch, tmp_path):
    import trend.sources as sources

    def fake_fetch(url, limit=25):
        if "hong" in url:
            raise OSError("máy chủ không phản hồi")
        return ["Tieu de A", "Tieu de B"]

    monkeypatch.setattr(sources, "fetch_feed", fake_fetch)

    config = TrendConfig(
        use_google_trends=False,
        feeds=[
            sources.Feed(name="Nguồn tốt", url="https://tot/rss"),
            sources.Feed(name="Nguồn hỏng", url="https://hong/rss"),
        ],
    )
    signals = collect_signals(config)

    assert signals.feeds == {"Nguồn tốt": ["Tieu de A", "Tieu de B"]}
    assert len(signals.errors) == 1
    assert "Nguồn hỏng" in signals.errors[0]
    assert not signals.is_empty
    assert signals.total_items == 2


def test_tat_ca_nguon_hong_thi_bao_rong_de_cli_dung_lai(monkeypatch):
    import trend.sources as sources

    monkeypatch.setattr(
        sources, "fetch_feed", lambda url, limit=25: (_ for _ in ()).throw(OSError("toang"))
    )
    config = TrendConfig(
        use_google_trends=False, feeds=[sources.Feed(name="A", url="https://a/rss")]
    )
    signals = collect_signals(config)
    assert signals.is_empty
    assert signals.errors


def test_config_load_doc_dung_danh_sach_feed(tmp_path):
    path = tmp_path / "trend.yaml"
    path.write_text(
        "region: VN\n"
        "max_items_per_feed: 5\n"
        "feeds:\n"
        '  - name: "Tâm sự"\n'
        '    url: "https://vi-du/tam-su.rss"\n'
        '  - url: "https://vi-du/khong-ten.rss"\n'
        "youtube_channels:\n"
        '  - "UC123"\n',
        encoding="utf-8",
    )
    config = TrendConfig.load(path)
    assert config.max_items_per_feed == 5
    assert [f.name for f in config.feeds] == ["Tâm sự", "https://vi-du/khong-ten.rss"]
    assert config.youtube_channels == ["UC123"]


def test_config_bo_qua_muc_feed_thieu_url(tmp_path):
    path = tmp_path / "trend.yaml"
    path.write_text('feeds:\n  - name: "Thiếu url"\n', encoding="utf-8")
    assert TrendConfig.load(path).feeds == []


# --- chọn kênh thông báo ------------------------------------------------------


def test_auto_dung_macos_khi_chua_cau_hinh_telegram(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("NOTIFY_CHANNEL", raising=False)
    assert resolve_channel() == MACOS


def test_auto_uu_tien_telegram_khi_da_cau_hinh(monkeypatch):
    monkeypatch.delenv("NOTIFY_CHANNEL", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    assert resolve_channel() == TELEGRAM


def test_telegram_thieu_mot_nua_thi_van_roi_ve_macos(monkeypatch):
    monkeypatch.delenv("NOTIFY_CHANNEL", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert resolve_channel() == MACOS


def test_ep_cung_kenh_bang_bien_moi_truong(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    monkeypatch.setenv("NOTIFY_CHANNEL", "macos")
    assert resolve_channel() == MACOS

    monkeypatch.setenv("NOTIFY_CHANNEL", "none")
    assert resolve_channel() == NONE


def test_gia_tri_kenh_la_thi_roi_ve_auto(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("NOTIFY_CHANNEL", "telegramm")
    assert resolve_channel() == MACOS


# --- AppleScript --------------------------------------------------------------


def test_thoat_ky_tu_dac_biet_cho_applescript():
    # Tiêu đề truyện hay có dấu ngoặc kép — không thoát là AppleScript hỏng cú pháp.
    assert _escape('Cô ấy nói "không"') == 'Cô ấy nói \\"không\\"'
    assert _escape("C:\\path") == "C:\\\\path"
