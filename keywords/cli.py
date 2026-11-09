"""Stage 0: từ khóa xu hướng -> truyện cho hôm nay.

    uv run python -m keywords.cli            # in "Truyện: <id>" cho run_daily.sh
    uv run python -m keywords.cli --dry-run  # chỉ in bảng điểm cụm, không gọi mô hình

Thứ tự: gom gợi ý tìm kiếm YouTube VN + video đối thủ (cache 7 ngày) -> chấm
4 cột -> lấy cụm điểm cao chưa dùng -> dò kho: có truyện mang cụm đó thì dùng
luôn; không có thì nhờ mô hình (STORY_LLM) viết một bản ghi kho mới mang đúng cụm,
lưu vào data/story_bank.auto.json. Mã thoát 3 = không có cụm nào đạt (run_daily
rơi về chọn truyện trong kho như cũ).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from keywords import sources
from keywords.matching import find_bank_story
from keywords.prompts import build_keyword_story_prompt, build_keyword_story_retry_prompt
from keywords.scoring import Cluster, score_clusters
from keywords.story import append_auto_story, next_auto_id, to_bank_record, validate_story
from scripts import story_bank

load_dotenv()

STORY_ATTEMPTS = 3
TOP_CANDIDATES = 5  # thử tối đa chừng này cụm trước khi bỏ cuộc


def load_used(path: Path, window_days: int) -> list[str]:
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).date().isoformat()
    return [r["phrase"] for r in rows if isinstance(r, dict) and r.get("date", "") >= cutoff]


def record_used(path: Path, phrase: str, story_id: int, source: str) -> None:
    rows = []
    if path.exists():
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []
    rows.append({"date": date.today().isoformat(), "phrase": phrase, "story_id": story_id, "source": source})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def competitor_videos(config: sources.KeywordConfig, cache_dir: Path, refresh: bool) -> list:
    cached = None if refresh else sources.load_competitor_cache(cache_dir, config.competitor_cache_days)
    if cached is not None:
        return cached
    try:
        from upload.auth import load_credentials

        videos = sources.fetch_competitor_videos(load_credentials(), config.competitors, cache_dir)
        sources.save_competitor_cache(cache_dir, videos)
        return videos
    except Exception as exc:  # thiếu token/hết hạn mức: vẫn chấm được bằng gợi ý
        print(f"CẢNH BÁO: không lấy được video đối thủ ({exc}); cột View = 0.", file=sys.stderr)
        stale = sources.load_competitor_cache(cache_dir, 10_000)
        return stale or []


def describe(clusters: list[Cluster], limit: int = 25) -> str:
    lines = [f"{'Tổng':>4} {'Cầu':>3} {'View':>4} {'Giọng':>5} {'Mới':>3}  cụm"]
    for c in clusters[:limit]:
        lines.append(f"{c.total:>4} {c.demand:>3} {c.view:>4} {c.voice:>5} {c.novelty:>3}  {c.phrase}")
    return "\n".join(lines)


async def write_story(cluster: Cluster, bank, titles: list[str], llm: str | None) -> dict | None:
    from scripts.generator import ScriptGenerationError, _parse_json_response
    from scripts.llm import make_client

    client = await make_client(llm)
    chat = client.start_chat()
    prompt = build_keyword_story_prompt(cluster.phrase, cluster.evidence, bank.writing_rules, titles)
    for attempt in range(STORY_ATTEMPTS):
        reply = await chat.send_message(prompt)
        try:
            data = _parse_json_response(reply.text)
        except ScriptGenerationError as exc:
            problems = [f"không đọc được JSON: {str(exc)[:160]}"]
        else:
            problems = validate_story(data, cluster.phrase, titles)
            if not problems:
                return data
        print(f"Lượt {attempt + 1}/{STORY_ATTEMPTS} chưa đạt: {'; '.join(problems)}")
        prompt = build_keyword_story_retry_prompt(problems)
    return None


async def run(args) -> int:
    config = sources.KeywordConfig.load(args.config)
    cache_dir = args.cache_dir
    used_path = cache_dir / "used.json"

    bank = story_bank.load_bank()
    taken = story_bank.used_ids()
    titles = [s.title for s in bank.stories]
    used_recent = load_used(used_path, config.used_window_days)

    suggest = sources.collect_suggestions(config.seeds, config.letters)
    print(f"Gợi ý: {len(suggest)} cụm từ {len(config.seeds)} hạt giống.")
    videos = competitor_videos(config, cache_dir, args.refresh_competitors)
    print(f"Đối thủ: {len(videos)} video.")

    clusters = score_clusters(
        suggest, videos, titles, used_recent, config.voice_blocklist, config.voice_allowlist
    )
    print(describe(clusters))
    (cache_dir).mkdir(parents=True, exist_ok=True)
    (cache_dir / f"clusters-{date.today().isoformat()}.json").write_text(
        json.dumps([c.__dict__ for c in clusters], ensure_ascii=False, indent=1), encoding="utf-8"
    )
    good = [c for c in clusters if c.total >= config.min_score and c.voice > 0 and c.novelty > 0]
    if args.dry_run:
        return 0
    if not good:
        print(f"Không cụm nào đạt ngưỡng {config.min_score}; dùng kho như cũ.")
        return 3

    for cluster in good[:TOP_CANDIDATES]:
        print(f"Từ khóa: {cluster.phrase}")
        hit = find_bank_story(cluster.phrase, bank.stories, taken)
        if hit is not None:
            record_used(used_path, cluster.phrase, hit.id, "kho")
            print("Nguồn: kho")
            print(f"Tiêu đề: {hit.title}")
            print(f"Truyện: {hit.id}")
            return 0
        if args.no_llm:
            continue
        data = await write_story(cluster, bank, titles, args.llm)
        if data is None:
            print(f"CẢNH BÁO: mô hình không viết được truyện cho '{cluster.phrase}', thử cụm khác.")
            continue
        story_id = next_auto_id(args.auto_bank)
        record = to_bank_record(data, story_id, cluster.phrase)
        append_auto_story(record, args.auto_bank)
        record_used(used_path, cluster.phrase, story_id, "mới")
        print("Nguồn: mới")
        print(f"Tiêu đề: {record['title']}")
        print(f"Đã lưu kho phụ: {args.auto_bank}")
        print(f"Truyện: {story_id}")
        return 0
    print("Không tạo được truyện từ các cụm đạt ngưỡng; dùng kho như cũ.")
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 0: từ khóa xu hướng -> truyện hôm nay.")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in bảng điểm cụm")
    parser.add_argument("--no-llm", action="store_true", help="Chỉ dò kho, không tự viết truyện mới")
    parser.add_argument("--refresh-competitors", action="store_true", help="Bỏ cache, gọi API lại")
    parser.add_argument("--llm", default=None, help="claude | gemini (mặc định STORY_LLM)")
    parser.add_argument("--config", type=Path, default=sources.DEFAULT_CONFIG_PATH)
    parser.add_argument("--cache-dir", type=Path, default=sources.DEFAULT_CACHE_DIR)
    parser.add_argument("--auto-bank", type=Path, default=story_bank.DEFAULT_AUTO_BANK_PATH)
    args = parser.parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())


def main_sync(args) -> int:
    """Chạy `run` với args đã dựng sẵn (test dùng, khỏi qua argparse)."""
    return asyncio.run(run(args))
