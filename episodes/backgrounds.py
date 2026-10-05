"""Video nền cho video dài: thay các ảnh tĩnh bằng một video lặp lại.

Thả file .mp4 vào assets/backgrounds/ là xong; mỗi tập tự bốc ngẫu nhiên một
video. Thư mục trống (hoặc mọi video đều hỏng) thì không đổi gì, video vẫn dựng
bằng ảnh của stage 3 như trước.

Mỗi video nguồn được tiền xử lý MỘT lần bằng ffmpeg rồi cache vào
assets/backgrounds/.prepared/:
- Đưa về đúng khung video dài (1024x576, 30fps -- remotion/src/Root.tsx).
- Video dọc (phần lớn video Douyin) không bị cắt cụt mà đặt giữa, hai bên là
  chính nó phóng to làm mờ. Cắt cho vừa khung ngang thì chỉ còn dải giữa ~32%
  chiều cao, lại phóng gần gấp đôi từ 576px nên nhoè.
- Bỏ tiếng gốc: nhạc nền Douyin lọt vào là đè lên giọng đọc.
Làm sẵn ở đây thay vì để Remotion xử lý mỗi khung hình: đệm mờ trong Remotion
là giải mã HAI lớp video suốt 45 phút render.
"""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
BACKGROUND_DIR = ROOT / "assets" / "backgrounds"
CACHE_DIRNAME = ".prepared"

# Khung video dài, phải khớp WIDTH/HEIGHT/FPS trong remotion/src/Root.tsx.
WIDTH = 1024
HEIGHT = 576
FPS = 30

# Độ mờ lớp nền hai bên. Đủ mờ để không tranh chỗ với video chính giữa.
BLUR = "boxblur=20:2"


class BackgroundError(Exception):
    pass


def list_sources(directory: Path | None = None) -> list[Path]:
    """Các video nguồn, sắp theo tên để kết quả chọn ổn định giữa các máy."""
    # Giải mặc định lúc gọi, không gắn lúc import: gắn lúc import thì
    # monkeypatch trong test không ăn, test đi đọc video thật trên đĩa.
    directory = directory or BACKGROUND_DIR
    if not directory.is_dir():
        return []
    return sorted(
        (
            p
            for p in directory.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".mp4"
            # Finder rải '._ten.mp4' khi chép từ ổ ngoài; ffmpeg đọc là lỗi.
            and not p.name.startswith(".")
        ),
        key=lambda p: p.name.lower(),
    )


def pick(sources: list[Path], seed: str) -> Path | None:
    """Bốc một video theo seed: cùng tập dựng lại ra cùng nền, tập khác thì
    ngẫu nhiên. Seed là stem của tập, vốn đã mang dấu thời gian."""
    if not sources:
        return None
    return random.Random(seed).choice(sources)


def prepared_path(src: Path, width: int = WIDTH, height: int = HEIGHT) -> Path:
    return src.parent / CACHE_DIRNAME / f"{src.stem}-{width}x{height}.mp4"


def needs_prepare(src: Path, out: Path) -> bool:
    """Chưa có bản cache, hoặc người dùng đã thay video nguồn cùng tên."""
    return not out.exists() or out.stat().st_mtime < src.stat().st_mtime


def ffmpeg_command(src: Path, out: Path, width: int, height: int, fps: int) -> list[str]:
    filtre = (
        "[0:v]split=2[nen][truoc];"
        f"[nen]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},{BLUR}[nenmo];"
        # force_divisible_by=2: libx264 đòi kích thước chẵn, mà 576x1036 thu về
        # 320,2px là lẻ.
        f"[truoc]scale={width}:{height}:force_original_aspect_ratio=decrease:"
        "force_divisible_by=2[truocthu];"
        f"[nenmo][truocthu]overlay=(W-w)/2:(H-h)/2,fps={fps},setsar=1,format=yuv420p"
    )
    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-an",
        "-filter_complex", filtre,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-movflags", "+faststart",
        str(out),
    ]


def probe_seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
        return float(json.loads(out)["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise BackgroundError(f"Không đọc được thời lượng {path.name}: {exc}") from exc


def prepare(src: Path, width: int = WIDTH, height: int = HEIGHT, fps: int = FPS) -> tuple[Path, float]:
    """Bản đã chuẩn bị của `src` (làm mới nếu cần) cùng thời lượng giây."""
    out = prepared_path(src, width, height)
    if needs_prepare(src, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        # Ghi ra file tạm rồi đổi tên: ffmpeg chết giữa chừng thì không để lại
        # một bản cache cụt mà lần sau tưởng là dùng được.
        tmp = out.with_name(out.stem + ".tmp.mp4")
        print(f"Chuẩn bị video nền {src.name} -> {out.name} (chỉ làm một lần)")
        ket_qua = subprocess.run(
            ffmpeg_command(src, tmp, width, height, fps), capture_output=True, text=True
        )
        if ket_qua.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise BackgroundError(
                f"ffmpeg không xử lý được {src.name}: {ket_qua.stderr.strip()[-400:]}"
            )
        tmp.replace(out)
    return out, probe_seconds(out)


def choose(
    directory: Path | None = None,
    seed: str = "",
    *,
    repo_root: Path | None = None,
    prepare: Callable[..., tuple[Path, float]] | None = None,
) -> dict | None:
    """Trường props cho Remotion, hoặc None nếu không có video nền dùng được.

    None nghĩa là dựng bằng ảnh như cũ -- một video nền hỏng không đáng làm
    mất cả lượt dựng một tiếng.
    """
    repo_root = repo_root or ROOT
    prepare = prepare or globals()["prepare"]
    src = pick(list_sources(directory), seed)
    if src is None:
        return None
    try:
        out, seconds = prepare(src, WIDTH, HEIGHT, FPS)
    except BackgroundError as exc:
        print(f"CẢNH BÁO: bỏ video nền, dựng bằng ảnh như cũ ({exc})")
        return None
    if seconds <= 0:
        print(f"CẢNH BÁO: video nền {out.name} dài 0 giây, dựng bằng ảnh như cũ")
        return None
    print(f"Video nền: {src.name}")
    return {
        "backgroundVideo": str(out.relative_to(repo_root)),
        "backgroundVideoSeconds": round(seconds, 3),
    }
