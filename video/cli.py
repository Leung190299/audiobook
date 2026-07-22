# video/cli.py
import argparse
import json
import subprocess
from pathlib import Path

from scripts.models import Script
from video.props_builder import build_video_props
from video.storage import save_video_props

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "video"


class VideoRenderError(Exception):
    pass


def _run(
    script_path: Path, tts_metadata_path: Path, images_metadata_path: Path
) -> Path:
    # Resolve to absolute before deriving audio_path/images_dir below --
    # build_video_props() computes paths via .relative_to(REPO_ROOT), which
    # requires both sides to be absolute (a relative input path here would
    # otherwise raise "not in the subpath of" even when it's really under
    # the repo root).
    tts_metadata_path = tts_metadata_path.resolve()
    images_metadata_path = images_metadata_path.resolve()

    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))
    images_metadata = json.loads(images_metadata_path.read_text(encoding="utf-8"))

    audio_path = tts_metadata_path.with_suffix(".wav")
    images_dir = images_metadata_path.parent

    video_props = build_video_props(
        script,
        tts_metadata,
        images_metadata,
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=REPO_ROOT,
    )
    props_path = save_video_props(video_props, OUTPUT_DIR)

    output_path = OUTPUT_DIR / f"{props_path.stem}.mp4"

    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        "MainVideo",
        str(output_path),
        f"--props={props_path}",
        f"--public-dir={REPO_ROOT}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REMOTION_DIR)

    if result.returncode != 0:
        raise VideoRenderError(
            f"Lỗi khi render video bằng Remotion: {result.stderr or result.stdout}"
        )

    if not output_path.exists():
        raise VideoRenderError(
            f"Lỗi: Remotion trả về mã thành công nhưng file video không được tạo tại {output_path}"
        )

    print(f"Đã render video vào {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dựng video hoàn chỉnh bằng Remotion."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("tts_metadata_path", help="Đường dẫn file JSON metadata TTS")
    parser.add_argument(
        "images_metadata_path", help="Đường dẫn file JSON metadata ảnh"
    )
    args = parser.parse_args()
    _run(
        Path(args.script_path),
        Path(args.tts_metadata_path),
        Path(args.images_metadata_path),
    )


if __name__ == "__main__":
    main()
