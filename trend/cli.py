"""Stage 0: chọn chủ đề bắt trend cho tập hôm nay.

    uv run python -m trend.cli
    # Đã lưu ý tưởng: output/ideas/<slug>-<ts>.txt
    # Slug: <slug>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from trend.idea_generator import generate_idea
from trend.sources import TrendConfig, collect_signals
from trend.storage import append_history, load_recent_titles, save_idea

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "trend.yaml"
OUTPUT_DIR = ROOT / "output" / "ideas"


async def _run(config_path: Path, output_dir: Path) -> None:
    config = TrendConfig.load(config_path)

    signals = collect_signals(config)

    for error in signals.errors:
        print(f"[trend] {error}", file=sys.stderr)

    if signals.is_empty:
        raise SystemExit(
            "Không lấy được tín hiệu nào từ bất kỳ nguồn nào. Kiểm tra mạng, "
            "hoặc chạy pipeline theo trope có sẵn: ./run_daily.sh --trope <trope_id>"
        )

    for name, titles in signals.feeds.items():
        print(f"[trend] {name}: {len(titles)} tiêu đề", file=sys.stderr)
    print(
        f"[trend] Google Trends: {len(signals.google_trends)} từ khoá "
        f"(tổng {signals.total_items} tín hiệu)",
        file=sys.stderr,
    )

    recent = load_recent_titles(output_dir)
    idea = await generate_idea(signals, recent)
    txt_path, json_path = save_idea(idea, output_dir)
    append_history(output_dir, idea)

    print(f"Đã lưu ý tưởng: {txt_path}")
    print(f"JSON: {json_path}")
    print(f"Slug: {idea.slug}")
    print(f"Tiêu đề gợi ý: {idea.title_hint}")
    print(f"Bám trend: {idea.trend_hook}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh ý tưởng truyện bắt trend cho tập hôm nay."
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    asyncio.run(_run(args.config, args.output_dir))


if __name__ == "__main__":
    main()
