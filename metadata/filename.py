import re
import unicodedata
from pathlib import Path


class VideoRenameError(Exception):
    pass


def slugify(title: str, max_length: int = 100) -> str:
    normalized = unicodedata.normalize("NFD", title)
    without_accents = "".join(
        c for c in normalized if unicodedata.category(c) != "Mn"
    )
    without_accents = without_accents.replace("Đ", "D").replace("đ", "d")
    lowered = without_accents.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")

    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug


def rename_video_file(video_path: Path, title: str) -> Path:
    """Đổi tên video sang slug của tiêu đề. Trùng tên thì thêm hậu tố -2, -3...

    Trước 05/10 trùng tên là ném lỗi, và lượt dựng truyện #9 sáng đó chết ở
    stage 6 sau gần 1 tiếng chỉ vì bản dựng #9 hôm 30/09 còn nằm đúng tên đó.
    Tên file chỉ để nhìn trên máy (tiêu đề YouTube là chuyện riêng), không đáng
    làm mất cả lượt dựng. Nhưng KHÔNG BAO GIỜ ghi đè file đang có: bản cũ có
    thể vẫn cần, xoá hay giữ là việc của người dùng.
    """
    slug = slugify(title)
    new_path = video_path.with_name(f"{slug}{video_path.suffix}")
    n = 2
    while new_path.exists() and new_path != video_path:
        new_path = video_path.with_name(f"{slug}-{n}{video_path.suffix}")
        n += 1
    if new_path != video_path:
        video_path.rename(new_path)
    return new_path
