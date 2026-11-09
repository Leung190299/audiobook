# episodes/cli.py
"""Stage 4: dựng MỖI TẬP một video 15-20 phút, hoặc (--format full, từ 24/09)
MỘT video cả truyện có cold open + card kết (xem episodes/full.py).

    uv run python -m episodes.cli <script> <tts> <images> --format full
    # Đã render video full: output/episodes/<topic>-<ts>-full.mp4
    # Manifest: output/episodes/<topic>-<ts>-full.json
    # Đã render 1 video vào output/episodes

    uv run python -m episodes.cli <script_json> <tts_metadata_json> [<images_metadata_json>]

Không truyền metadata ảnh = dựng bằng video nền (assets/backgrounds/), stage 3
được bỏ hẳn. Khi đó thư mục video nền phải có video dùng được.
    # Đã render tập 1/3: output/episodes/<trope>-<ts>-ep-01.mp4
    # Đã render tập 2/3: ...
    # Manifest: output/episodes/<trope>-<ts>-episodes.json
    # Đã render 3 tập vào output/episodes

Mỗi tập = cold open (đoạn cao trào cắt từ chương cuối tập) + các chương của tập
+ card kết kêu gọi tập sau. Xem episodes/plan.py (vì sao chia tập) và
episodes/cutter.py (vì sao cold open). Dùng lại composition MainVideo của
Remotion với vài props tuỳ chọn thêm, nên video/cli.py cũ vẫn chạy được nếu
muốn dựng bản full.
"""

import argparse
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from episodes.audio_build import build_episode_wav
from episodes.cutter import plan_cuts
from episodes.full import full_outro_text, plan_full_cut, suggest_same_topic
from episodes.plan import plan_episodes
from episodes import backgrounds, music
from episodes.props_builder import build_episode_props, chapter_lines
from episodes.storage import (
    episode_audio_path,
    episode_stem,
    episode_video_path,
    full_stem,
    make_stem,
    save_episode_props,
    save_manifest,
)
from scripts.models import Script

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "episodes"
METADATA_INDEX_JSONL = REPO_ROOT / "output" / "metadata" / "index.jsonl"
TOPICS_HISTORY = REPO_ROOT / "output" / "topics_history.json"


class EpisodeRenderError(Exception):
    pass


def _render(props_path: Path, output_path: Path) -> None:
    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        "MainVideo",
        str(output_path),
        f"--props={props_path}",
        f"--public-dir={REPO_ROOT}",
        f"--jpeg-quality={backgrounds.RENDER_JPEG_QUALITY}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REMOTION_DIR)
    if result.returncode != 0:
        raise EpisodeRenderError(
            f"Lỗi khi render {output_path.name} bằng Remotion: {result.stderr or result.stdout}"
        )
    if not output_path.exists():
        raise EpisodeRenderError(
            f"Remotion trả về mã thành công nhưng không thấy file video tại {output_path}"
        )


def _run(
    script_path: Path, tts_metadata_path: Path, images_metadata_path: Path | None, fmt: str | None = None
) -> Path:
    tts_metadata_path = tts_metadata_path.resolve()
    if images_metadata_path is not None:
        images_metadata_path = images_metadata_path.resolve()

    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))
    images_metadata = (
        json.loads(images_metadata_path.read_text(encoding="utf-8"))
        if images_metadata_path is not None
        else None
    )

    source_wav = tts_metadata_path.with_suffix(".wav")
    if not source_wav.exists():
        raise EpisodeRenderError(
            f"Không tìm thấy wav nguồn tại {source_wav} (suy ra từ {tts_metadata_path})."
        )
    images_dir = images_metadata_path.parent if images_metadata_path is not None else None

    # Không truyền --format thì theo kịch bản (stage 1 ghi format), rồi mới tới
    # mặc định cũ "episodes" -- để lệnh gọi tay trên kịch bản cũ không đổi hành vi.
    fmt = fmt or script.format or "episodes"
    stem = make_stem(script.trope)
    if fmt == "full":
        cuts = [plan_full_cut(tts_metadata, len(script.chapters), script.short_beats)]
        suggestion = suggest_same_topic(script.topic, script.title, METADATA_INDEX_JSONL, TOPICS_HISTORY)
        label_override: str | None = ""
        outro_override: str | None = full_outro_text(script.comment_question, suggestion)
    else:
        cuts = plan_cuts(tts_metadata, plan_episodes(len(script.chapters)))
        label_override = None
        outro_override = None
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_episodes: list[dict] = []
    for cut in cuts:
        ep = cut.episode
        ep_stem = full_stem(stem) if fmt == "full" else episode_stem(stem, ep.number)
        audio_path = episode_audio_path(ep_stem, OUTPUT_DIR)
        output_path = episode_video_path(ep_stem, OUTPUT_DIR)

        duration = build_episode_wav(source_wav, cut, audio_path)
        props = build_episode_props(
            script,
            tts_metadata,
            images_metadata,
            cut,
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=REPO_ROOT,
            episode_label=label_override,
            outro=outro_override,
        )
        # Video nền thay ảnh tĩnh nếu assets/backgrounds/ có video; trống thì
        # props giữ nguyên và Remotion dựng bằng ảnh như trước. Seed là stem
        # của tập (đã mang dấu thời gian) nên mỗi tập một nền ngẫu nhiên.
        nen = backgrounds.choose(seed=ep_stem)
        if nen:
            props.update(nen)
        elif images_metadata is None:
            # Bỏ stage 3 mà video nền lại không dùng được: render tiếp là ra
            # 40 phút màn hình đen giữa hai tấm thương hiệu. Dừng ở đây.
            raise EpisodeRenderError(
                "Không có ảnh (đã bỏ stage 3) mà cũng không có video nền dùng được trong "
                f"{backgrounds.BACKGROUND_DIR}. Thêm video .mp4 vào đó, hoặc chạy stage 3 "
                "rồi truyền metadata ảnh."
            )
        # Nhạc nền nhẹ (09/11, thử nghiệm): chỉ khi AUDIOBOOK_BGM bật; mặc định tắt.
        nhac = music.choose(seed=ep_stem, repo_root=REPO_ROOT)
        if nhac:
            props.update(nhac)
        props_path = save_episode_props(ep_stem, props, OUTPUT_DIR)
        _render(props_path, output_path)

        manifest_episodes.append(
            {
                "number": ep.number,
                "total": ep.total,
                "first_chapter": ep.first_chapter,
                "last_chapter": ep.last_chapter,
                "video_path": str(output_path),
                "audio_path": str(audio_path),
                "props_path": str(props_path),
                "duration_seconds": round(duration, 3),
                "cold_open_seconds": round(props["coldOpenSeconds"], 3),
                "chapters": chapter_lines(cut, script, tts_metadata),
            }
        )
        if fmt == "full":
            print(f"Đã render video full: {output_path}")
        else:
            print(f"Đã render tập {ep.number}/{ep.total}: {output_path}")

    manifest = {
        "trope": script.trope,
        "topic": script.topic,
        "format": fmt,
        "title": script.title,
        "hook": script.hook,
        "comment_question": script.comment_question,
        "script_path": str(script_path.resolve()),
        "episodes": manifest_episodes,
    }
    path = save_manifest(stem, manifest, OUTPUT_DIR, fmt)
    print(f"Manifest: {path}")
    unit = "video" if fmt == "full" else "tập"
    print(f"Đã render {len(manifest_episodes)} {unit} vào {OUTPUT_DIR}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Dựng từng tập 15-20 phút bằng Remotion.")
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("tts_metadata_path", help="Đường dẫn file JSON metadata TTS")
    parser.add_argument(
        "images_metadata_path",
        nargs="?",
        default=None,
        help="Metadata ảnh của stage 3. Bỏ trống = dựng bằng video nền (assets/backgrounds/)",
    )
    parser.add_argument(
        "--format",
        choices=("full", "episodes"),
        default=None,
        help="full = 1 video cả truyện; episodes = 3 tập. Mặc định: theo kịch bản, rồi 'episodes'.",
    )
    args = parser.parse_args()
    _run(
        Path(args.script_path),
        Path(args.tts_metadata_path),
        Path(args.images_metadata_path) if args.images_metadata_path else None,
        args.format,
    )


if __name__ == "__main__":
    main()
