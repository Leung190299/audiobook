# shorts/tiktok.py
"""Clip TikTok 3-5 phút: đoạn kịch tính nhất của truyện (19/10).

    uv run python -m shorts.tiktok <tts_metadata_json> --script <script_json>
    # Đã render TikTok: output/tiktok/<trope>-<ts>.mp4  (+ .txt caption để dán)
    uv run python -m shorts.tiktok --all   # mọi truyện full đã dựng/đăng chưa có clip
    uv run python -m shorts.tiktok --captions   # caption kèm link YouTube + SEO

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


MAX_HASHTAGS = 10
INDEX_JSONL = REPO_ROOT / "output" / "metadata" / "index.jsonl"


def caption_text(
    title: str,
    caption: str,
    topic_hashtags: tuple[str, ...] = (),
    *,
    url: str | None = None,
    air=None,
    keywords: list[str] | tuple[str, ...] = (),
    yt_hashtags: list[str] | tuple[str, ...] = (),
    now=None,
) -> str:
    """Caption dán vào TikTok: tiêu đề, câu mồi, link video full YouTube (khi đã
    đăng), từ khoá cho ô tìm kiếm TikTok, hashtag.

    Link nằm ở CAPTION theo yêu cầu kênh (21/10), không đè lên video: chữ trên
    video nhắc nền tảng khác thì TikTok hạn chế hiển thị. Link trong caption
    TikTok không bấm được -- người xem phải chép, nên kèm cả tên kênh để tìm."""
    tags = list(dict.fromkeys([*BASE_HASHTAGS, *yt_hashtags, *topic_hashtags, "#fyp"]))
    tags = [t for t in tags if t != "#fyp"][: MAX_HASHTAGS - 1] + ["#fyp"]
    lines = [title]
    if caption:
        lines.append(caption)
    if url:
        lines.append("")
        from datetime import datetime, timezone

        now = now or datetime.now(timezone.utc)
        # Video đã chiếu thì không ghi giờ: "lên sóng 28/09" đọc như chưa chiếu.
        when = f" (lên sóng {air:%H:%M %d/%m})" if air is not None and air > now else ""
        lines.append(f"▶ Nghe trọn truyện trên YouTube kênh Audio Truyện{when}: {url}")
    kws = list(dict.fromkeys(k.strip() for k in keywords if k.strip()))[:6]
    if kws:
        lines.append("🔎 " + " | ".join(kws))
    lines += ["", " ".join(tags)]
    return "\n".join(lines) + "\n"


def _youtube_rows(index_jsonl: Path) -> dict[str, dict]:
    """story_title -> dòng index.jsonl mới nhất của video dài đã đăng."""
    rows: dict[str, dict] = {}
    if not index_jsonl.exists():
        return rows
    for line in index_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("story_title") or row.get("title")
        if key and row.get("url"):
            rows[key] = row
    return rows


def _old_caption(txt: Path, title: str) -> str:
    """Câu mồi Claude viết lúc render, đọc lại từ .txt cũ (dòng thứ 2)."""
    if not txt.exists():
        return ""
    lines = txt.read_text(encoding="utf-8").splitlines()
    if len(lines) > 1 and lines[0] == title and lines[1] and not lines[1].startswith(("#", "▶", "🔎")):
        return lines[1]
    return ""


def posting_name(title: str, publish_at: str | None) -> str:
    """Tên file dễ đăng: ngày video YouTube lên sóng + tên truyện. Sắp theo tên
    là ra đúng thứ tự đăng; truyện chưa lên YouTube thì dồn về cuối."""
    from metadata.filename import slugify

    prefix = publish_at[:10] if publish_at else "chua-dang-youtube"
    return f"{prefix}_{slugify(title, max_length=80)}"


def _rename_for_posting(video: Path, title: str, publish_at: str | None) -> Path:
    target = video.with_name(posting_name(title, publish_at) + ".mp4")
    if target == video or not video.exists():
        return video if video.exists() else target
    for ext in (".mp4", ".txt"):
        src = video.with_suffix(ext)
        if src.exists():
            src.replace(target.with_suffix(ext))
    return target


def refresh_captions(done_index: Path | None = None, index_jsonl: Path | None = None) -> int:
    """Viết lại .txt của mọi clip TikTok theo link + SEO YouTube hiện có. Chạy sau
    mỗi lượt đăng YouTube (upload/episodes_cli.py gọi). Trả về số clip có link."""
    from datetime import datetime

    from scripts.topics import TOPICS

    done_index = done_index or DONE_INDEX
    index_jsonl = index_jsonl or INDEX_JSONL
    if not done_index.exists():
        return 0
    rows = _youtube_rows(index_jsonl)
    linked = 0
    done = json.loads(done_index.read_text(encoding="utf-8"))
    for title, video in list(done.items()):
        row = rows.get(title, {})
        video = _rename_for_posting(Path(video), title, row.get("publishAt"))
        done[title] = str(video)
        txt = video.with_suffix(".txt")
        seo: dict = {}
        if row.get("index"):
            try:
                seo = json.loads(Path(row["index"]).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                seo = {}
        topic = TOPICS.get(seo.get("topic") or row.get("topic") or "")
        air = None
        if row.get("publishAt"):
            try:
                air = datetime.fromisoformat(row["publishAt"])
            except ValueError:
                air = None
        txt.write_text(
            caption_text(
                title, _old_caption(txt, title), topic.hashtags if topic else (),
                url=row.get("url"), air=air, keywords=seo.get("tags") or (),
                yt_hashtags=seo.get("hashtags") or (),
            ),
            encoding="utf-8",
        )
        linked += bool(row.get("url"))
    done_index.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
    write_seo_doc(done_index, rows)
    return linked


SEO_DOC = OUTPUT_DIR / "SEO_TIKTOK.md"


def write_seo_doc(done_index: Path, rows: dict[str, dict], out: Path | None = None, now=None) -> Path:
    """Một file gom caption SEO của mọi clip, chia theo đã/chưa nên đăng, để chép
    dán từng khối vào TikTok. Clip đăng trước giờ YouTube lên sóng thì link mở ra
    video riêng tư, nên xếp nhóm theo giờ lên sóng."""
    from datetime import datetime, timezone

    out = out or done_index.parent / SEO_DOC.name
    now = now or datetime.now(timezone.utc)
    done = json.loads(done_index.read_text(encoding="utf-8"))
    groups: dict[str, list] = {
        "ĐĂNG ĐƯỢC NGAY (video YouTube đã lên sóng)": [],
        "CHỜ — đăng sau giờ YouTube lên sóng": [],
        "CHƯA ĐĂNG — truyện chưa có trên YouTube": [],
    }
    names = list(groups)
    for title, video in done.items():
        raw = rows.get(title, {}).get("publishAt")
        air = datetime.fromisoformat(raw) if raw else None
        key = names[2] if air is None else (names[0] if air <= now else names[1])
        groups[key].append((air.isoformat() if air else "", title, Path(video)))
    lines = [f"# SEO TikTok — {len(done)} clip", "",
             "Chép nguyên khối dán vào ô mô tả TikTok. File video nằm trong `output/tiktok/`.", ""]
    n = 0
    for name, items in groups.items():
        lines += [f"## {name} ({len(items)})", ""]
        for air, title, video in sorted(items):
            n += 1
            when = f" — YouTube {air[11:16]} {air[8:10]}/{air[5:7]}" if air else ""
            txt = video.with_suffix(".txt")
            body = txt.read_text(encoding="utf-8").strip() if txt.exists() else title
            lines += [f"### {n}. {title}{when}", f"File: `{video.name}`", "", "```", body, "```", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


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
    from scripts.models import without_prologue

    # Bỏ chương "Mở đầu" (kể trước cao trào): clip phải lấy cao trào thật.
    sentences = without_prologue(meta).get("sentences") or []
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


DONE_INDEX = OUTPUT_DIR / "done.json"
EPISODES_DIR = REPO_ROOT / "output" / "episodes"


def pending_stories(
    episodes_dir: Path = EPISODES_DIR, done_index: Path = DONE_INDEX, audio_dir: Path = AUDIO_DIR
) -> list[tuple[str, Path, Path]]:
    """(tiêu đề, metadata TTS, kịch bản) của mọi truyện FULL đã dựng mà chưa
    có clip TikTok. Truyện dựng nhiều lần thì lấy bản mới nhất."""
    done = json.loads(done_index.read_text(encoding="utf-8")) if done_index.exists() else {}
    found: dict[str, tuple[str, Path, Path]] = {}
    for manifest in sorted(episodes_dir.glob("*-full.json")):
        try:
            d = json.loads(manifest.read_text(encoding="utf-8"))
            script = Path(d["script_path"])
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        tts = find_tts_metadata(d.get("trope", ""), d.get("title", ""), audio_dir)
        if d.get("title") in done or tts is None or not script.exists():
            continue
        found[d["title"]] = (d["title"], tts, script)
    return list(found.values())


def _mark_done(title: str, video: Path, done_index: Path = DONE_INDEX) -> None:
    done = json.loads(done_index.read_text(encoding="utf-8")) if done_index.exists() else {}
    done[title] = str(video)
    done_index.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")


def run_all() -> None:
    todo = pending_stories()
    print(f"{len(todo)} truyện chưa có clip TikTok")
    for n, (title, tts, script) in enumerate(todo, 1):
        print(f"== [{n}/{len(todo)}] {title}", flush=True)
        try:
            _mark_done(title, _run(tts, script))
        except Exception as exc:  # noqa: BLE001 -- một truyện hỏng không chặn cả lô
            print(f"LỖI: {title}: {exc}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Clip TikTok 3-5 phút: đoạn kịch tính nhất của truyện.")
    p.add_argument("tts_metadata", type=Path, nargs="?", help="Metadata stage 2 (output/audio/<trope>-<ts>.json)")
    p.add_argument("--script", type=Path, help="Kịch bản stage 1")
    p.add_argument("--all", action="store_true", help="Làm cho mọi truyện full đã dựng chưa có clip")
    p.add_argument("--captions", action="store_true", help="Viết lại caption .txt kèm link YouTube + SEO")
    a = p.parse_args()
    if a.captions:
        print(f"Đã cập nhật caption; {refresh_captions()} clip có link YouTube")
    elif a.all:
        run_all()
        refresh_captions()  # truyện đã đăng thì caption có link ngay
    elif a.tts_metadata and a.script:
        meta = json.loads(a.tts_metadata.read_text(encoding="utf-8"))
        _mark_done(meta["title"], _run(a.tts_metadata, a.script))
        refresh_captions()
    else:
        p.error("cần <tts_metadata> --script <kịch bản>, hoặc --all")


if __name__ == "__main__":
    main()
