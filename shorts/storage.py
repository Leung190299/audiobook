# shorts/storage.py
"""Lưu output của stage short: mỗi phần một bộ bốn file cùng chung một tên gốc.

Khác `tts/storage.py` và `video/storage.py` ở chỗ: timestamp được sinh MỘT LẦN
qua `make_stem()` rồi truyền vào `part_stem()` cho từng phần, để cả .wav/.mp4/
-props.json/.txt của cùng một lượt chạy dùng chung một gốc tên, chỉ khác số
phần. Nếu mỗi hàm tự sinh timestamp thì các phần sẽ lệch nhau vài giây và rất
khó ghép lại khi cần lần vết.

Số phần đệm hai chữ số (`part-07`, không phải `part-7`) để sắp xếp theo tên file
(ls, file explorer, ...) ra đúng thứ tự phần thay vì thứ tự chữ cái (1, 10, 11,
..., 2, 20, ...).
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def make_stem(trope: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{trope}-{timestamp}"


def part_stem(stem: str, number: int) -> str:
    # Đệm cứng hai chữ số: từ phần 100 trở đi thì "part-100" sắp trước "part-99"
    # theo thứ tự chữ cái, làm rối cả thư mục. Một tập ra ~30 phần, chạm 100 nghĩa
    # là có gì đó sai từ trước — dừng lại còn hơn đẻ ra đống file xếp sai.
    if not 1 <= number <= 99:
        raise ValueError(f"Số phần phải nằm trong khoảng 1-99, nhận được {number}")
    return f"{stem}-part-{number:02d}"


def save_short_props(part_stem: str, props: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{part_stem}-props.json"
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def short_audio_path(part_stem: str, output_dir: Path) -> Path:
    return output_dir / f"{part_stem}.wav"


def short_video_path(part_stem: str, output_dir: Path) -> Path:
    return output_dir / f"{part_stem}.mp4"


def short_thumbnail_path(part_stem: str, output_dir: Path) -> Path:
    # JPEG chứ không PNG: YouTube từ chối thumbnail lớn hơn 2MB, mà PNG của một
    # khung 1080x1920 kiểu tranh vẽ luôn nặng 2.2-2.3MB. Đo thật ở series đầu
    # tiên: cả 6 phần đều bị bỏ qua thumbnail vì lý do đó.
    return output_dir / f"{part_stem}.jpg"


# Tags cố định, giống nhau cho mọi phần của mọi series -- một series thì tính
# nhất quán quan trọng hơn tối ưu SEO từng phần riêng lẻ. upload/series_cli.py
# đọc thẳng danh sách này qua .json, không cần đoán hay tự sinh tag.
SHORT_TAGS = [
    "truyện audio",
    "truyện trọng sinh",
    "nghe truyện",
    "shorts",
    "truyện đêm khuya",
]


def save_short_metadata(
    part_stem: str,
    trope: str,
    episode_title: str,
    number: int,
    total: int,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Ghi cả `.txt` (đọc tay) lẫn `.json` (upload/series_cli.py đọc máy) cho
    một phần, cùng nội dung tiêu đề/mô tả. Trả về (txt_path, json_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    part_label = f"Trích đoạn {number}/{total}"
    title = f"{episode_title} — {part_label}"
    description = (
        f"{title}.\n"
        "Nghe trọn tập trên kênh — link ở phần mô tả kênh.\n"
        "#shorts #TruyenAudio"
    )
    video_filename = f"{part_stem}.mp4"

    txt_path = output_dir / f"{part_stem}.txt"
    txt_path.write_text(
        f"TIÊU ĐỀ:\n{title}\n\n"
        f"MÔ TẢ:\n{description}\n\n"
        f"TÊN FILE VIDEO:\n{video_filename}\n",
        encoding="utf-8",
    )

    json_path = output_dir / f"{part_stem}.json"
    json_path.write_text(
        json.dumps(
            {
                "trope": trope,
                "title": title,
                "description": description,
                "tags": SHORT_TAGS,
                "part_number": number,
                "total_parts": total,
                "video_filename": video_filename,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return txt_path, json_path
