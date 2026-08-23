# tests/shorts/test_props_builder.py
from pathlib import Path

import pytest

from shorts.planner import PartCaption, ShortPart
from shorts.props_builder import ShortPropsBuildError, build_short_props

TROPE = "trong_sinh_bao_thu"
TITLE = "Trọng Sinh Báo Thù"


def _part(number: int = 2, chapter_index: int = 2) -> ShortPart:
    return ShortPart(
        number=number,
        chapter_index=chapter_index,
        heading="Chương 2: Cao trào",
        source_start_seconds=90.0,
        source_end_seconds=95.5,
        captions=[
            PartCaption(text="Cô ấy đến.", start_seconds=0.0, end_seconds=2.5),
            PartCaption(text="Trời mưa.", start_seconds=2.65, end_seconds=5.5),
        ],
    )


def _images_metadata() -> dict:
    return {
        "trope": TROPE,
        "title": TITLE,
        "chapters": [
            {"index": 1, "filename": "anh-1.png", "scene_description": "..."},
            {"index": 2, "filename": "anh-2.png", "scene_description": "..."},
        ],
    }


def _setup_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path
    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-1.png").write_bytes(b"x")
    (images_dir / "anh-2.png").write_bytes(b"x")

    audio_dir = repo_root / "output" / "shorts"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / f"{TROPE}-20260822T010000Z-part-02.wav"
    audio_path.write_bytes(b"x")

    return repo_root, images_dir, audio_path


def _build(
    tmp_path: Path,
    part: ShortPart | None = None,
    total_parts: int = 5,
    images_metadata: dict | None = None,
) -> dict:
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    return build_short_props(
        part=part or _part(),
        total_parts=total_parts,
        episode_title=TITLE,
        trope=TROPE,
        images_metadata=images_metadata or _images_metadata(),
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=repo_root,
    )


def test_props_dung_anh_cua_chuong_chua_phan(tmp_path: Path):
    props = _build(tmp_path)

    assert props["imagePath"] == "output/images/anh-2.png"
    assert props["audioPath"] == "output/shorts/trong_sinh_bao_thu-20260822T010000Z-part-02.wav"
    assert props["hookText"] == "Chương 2: Cao trào"
    assert props["title"] == TITLE
    assert props["trope"] == TROPE


def test_captions_lay_thang_tu_part_captions(tmp_path: Path):
    props = _build(tmp_path)

    assert props["captions"] == [
        {"text": "Cô ấy đến.", "startSeconds": 0.0, "endSeconds": 2.5},
        {"text": "Trời mưa.", "startSeconds": 2.65, "endSeconds": 5.5},
    ]
    assert props["audioDurationSeconds"] == pytest.approx(5.5)
    assert props["ctaSeconds"] == 4.0


def test_cta_text_phan_giua_moi_sang_phan_ke_tiep(tmp_path: Path):
    part = _part(number=2)
    props = _build(tmp_path, part=part, total_parts=5)

    assert props["ctaText"] == "Xem phần 3"


def test_cta_text_phan_cuoi_moi_nghe_full(tmp_path: Path):
    part = _part(number=5)
    props = _build(tmp_path, part=part, total_parts=5)

    assert props["ctaText"] == "Nghe full trên kênh"


def test_part_label_dinh_dang_phan_dau(tmp_path: Path):
    part = _part(number=1)
    props = _build(tmp_path, part=part, total_parts=30)

    assert props["partLabel"] == "PHẦN 1/30"


def test_part_label_dinh_dang_phan_giua(tmp_path: Path):
    part = _part(number=15)
    props = _build(tmp_path, part=part, total_parts=30)

    assert props["partLabel"] == "PHẦN 15/30"


def test_part_label_dinh_dang_phan_cuoi(tmp_path: Path):
    part = _part(number=30)
    props = _build(tmp_path, part=part, total_parts=30)

    assert props["partLabel"] == "PHẦN 30/30"


def test_phan_duy_nhat_cua_tap_cung_la_phan_cuoi(tmp_path: Path):
    # total_parts == 1 và number == 1 -- phần duy nhất của tập cũng phải coi là
    # phần cuối, không được lỡ tay chào "Xem phần 2" (không tồn tại).
    part = _part(number=1)
    props = _build(tmp_path, part=part, total_parts=1)

    assert props["ctaText"] == "Nghe full trên kênh"


def test_khong_co_anh_cho_chuong_do_thi_bao_loi(tmp_path: Path):
    images_metadata = _images_metadata()
    images_metadata["chapters"] = [images_metadata["chapters"][0]]

    with pytest.raises(ShortPropsBuildError, match="chương 2"):
        _build(tmp_path, images_metadata=images_metadata)


def test_file_anh_khong_ton_tai_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    (images_dir / "anh-2.png").unlink()

    with pytest.raises(ShortPropsBuildError, match="Không tìm thấy file ảnh"):
        build_short_props(
            part=_part(),
            total_parts=5,
            episode_title=TITLE,
            trope=TROPE,
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_anh_ngoai_repo_root_bao_loi_dung_kieu_khong_phai_valueerror(tmp_path: Path):
    # image_path.relative_to(repo_root) tự nhiên bắn ValueError khi images_dir nằm
    # ngoài repo_root -- phải bọc lại thành ShortPropsBuildError của module này.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    images_dir = tmp_path / "ngoai_repo" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-1.png").write_bytes(b"x")
    (images_dir / "anh-2.png").write_bytes(b"x")

    audio_dir = repo_root / "output" / "shorts"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / f"{TROPE}-20260822T010000Z-part-02.wav"
    audio_path.write_bytes(b"x")

    with pytest.raises(ShortPropsBuildError, match="nằm ngoài repo"):
        build_short_props(
            part=_part(),
            total_parts=5,
            episode_title=TITLE,
            trope=TROPE,
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )
