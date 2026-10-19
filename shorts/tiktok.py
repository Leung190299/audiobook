# shorts/tiktok.py
"""Clip TikTok 3-5 phút: đoạn kịch tính nhất của truyện (19/10).

    uv run python -m shorts.tiktok <tts_metadata_json> --script <script_json>
    # Đã render TikTok: output/tiktok/<trope>-<ts>.mp4  (+ .txt caption để dán)

Khác short YouTube (30-55 giây, đoạn HÀI, mồi về video dài): TikTok ưu tiên
video kể chuyện dài, nên clip lấy trọn một màn cao trào -- bị dồn ép, đối chất,
lật tẩy -- và cắt ngay sau câu chốt. Claude đọc cả truyện (đánh số từng câu) rồi
chọn dải câu; thời lượng thật đo bằng mốc câu của stage 2 rồi nới/cắt về 3-5
phút. Claude lỗi thì lấy đoạn cuối chương áp chót, nơi luật viết đặt cú lật.

Dựng bằng composition ShortVideo (9:16, nền video dọc, phụ đề theo câu), cắt
thẳng từ wav stage 2, không TTS lại. Câu kêu gọi cuối KHÔNG nhắc YouTube:
TikTok hạn chế hiển thị video dẫn sang nền tảng khác. Đăng TikTok là việc tay.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from shorts.planner import PartCaption, ShortPart

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "tiktok"
AUDIO_DIR = REPO_ROOT / "output" / "audio"

MIN_SECONDS = 180.0
MAX_SECONDS = 300.0
TIKTOK_CTA = "Tìm 'Audio Truyện' để nghe trọn truyện"
PART_LABEL = "ĐOẠN CAO TRÀO"
BASE_HASHTAGS = ("#truyenaudio", "#nghetruyen", "#truyenhay", "#audiotruyen")


class TikTokPickError(Exception):
    pass


class TikTokRenderError(Exception):
    pass


@dataclass
class Pick:
    start: int
    end: int
    hook: str = ""
    caption: str = ""


def numbered_sentences(sentences: list[dict]) -> str:
    return "\n".join(
        f"[{i}] (chương {s['chapter_index']}) {s['text']}" for i, s in enumerate(sentences)
    )


def pick_prompt(title: str, sentences: list[dict]) -> str:
    return f"""Truyện audio "{title}", đánh số từng câu theo thứ tự đọc:

{numbered_sentences(sentences)}

Chọn MỘT đoạn LIỀN MẠCH để làm video TikTok dài 3-5 phút (khoảng 650-1.100 từ):
đoạn KỊCH TÍNH nhất truyện -- nhân vật chính bị dồn ép, đối chất, rồi màn lật tẩy.
Đoạn phải tự hiểu được khi xem riêng (câu đầu giới thiệu đủ ai đang đối đầu ai)
và KẾT THÚC NGAY SAU câu chốt của màn lật tẩy.

Chỉ trả về JSON, không giải thích:
{{"start": <số câu đầu>, "end": <số câu cuối>, "hook": "<câu mồi trên màn hình, tối đa 12 chữ>",
 "caption": "<caption TikTok 1-2 câu gây tò mò, tối đa 150 ký tự, không hashtag>"}}"""


def parse_pick(raw: str, n_sentences: int) -> Pick:
    from scripts.generator import ScriptGenerationError, _parse_json_response

    try:
        data = _parse_json_response(raw)
        start, end = int(data["start"]), int(data["end"])
    except (ScriptGenerationError, KeyError, TypeError, ValueError) as exc:
        raise TikTokPickError(f"Không đọc được đoạn Claude chọn: {raw[:200]!r}") from exc
    if not 0 <= start <= end < n_sentences:
        raise TikTokPickError(f"Dải câu vô lý: {start}-{end} (truyện có {n_sentences} câu)")
    return Pick(start, end, str(data.get("hook") or "").strip(), str(data.get("caption") or "").strip())


def _duration(sentences: list[dict], i: int, j: int) -> float:
    return sentences[j]["end_seconds"] - sentences[i]["start_seconds"]


def fit_span(
    sentences: list[dict], i: int, j: int, min_s: float = MIN_SECONDS, max_s: float = MAX_SECONDS
) -> tuple[int, int]:
    """Nới/cắt dải câu về [min_s, max_s] giây. Dài quá thì bỏ bớt câu ĐẦU (giữ
    câu chốt ở cuối); ngắn quá thì kéo thêm câu sau, hết truyện thì lùi đầu."""
    while _duration(sentences, i, j) > max_s and i < j:
        i += 1
    while _duration(sentences, i, j) < min_s:
        if j + 1 < len(sentences) and _duration(sentences, i, j + 1) <= max_s:
            j += 1
        elif i > 0 and _duration(sentences, i - 1, j) <= max_s:
            i -= 1
        else:
            break
    return i, j


def fallback_span(sentences: list[dict]) -> tuple[int, int]:
    """Đoạn cuối chương áp chót (luật viết đặt cú lật ở đó), dài tối đa 4 phút."""
    chapters = sorted({s["chapter_index"] for s in sentences})
    target = chapters[-2] if len(chapters) > 1 else chapters[-1]
    j = max(k for k, s in enumerate(sentences) if s["chapter_index"] == target)
    i = j
    while i > 0 and _duration(sentences, i - 1, j) <= 240.0:
        i -= 1
    return fit_span(sentences, i, j)


def make_part(sentences: list[dict], i: int, j: int, hook: str) -> ShortPart:
    origin = sentences[i]["start_seconds"]
    return ShortPart(
        number=1,
        chapter_index=sentences[i]["chapter_index"],
        heading=hook,
        source_start_seconds=origin,
        source_end_seconds=sentences[j]["end_seconds"],
        captions=[
            PartCaption(s["text"], s["start_seconds"] - origin, s["end_seconds"] - origin)
            for s in sentences[i : j + 1]
        ],
        hook_line=hook,
    )


def caption_text(title: str, caption: str, topic_hashtags: tuple[str, ...] = ()) -> str:
    tags = list(dict.fromkeys([*BASE_HASHTAGS, *topic_hashtags, "#fyp"]))
    lines = [title]
    if caption:
        lines.append(caption)
    lines += ["", " ".join(tags)]
    return "\n".join(lines) + "\n"


def find_tts_metadata(trope: str, title: str, audio_dir: Path = AUDIO_DIR) -> Path | None:
    """Metadata stage 2 mới nhất của truyện này (khớp trope + tiêu đề)."""
    for path in sorted(audio_dir.glob(f"{trope}-*.json"), reverse=True):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("title") == title:
                return path
        except (OSError, json.JSONDecodeError):
            continue
    return None


async def pick_climax(title: str, sentences: list[dict], chat=None) -> Pick:
    """Hỏi Claude chọn đoạn; lỗi gì cũng rơi về fallback_span (in cảnh báo)."""
    try:
        if chat is None:
            from scripts.llm import ClaudeClient

            chat = ClaudeClient(effort="medium").start_chat()
        reply = await chat.send_message(pick_prompt(title, sentences))
        pick = parse_pick(reply.text, len(sentences))
    except Exception as exc:  # noqa: BLE001 -- bước phụ: không được làm hỏng clip
        print(f"CẢNH BÁO: Claude không chọn được đoạn ({exc}); dùng cuối chương áp chót.")
        i, j = fallback_span(sentences)
        return Pick(i, j, title, "")
    i, j = fit_span(sentences, pick.start, pick.end)
    return Pick(i, j, pick.hook or title, pick.caption)


def _remotion(args: list[str]) -> None:
    result = subprocess.run(["npx", "remotion", *args], capture_output=True, text=True, cwd=REMOTION_DIR)
    if result.returncode != 0:
        raise TikTokRenderError(f"Remotion lỗi: {(result.stderr or result.stdout)[-2000:]}")


def _run(tts_metadata_path: Path, script_path: Path) -> Path:
    from episodes import backgrounds
    from scripts.models import Script
    from scripts.topics import TOPICS
    from shorts.audio_cut import cut_wav
    from shorts.props_builder import build_short_props
    from shorts.storage import make_stem

    tts_metadata_path = tts_metadata_path.resolve()
    meta = json.loads(tts_metadata_path.read_text(encoding="utf-8"))
    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    sentences = meta.get("sentences") or []
    if not sentences:
        raise TikTokRenderError("Metadata TTS không có mốc câu; chạy lại stage 2.")

    pick = asyncio.run(pick_climax(meta["title"], sentences))
    part = make_part(sentences, pick.start, pick.end, pick.hook)
    print(f"Đoạn cao trào: câu {pick.start}-{pick.end}, {part.duration_seconds:.0f} giây")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = make_stem(meta["trope"])
    audio_path = OUTPUT_DIR / f"{stem}.wav"
    video_path = OUTPUT_DIR / f"{stem}.mp4"
    cut_wav(tts_metadata_path.with_suffix(".wav"), part.source_start_seconds, part.source_end_seconds, audio_path)

    props = build_short_props(
        part=part,
        total_parts=1,
        episode_title=meta["title"],
        trope=meta["trope"],
        images_metadata=None,
        audio_path=audio_path,
        images_dir=None,
        repo_root=REPO_ROOT,
        cta_text=TIKTOK_CTA,
        background=backgrounds.choose_for_short(seed=stem),
    )
    props["partLabel"] = PART_LABEL
    props_path = OUTPUT_DIR / f"{stem}-props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    _remotion([
        "render", "src/index.ts", "ShortVideo", str(video_path), f"--props={props_path}",
        f"--public-dir={REPO_ROOT}", f"--jpeg-quality={backgrounds.RENDER_JPEG_QUALITY}",
    ])
    if not video_path.exists():
        raise TikTokRenderError(f"Remotion báo xong nhưng không có file {video_path}")

    topic = TOPICS.get(script.topic or "")
    caption_path = video_path.with_suffix(".txt")
    caption_path.write_text(
        caption_text(meta["title"], pick.caption, topic.hashtags if topic else ()), encoding="utf-8"
    )
    print(f"Đã render TikTok: {video_path}\nCaption: {caption_path}")
    return video_path


def main() -> None:
    p = argparse.ArgumentParser(description="Clip TikTok 3-5 phút: đoạn kịch tính nhất của truyện.")
    p.add_argument("tts_metadata", type=Path, help="Metadata stage 2 (output/audio/<trope>-<ts>.json)")
    p.add_argument("--script", type=Path, required=True, help="Kịch bản stage 1")
    a = p.parse_args()
    _run(a.tts_metadata, a.script)


if __name__ == "__main__":
    main()
