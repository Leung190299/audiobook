# episodes/props_builder.py
"""Dựng props Remotion (composition MainVideo) cho MỘT tập.

Khác video/props_builder.py (cả truyện, trục thời gian = wav gốc) ở chỗ mọi
mốc ở đây QUY VỀ TRỤC CỦA TẬP: wav của tập là file ghép mới (xem
audio_build.py), nên cảnh/câu của thân tập dời đi một khoảng bằng cold open +
khoảng nghỉ, còn cold open thành một 'chương' giả index 0 ở đầu.

Props thêm so với VideoProps cũ (đều tuỳ chọn để MainVideo vẫn render được
props của video/cli.py):
    episodeLabel     "TẬP 1/3" -- góc trên video
    hookText         câu hook của truyện -- hiện trong cold open
    coldOpenSeconds  độ dài cold open (0 nếu không có)
    outroSeconds     độ dài card kết
    outroTitle       dòng to trên card kết (tiêu đề truyện)
    outroText        dòng vàng trên card kết ("Tập 2 lên sóng 20h mai…")
"""

from pathlib import Path

from episodes.cutter import EpisodeCut
from scripts.models import Script

COLD_OPEN_HEADING = "Mở đầu"
NEXT_EPISODE_TIME_TEXT = "20h mai"


class EpisodePropsBuildError(Exception):
    pass


def outro_text(cut: EpisodeCut, comment_question: str = "") -> str:
    ep = cut.episode
    if ep.is_last:
        base = "Hết truyện. Đăng ký kênh để nghe truyện mới mỗi ngày!"
    else:
        base = f"Tập {ep.number + 1} lên sóng {NEXT_EPISODE_TIME_TEXT} — đăng ký để không bỏ lỡ!"
    if comment_question:
        return f"{comment_question}\n{base}"
    return base


def _relative_image(images_dir: Path, filename: str, repo_root: Path) -> str:
    image_path = images_dir / filename
    if not image_path.exists():
        raise EpisodePropsBuildError(f"Không tìm thấy file ảnh: {image_path}")
    try:
        return str(image_path.relative_to(repo_root))
    except ValueError as exc:
        raise EpisodePropsBuildError(
            f"File ảnh {image_path} nằm ngoài repo ({repo_root}) -- images_dir phải là "
            "thư mục con của repo_root"
        ) from exc


def _scenes_in(
    scenes: list[dict],
    source_start: float,
    source_end: float,
    shift: float,
    images_dir: Path,
    repo_root: Path,
) -> list[dict]:
    """Các cảnh giao với [source_start, source_end), mốc dời sang trục tập bằng
    `shift` (= mốc tập - mốc gốc) và kẹp trong khoảng của khúc."""
    overlapping = [
        s for s in scenes if s["end_seconds"] > source_start and s["start_seconds"] < source_end
    ]
    return [
        {
            "number": s["number"],
            "startSeconds": max(source_start, s["start_seconds"]) + shift,
            "endSeconds": min(source_end, s["end_seconds"]) + shift,
            "imagePath": _relative_image(images_dir, s["filename"], repo_root),
        }
        for s in overlapping
    ]


def _sentences_in(sentences: list[dict], source_start: float, source_end: float, shift: float) -> list[dict]:
    return [
        {
            "text": s["text"],
            "startSeconds": s["start_seconds"] + shift,
            "endSeconds": s["end_seconds"] + shift,
        }
        for s in sentences
        if s["start_seconds"] >= source_start and s["end_seconds"] <= source_end
    ]


def build_episode_props(
    script: Script,
    tts_metadata: dict,
    images_metadata: dict | None,
    cut: EpisodeCut,
    audio_path: Path,
    images_dir: Path | None,
    repo_root: Path,
    episode_label: str | None = None,
    outro: str | None = None,
) -> dict:
    """`episode_label`/`outro` None = mặc định chế độ tập ("TẬP N/3", card tập
    sau). Chế độ full truyền "" (không badge -- MainVideo ẩn khi rỗng) và câu
    card kết riêng (episodes/full.py).

    `images_metadata` None = dựng bằng video nền (episodes/backgrounds.py), bỏ
    hẳn stage 3: mỗi chương có `scenes` rỗng, MainVideo chỉ vẽ video nền. Mốc
    chương, mốc câu và cold open vẫn tính như thường.
    """
    sources = [("tts", tts_metadata)]
    if images_metadata is not None:
        sources.append(("images", images_metadata))
    for source_name, source in sources:
        if source["trope"] != script.trope or source["title"] != script.title:
            raise EpisodePropsBuildError(
                f"trope/title của {source_name}_metadata không khớp với script "
                f"(script: {script.trope!r}/{script.title!r}, "
                f"{source_name}: {source['trope']!r}/{source['title']!r})"
            )
    if not tts_metadata.get("sentences"):
        raise EpisodePropsBuildError(
            "Metadata TTS thiếu mảng 'sentences' -- chạy lại stage 2 cho tập này."
        )

    ep = cut.episode
    tts_by_index = {c["index"]: c for c in tts_metadata["chapters"]}
    images_by_index = (
        {c["index"]: c for c in images_metadata["chapters"]} if images_metadata is not None else None
    )
    script_by_index = {c.index: c for c in script.chapters}
    sentences_by_chapter: dict[int, list[dict]] = {}
    for s in tts_metadata["sentences"]:
        sentences_by_chapter.setdefault(s["chapter_index"], []).append(s)

    tables = [("script", script_by_index), ("tts", tts_by_index)]
    if images_by_index is not None:
        tables.append(("images", images_by_index))
    for index in ep.chapter_indices:
        missing = [name for name, table in tables if index not in table]
        if missing:
            raise EpisodePropsBuildError(f"Thiếu chương {index} trong: {', '.join(missing)}")
        if images_by_index is not None and not images_by_index[index].get("scenes"):
            raise EpisodePropsBuildError(
                f"Metadata ảnh của chương {index} không có mảng 'scenes' -- chạy lại stage 3."
            )

    chapters: list[dict] = []

    if cut.cold_open is not None:
        co = cut.cold_open
        shift = -co.source_start_seconds
        chapters.append(
            {
                "index": 0,
                "heading": COLD_OPEN_HEADING,
                "startSeconds": 0.0,
                "endSeconds": co.duration_seconds,
                "scenes": (
                    _scenes_in(
                        images_by_index[co.chapter_index]["scenes"],
                        co.source_start_seconds, co.source_end_seconds, shift, images_dir, repo_root,
                    )
                    if images_by_index is not None
                    else []
                ),
                "sentences": _sentences_in(
                    sentences_by_chapter.get(co.chapter_index, []),
                    co.source_start_seconds,
                    co.source_end_seconds,
                    shift,
                ),
            }
        )

    body_shift = cut.body_offset_seconds - cut.body_source_start_seconds
    for index in ep.chapter_indices:
        tts_chapter = tts_by_index[index]
        start = float(tts_chapter["start_seconds"])
        end = float(tts_chapter["end_seconds"])
        chapters.append(
            {
                "index": index,
                "heading": script_by_index[index].heading,
                "startSeconds": start + body_shift,
                "endSeconds": end + body_shift,
                "scenes": (
                    _scenes_in(images_by_index[index]["scenes"], start, end, body_shift, images_dir, repo_root)
                    if images_by_index is not None
                    else []
                ),
                "sentences": _sentences_in(sentences_by_chapter.get(index, []), start, end, body_shift),
            }
        )
    # Chương cuối của tập kéo tới hết thân tập (mốc chương của stage 2 và
    # body_source_end trùng nhau theo định nghĩa, nhưng chốt lại cho chắc).
    chapters[-1]["endSeconds"] = cut.outro_start_seconds

    return {
        "trope": script.trope,
        "title": script.title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "sampleRate": tts_metadata["sample_rate"],
        "chapters": chapters,
        "episodeLabel": f"TẬP {ep.number}/{ep.total}" if episode_label is None else episode_label,
        "hookText": script.hook,
        "coldOpenSeconds": cut.cold_open.duration_seconds if cut.cold_open else 0.0,
        "outroSeconds": cut.outro_seconds,
        "outroTitle": script.title,
        "outroText": outro_text(cut, script.comment_question) if outro is None else outro,
    }


def chapter_lines(cut: EpisodeCut, script: Script, tts_metadata: dict) -> list[dict]:
    """Mốc chương trên trục tập cho mô tả YouTube: [{'heading', 'start_seconds'}].
    Mốc đầu luôn 0:00 (YouTube bắt buộc để hiện 'Khoảnh khắc chính')."""
    tts_by_index = {c["index"]: c for c in tts_metadata["chapters"]}
    script_by_index = {c.index: c for c in script.chapters}
    lines: list[dict] = []
    if cut.cold_open is not None:
        lines.append({"heading": COLD_OPEN_HEADING, "start_seconds": 0.0})
    for index in cut.episode.chapter_indices:
        lines.append(
            {
                "heading": script_by_index[index].heading,
                "start_seconds": round(cut.to_episode_time(float(tts_by_index[index]["start_seconds"])), 3),
            }
        )
    lines[0]["start_seconds"] = 0.0
    return lines
