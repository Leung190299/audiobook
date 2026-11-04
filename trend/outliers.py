"""Video kênh đối thủ VƯỢT TRỘI so với chính kênh đó -- tín hiệu khuôn đang ăn khách.

    uv run python -m trend.outliers [--min 2.0]

View thô chỉ xếp hạng độ to của kênh: 40k ở kênh trung vị 8k đáng học hơn hẳn
100k ở kênh trung vị 300k. Nên mỗi video được chấm bằng BỘI SỐ so với trung vị
view của chính kênh nó (ý từ yt-viral trong
github.com/Jakeschincariol/chatgpt-youtube-agent-skill, viết lại cho kênh mình).

Dữ liệu là feed công khai của YouTube (15 video mới nhất, có sẵn lượt xem trong
<media:statistics>) -- không key, không đăng nhập. Hai giới hạn cần biết:
- Video dưới MIN_AGE_DAYS ngày bị loại khỏi cả trung vị lẫn xếp hạng: view còn
  đang lên, so với video cũ là thiệt.
- 15 video trải ~2 tuần với kênh ra mỗi ngày, video cũ hơn vẫn có lợi thế vài
  ngày tích view. Bội số 2x trở lên mới đáng tin, 1.3x là nhiễu.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIN_AGE_DAYS = 3
MIN_VIDEOS = 4
MIN_MULTIPLE = 2.0


@dataclass(frozen=True)
class ChannelVideo:
    channel: str
    title: str
    video_id: str
    published: datetime
    views: int


@dataclass(frozen=True)
class Outlier:
    video: ChannelVideo
    median: float
    multiple: float

    @property
    def url(self) -> str:
        return f"https://youtu.be/{self.video.video_id}"


def find_outliers(
    videos_by_channel: dict[str, list[ChannelVideo]],
    now: datetime,
    min_age_days: float = MIN_AGE_DAYS,
    min_videos: int = MIN_VIDEOS,
    min_multiple: float = MIN_MULTIPLE,
) -> tuple[list[Outlier], list[str]]:
    """-> (video vượt trội xếp theo bội số giảm dần, kênh bị bỏ vì quá ít video đủ tuổi).

    Trung vị từ dưới `min_videos` video là nhiễu, nên kênh đó bị bỏ và báo ra
    thay vì xếp hạng ngầm trên số liệu không đáng tin.
    """
    outliers: list[Outlier] = []
    thin: list[str] = []
    for channel, videos in videos_by_channel.items():
        settled = [v for v in videos if (now - v.published).total_seconds() >= min_age_days * 86400]
        if len(settled) < min_videos:
            thin.append(channel)
            continue
        median = statistics.median(v.views for v in settled)
        if median <= 0:
            continue
        for v in settled:
            multiple = v.views / median
            if multiple >= min_multiple:
                outliers.append(Outlier(video=v, median=median, multiple=multiple))
    outliers.sort(key=lambda o: -o.multiple)
    return outliers, thin


def main() -> None:
    from trend.sources import TrendConfig, fetch_channel_videos

    parser = argparse.ArgumentParser(description="Video kênh đối thủ vượt trội so với chính kênh đó.")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config" / "trend.yaml")
    parser.add_argument("--min", type=float, default=MIN_MULTIPLE, help=f"bội số tối thiểu (mặc định {MIN_MULTIPLE})")
    args = parser.parse_args()

    config = TrendConfig.load(args.config)
    videos_by_channel: dict[str, list[ChannelVideo]] = {}
    for channel_id in config.youtube_channels:
        try:
            videos = fetch_channel_videos(channel_id)
        except Exception as exc:  # noqa: BLE001 -- feed nào lỗi thì báo rồi đi tiếp
            print(f"  LỖI feed {channel_id}: {exc} -- ID chết hoặc kênh đổi tên, soát config/trend.yaml", file=sys.stderr)
            continue
        if videos:
            videos_by_channel[videos[0].channel] = videos

    now = datetime.now(timezone.utc)
    outliers, thin = find_outliers(videos_by_channel, now, min_multiple=args.min)
    print(f"\n  {sum(map(len, videos_by_channel.values()))} video / {len(videos_by_channel)} kênh, "
          f"vượt trội từ {args.min:g}x trung vị kênh\n")
    for o in outliers:
        age = (now - o.video.published).days
        print(f"  {o.multiple:5.1f}x  {o.video.views:>9,} / trung vị {o.median:>9,.0f}  {age:>2} ngày  "
              f"{o.video.channel[:20]:<20}  {o.video.title[:70]}")
        print(f"          {o.url}")
    if not outliers:
        print("  Không video nào vượt ngưỡng -- hạ --min hoặc chờ thêm vài ngày.")
    if thin:
        print(f"\n  Bỏ qua (dưới {MIN_VIDEOS} video đủ {MIN_AGE_DAYS} ngày tuổi): {', '.join(thin)}")
    print()


if __name__ == "__main__":
    main()
