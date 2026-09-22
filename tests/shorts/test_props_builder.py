# tests/shorts/test_props_builder.py
from pathlib import Path

import pytest

from shorts.planner import PartCaption, ShortPart
from shorts.props_builder import ShortPropsBuildError, build_short_props

TROPE = "trong_sinh_bao_thu"
TITLE = "Trọng Sinh Báo Thù"


def _part(
    number: int = 2,
    chapter_index: int = 2,
    source_start_seconds: float = 110.0,
    source_end_seconds: float = 115.5,
) -> ShortPart:
    return ShortPart(
        number=number,
        chapter_index=chapter_index,
        heading="Chương 2: Cao trào",
        source_start_seconds=source_start_seconds,
        source_end_seconds=source_end_seconds,
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
            {"index": 1, "scenes": [
                {"number": 1, "start_seconds": 0.0, "end_seconds": 50.0,
                 "filename": "anh-1-1.png", "scene_description": "..."},
                {"number": 2, "start_seconds": 50.0, "end_seconds": 100.0,
                 "filename": "anh-1-2.png", "scene_description": "..."},
            ]},
            {"index": 2, "scenes": [
                {"number": 1, "start_seconds": 100.0, "end_seconds": 150.0,
                 "filename": "anh-2-1.png", "scene_description": "..."},
            ]},
        ],
    }


def _setup_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path
    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-1-1.png").write_bytes(b"x")
    (images_dir / "anh-1-2.png").write_bytes(b"x")
    (images_dir / "anh-2-1.png").write_bytes(b"x")

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

    assert props["imagePath"] == "output/images/anh-2-1.png"
    assert props["audioPath"] == "output/shorts/trong_sinh_bao_thu-20260822T010000Z-part-02.wav"
    assert props["hookText"] == "Chương 2: Cao trào"
    assert props["title"] == TITLE
    assert props["trope"] == TROPE


def test_phan_bat_dau_giua_chuong_lay_canh_dang_chieu(tmp_path):
    # Phần bắt đầu ở giây 70 của chương 1 -> cảnh 2 (50s-100s), không phải cảnh 1.
    props = _build(
        tmp_path,
        part=_part(chapter_index=1, source_start_seconds=70.0, source_end_seconds=95.0),
    )

    assert props["imagePath"] == "output/images/anh-1-2.png"


def test_metadata_anh_khong_co_scenes_thi_bao_chay_lai_stage_3(tmp_path):
    images_metadata = _images_metadata()
    images_metadata["chapters"][0] = {"index": 1, "filename": "anh-1.png", "scene_description": "..."}

    # Phần mặc định nằm ở chương 2 (còn nguyên "scenes") -- phải trỏ phần vào
    # đúng chương 1 vừa bị hỏng thì mới chạm nhánh lỗi đang kiểm tra.
    with pytest.raises(ShortPropsBuildError, match="chạy lại stage 3"):
        _build(tmp_path, part=_part(chapter_index=1), images_metadata=images_metadata)


def test_captions_lay_thang_tu_part_captions(tmp_path: Path):
    props = _build(tmp_path)

    assert props["captions"] == [
        {"text": "Cô ấy đến.", "startSeconds": 0.0, "endSeconds": 2.5},
        {"text": "Trời mưa.", "startSeconds": 2.65, "endSeconds": 5.5},
    ]
    assert props["audioDurationSeconds"] == pytest.approx(5.5)
    assert props["ctaSeconds"] == 4.0


def test_moi_trich_doan_deu_moi_ve_video_dai(tmp_path: Path):
    # Không còn "Xem phần N+1": short nay là mồi, đích duy nhất là tập đầy đủ.
    # Kiểm cả trích đoạn đầu, giữa và cuối để chắc không sót nhánh nào.
    for number in (1, 3, 5):
        props = _build(tmp_path / f"n{number}", part=_part(number=number), total_parts=5)

        assert props["ctaText"] == "Nghe trọn tập 1 trên kênh"


def test_part_label_dinh_dang_trich_doan(tmp_path: Path):
    for number in (1, 3, 5):
        props = _build(tmp_path / f"n{number}", part=_part(number=number), total_parts=5)

        assert props["partLabel"] == f"TRÍCH ĐOẠN {number}/5"


def test_khong_co_anh_cho_chuong_do_thi_bao_loi(tmp_path: Path):
    images_metadata = _images_metadata()
    images_metadata["chapters"] = [images_metadata["chapters"][0]]

    with pytest.raises(ShortPropsBuildError, match="chương 2"):
        _build(tmp_path, images_metadata=images_metadata)


def test_file_anh_khong_ton_tai_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    (images_dir / "anh-2-1.png").unlink()

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
    (images_dir / "anh-1-1.png").write_bytes(b"x")
    (images_dir / "anh-1-2.png").write_bytes(b"x")
    (images_dir / "anh-2-1.png").write_bytes(b"x")

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


def test_scenes_quy_ve_goc_phan_khi_phan_trai_qua_hai_canh(tmp_path):
    # Phần 30s-80s của chương 1 giao với cảnh 1 (0-50) và cảnh 2 (50-100).
    # Mốc quy về gốc phần: cảnh 1 chiếu 0-20, cảnh 2 chiếu 20-50.
    props = _build(
        tmp_path,
        part=_part(chapter_index=1, source_start_seconds=30.0, source_end_seconds=80.0),
    )

    assert props["scenes"] == [
        {"number": 1, "startSeconds": 0.0, "endSeconds": 20.0,
         "imagePath": "output/images/anh-1-1.png"},
        {"number": 2, "startSeconds": 20.0, "endSeconds": 50.0,
         "imagePath": "output/images/anh-1-2.png"},
    ]
    assert props["imagePath"] == "output/images/anh-1-1.png"


def test_scenes_mot_canh_phu_tron_phan(tmp_path):
    # Phần 110s-115.5s nằm gọn trong cảnh 1 chương 2 (100-150).
    props = _build(tmp_path)

    assert props["scenes"] == [
        {"number": 1, "startSeconds": 0.0, "endSeconds": 5.5,
         "imagePath": "output/images/anh-2-1.png"},
    ]


def test_scenes_khong_lay_canh_ket_thuc_dung_luc_phan_bat_dau(tmp_path):
    # Phần bắt đầu đúng giây 50 = lúc cảnh 1 kết thúc: chỉ lấy cảnh 2.
    props = _build(
        tmp_path,
        part=_part(chapter_index=1, source_start_seconds=50.0, source_end_seconds=60.0),
    )

    assert [s["number"] for s in props["scenes"]] == [2]
    assert props["imagePath"] == "output/images/anh-1-2.png"


def test_thieu_file_anh_cua_canh_thu_hai_thi_bao_loi(tmp_path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    (images_dir / "anh-1-2.png").unlink()

    with pytest.raises(ShortPropsBuildError, match="anh-1-2.png"):
        build_short_props(
            part=_part(chapter_index=1, source_start_seconds=30.0, source_end_seconds=80.0),
            total_parts=5,
            episode_title=TITLE,
            trope=TROPE,
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )
