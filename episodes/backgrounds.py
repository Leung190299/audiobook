"""Video nền cho video dài: thay các ảnh tĩnh bằng một video lặp lại.

Thả file .mp4 vào assets/backgrounds/ là xong; mỗi tập tự bốc ngẫu nhiên một
video. Thư mục trống (hoặc mọi video đều hỏng) thì không đổi gì, video vẫn dựng
bằng ảnh của stage 3 như trước.

Video nằm ở Ô GIỮA khung hình, hai bên là tấm thương hiệu của kênh
(remotion/src/BrandedLayout.tsx). Ô giữa co giãn theo khổ video: video dọc
(phần lớn video Douyin) hiện trọn vẹn, không cắt; video ngang thì bị chặn ở 66%
bề ngang và cắt bớt hai mép.

Mỗi video nguồn được tiền xử lý MỘT lần bằng ffmpeg rồi cache vào
assets/backgrounds/.prepared/:
- Đưa về đúng chiều cao khung (576px, 30fps -- remotion/src/Root.tsx), giữ
  nguyên khổ. Nguồn 720x1280 mà để nguyên thì Remotion giải mã gấp 5 lần số
  điểm ảnh cần dùng, suốt 45 phút render.
- Bỏ tiếng gốc: nhạc nền Douyin lọt vào là đè lên giọng đọc.
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

# Khung video dài, phải khớp HEIGHT/FPS trong remotion/src/Root.tsx.
HEIGHT = 576
FPS = 30


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


def prepared_path(src: Path, height: int = HEIGHT) -> Path:
    # Khoá "-h576" khác bản đệm mờ cũ ("-1024x576"): đổi bố cục là bản cũ tự
    # bị bỏ qua, không dùng nhầm video có hai dải mờ vào ô giữa.
    return src.parent / CACHE_DIRNAME / f"{src.stem}-h{height}.mp4"


def needs_prepare(src: Path, out: Path) -> bool:
    """Chưa có bản cache, hoặc người dùng đã thay video nguồn cùng tên."""
    return not out.exists() or out.stat().st_mtime < src.stat().st_mtime


def ffmpeg_command(src: Path, out: Path, height: int, fps: int) -> list[str]:
    # scale=-2:H: bề rộng tự tính theo khổ VÀ làm tròn về số chẵn -- libx264
    # đòi kích thước chẵn, mà 576x1036 thu về 320,2px là lẻ.
    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-an",
        "-vf", f"scale=-2:{height},fps={fps},setsar=1,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-movflags", "+faststart",
        str(out),
    ]


def probe(path: Path) -> tuple[float, float]:
    """(thời lượng giây, tỉ lệ rộng/cao) của video đã chuẩn bị."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "format=duration:stream=width,height",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
        data = json.loads(out)
        stream = data["streams"][0]
        return float(data["format"]["duration"]), stream["width"] / stream["height"]
    except (subprocess.CalledProcessError, KeyError, IndexError, ValueError,
            ZeroDivisionError, json.JSONDecodeError) as exc:
        raise BackgroundError(f"Không đọc được thông tin {path.name}: {exc}") from exc


def prepare(src: Path, height: int = HEIGHT, fps: int = FPS) -> tuple[Path, float, float]:
    """Bản đã chuẩn bị của `src` (làm mới nếu cần), thời lượng giây, tỉ lệ khung."""
    out = prepared_path(src, height)
    if needs_prepare(src, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        # Ghi ra file tạm rồi đổi tên: ffmpeg chết giữa chừng thì không để lại
        # một bản cache cụt mà lần sau tưởng là dùng được.
        tmp = out.with_name(out.stem + ".tmp.mp4")
        print(f"Chuẩn bị video nền {src.name} -> {out.name} (chỉ làm một lần)")
        ket_qua = subprocess.run(
            ffmpeg_command(src, tmp, height, fps), capture_output=True, text=True
        )
        if ket_qua.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise BackgroundError(
                f"ffmpeg không xử lý được {src.name}: {ket_qua.stderr.strip()[-400:]}"
            )
        tmp.replace(out)
    seconds, aspect = probe(out)
    return out, seconds, aspect


def choose(
    directory: Path | None = None,
    seed: str = "",
    *,
    repo_root: Path | None = None,
    prepare: Callable[..., tuple[Path, float, float]] | None = None,
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
        out, seconds, aspect = prepare(src, HEIGHT, FPS)
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
        "backgroundVideoAspect": round(aspect, 4),
    }
