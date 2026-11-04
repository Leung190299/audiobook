# tests/trend/test_outliers.py
from datetime import datetime, timedelta, timezone

from trend.outliers import ChannelVideo, Outlier, find_outliers
from trend.sources import TrendConfig, TrendSignals, _parse_channel_videos, collect_signals

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def _v(channel: str, views: int, age_days: float, title: str = "") -> ChannelVideo:
    return ChannelVideo(
        channel=channel,
        title=title or f"{channel} {views}",
        video_id=f"id{views}",
        published=NOW - timedelta(days=age_days),
        views=views,
    )


def test_cham_theo_trung_vi_cua_chinh_kenh_khong_theo_view_tho():
    # Kênh nhỏ 40k/trung vị 8k = 5x lọt; kênh to 500k/trung vị 300k chỉ 1.7x
    # dù view thô gấp 12 lần.
    small = [_v("Nho", 8_000, d) for d in (4, 5, 6)] + [_v("Nho", 40_000, 7)]
    big = [_v("To", 300_000, d) for d in (4, 5, 6)] + [_v("To", 500_000, 7)]
    outliers, thin = find_outliers({"Nho": small, "To": big}, NOW)
    assert [(o.video.channel, o.multiple) for o in outliers] == [("Nho", 5.0)]
    assert thin == []


def test_video_qua_moi_bi_loai_khoi_ca_trung_vi_lan_xep_hang():
    # Video 1 ngày tuổi còn đang lên view: tính vào trung vị là kéo trung vị xuống.
    videos = [_v("A", 10_000, d) for d in (4, 5, 6, 7)] + [_v("A", 100, 1), _v("A", 200, 0.5)]
    outliers, _ = find_outliers({"A": videos}, NOW)
    assert outliers == []


def test_kenh_qua_it_video_du_tuoi_thi_bo_va_bao_ra():
    videos = [_v("A", 1_000, 4), _v("A", 50_000, 5), _v("A", 900, 1)]
    outliers, thin = find_outliers({"A": videos}, NOW)
    assert outliers == []
    assert thin == ["A"]


def test_xep_theo_boi_so_giam_dan():
    a = [_v("A", 1_000, d) for d in (4, 5, 6)] + [_v("A", 3_000, 7)]
    b = [_v("B", 1_000, d) for d in (4, 5, 6)] + [_v("B", 9_000, 7)]
    outliers, _ = find_outliers({"A": a, "B": b}, NOW)
    assert [o.video.channel for o in outliers] == ["B", "A"]
    assert outliers[0].url == "https://youtu.be/id9000"


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Mạn Mạn Audio</title>
 <entry>
  <yt:videoId>NQfpChtWHXQ</yt:videoId>
  <title>Hoa Khôi Bán Đậu Hũ Thối | Mạn Mạn Audio</title>
  <published>2026-11-03T12:04:59+00:00</published>
  <media:group><media:community>
   <media:starRating count="25" average="5.00" min="1" max="5"/>
   <media:statistics views="1403"/>
  </media:community></media:group>
 </entry>
 <entry>
  <yt:videoId>thieuview</yt:videoId>
  <title>Không có lượt xem</title>
  <published>2026-11-02T12:00:00+00:00</published>
 </entry>
</feed>""".encode()


def test_parse_feed_kenh_lay_luot_xem_va_ngay_dang():
    videos = _parse_channel_videos(FEED)
    assert len(videos) == 1  # mục thiếu lượt xem bị bỏ
    v = videos[0]
    assert (v.channel, v.video_id, v.views) == ("Mạn Mạn Audio", "NQfpChtWHXQ", 1403)
    assert v.published == datetime(2026, 11, 3, 12, 4, 59, tzinfo=timezone.utc)


def test_collect_signals_van_giu_tieu_de_kenh_va_them_outliers(monkeypatch):
    import trend.sources as sources

    now = datetime.now(timezone.utc)
    videos = [
        ChannelVideo("Kênh X", f"Truyện {i}", f"v{i}", now - timedelta(days=4 + i), views)
        for i, views in enumerate([1_000, 1_100, 900, 5_000])
    ]
    monkeypatch.setattr(sources, "fetch_channel_videos", lambda cid: videos)
    signals = collect_signals(TrendConfig(use_google_trends=False, youtube_channels=["UCx"]))
    assert signals.feeds["Kênh YouTube UCx"] == ["Truyện 0", "Truyện 1", "Truyện 2", "Truyện 3"]
    assert [o.video.title for o in signals.outliers] == ["Truyện 3"]


def test_feed_kenh_loi_khong_lam_hong_ca_luot(monkeypatch):
    import trend.sources as sources

    def boom(cid):
        raise OSError("404")

    monkeypatch.setattr(sources, "fetch_channel_videos", boom)
    signals = collect_signals(TrendConfig(use_google_trends=False, youtube_channels=["UCx"]))
    assert signals.outliers == []
    assert "UCx" in signals.errors[0]


def test_prompt_dua_video_vuot_troi_da_bo_vo_boc():
    from trend.idea_generator import build_idea_prompt

    v = ChannelVideo("Vả Mặt Audio", "[Truyện Audio Full] | Gả Thay Cho Chị, Tôi Thành Phu Nhân | Vả Mặt Audio",
                     "abc", NOW, 50_000)
    signals = TrendSignals(feeds={"Kênh YouTube UCx": ["a"]})
    signals.outliers = [Outlier(video=v, median=10_000, multiple=5.0)]
    prompt = build_idea_prompt(signals, [])
    assert "VƯỢT TRỘI" in prompt
    assert "- 5.0x | Gả Thay Cho Chị, Tôi Thành Phu Nhân" in prompt
    assert "Vả Mặt Audio" not in prompt


def test_prompt_khong_co_vuot_troi_thi_khong_them_muc():
    from trend.idea_generator import build_idea_prompt

    prompt = build_idea_prompt(TrendSignals(feeds={"Kênh YouTube UCx": ["a"]}), [])
    assert "VƯỢT TRỘI" not in prompt
