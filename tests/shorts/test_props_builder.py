# tests/shorts/test_props_builder.py
from pathlib import Path

import pytest

from scripts.models import Chapter, Script
from shorts.excerpt import ShortExcerpt
from shorts.props_builder import ShortPropsBuildError, build_short_props
from tts.audio_postprocess import ChapterTiming


def _script() -> Script:
    return Script(
        trope="trong_sinh_bao_thu",
        title="Trọng Sinh Báo Thù",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="..."),
            Chapter(index=2, heading="Chương 2", text="..."),
        ],
    )


def _excerpt() -> ShortExcerpt:
    return ShortExcerpt(
        chapter_index=2,
        hook_text="CÔ ẤY BIẾT HẾT RỒI",
        excerpt_text="Cô ấy đến. Trời mưa.",
        short_title="Tiêu đề short",
        short_description="Mô tả short #shorts",
    )


def _images_metadata() -> dict:
    return {
        "trope": "trong_sinh_bao_thu",
        "title": "Trọng Sinh Báo Thù",
        "chapters": [
            {"index": 1, "filename": "anh-1.png", "scene_description": "..."},
            {"index": 2, "filename": "anh-2.png", "scene_description": "..."},
        ],
    }


def _timings() -> list[ChapterTiming]:
    return [
        ChapterTiming(index=1, heading="Câu 1", start_seconds=0.0, end_seconds=2.5),
        ChapterTiming(index=2, heading="Câu 2", start_seconds=2.65, end_seconds=5.0),
    ]


def _setup_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path
    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-1.png").write_bytes(b"x")
    (images_dir / "anh-2.png").write_bytes(b"x")

    audio_dir = repo_root / "output" / "shorts"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "trong_sinh_bao_thu-20260822T010000Z.wav"
    audio_path.write_bytes(b"x")

    return repo_root, images_dir, audio_path


def test_props_dung_anh_cua_chuong_duoc_chon(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    props = build_short_props(
        script=_script(),
        excerpt=_excerpt(),
        sentences=["Cô ấy đến.", "Trời mưa."],
        timings=_timings(),
        images_metadata=_images_metadata(),
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=repo_root,
    )

    assert props["imagePath"] == "output/images/anh-2.png"
    assert props["audioPath"] == "output/shorts/trong_sinh_bao_thu-20260822T010000Z.wav"
    assert props["hookText"] == "CÔ ẤY BIẾT HẾT RỒI"
    assert props["title"] == "Trọng Sinh Báo Thù"
    assert props["trope"] == "trong_sinh_bao_thu"


def test_moi_cau_giu_dung_moc_thoi_gian_that(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    props = build_short_props(
        script=_script(),
        excerpt=_excerpt(),
        sentences=["Cô ấy đến.", "Trời mưa."],
        timings=_timings(),
        images_metadata=_images_metadata(),
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=repo_root,
    )

    assert props["captions"] == [
        {"text": "Cô ấy đến.", "startSeconds": 0.0, "endSeconds": 2.5},
        {"text": "Trời mưa.", "startSeconds": 2.65, "endSeconds": 5.0},
    ]
    assert props["audioDurationSeconds"] == 5.0
    assert props["ctaSeconds"] == 4.0


def test_lech_so_cau_va_so_moc_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    with pytest.raises(ShortPropsBuildError, match="không khớp"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=["Chỉ một câu."],
            timings=_timings(),
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_khong_co_anh_cho_chuong_do_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    images_metadata = _images_metadata()
    images_metadata["chapters"] = [images_metadata["chapters"][0]]

    with pytest.raises(ShortPropsBuildError, match="chương 2"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=["Cô ấy đến.", "Trời mưa."],
            timings=_timings(),
            images_metadata=images_metadata,
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_file_anh_khong_ton_tai_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    (images_dir / "anh-2.png").unlink()

    with pytest.raises(ShortPropsBuildError, match="Không tìm thấy file ảnh"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=["Cô ấy đến.", "Trời mưa."],
            timings=_timings(),
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_khong_co_cau_nao_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    with pytest.raises(ShortPropsBuildError, match="Không có câu nào"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=[],
            timings=[],
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )
