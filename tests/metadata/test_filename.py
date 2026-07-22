import pytest

from metadata.filename import VideoRenameError, rename_video_file, slugify


def test_slugify_removes_vietnamese_diacritics_and_punctuation():
    result = slugify("Kẻ Phế Vật Mang Linh Hồn Thần Cổ: Ngày Tôi Trở Lại!")

    assert result == "ke-phe-vat-mang-linh-hon-than-co-ngay-toi-tro-lai"


def test_slugify_handles_dinh_letter():
    assert slugify("Đứa Trẻ Bị Bỏ Rơi") == "dua-tre-bi-bo-roi"


def test_slugify_truncates_long_titles():
    long_title = "a " * 80  # 160 chars before slugify

    result = slugify(long_title, max_length=50)

    assert len(result) <= 50
    assert not result.endswith("-")


def test_rename_video_file_uses_slugified_title(tmp_path):
    video_path = tmp_path / "phe_vat_nghich_tap-20260722T083627Z.mp4"
    video_path.write_bytes(b"fake video content")

    new_path = rename_video_file(video_path, "Kẻ Phế Vật Mang Linh Hồn Thần Cổ")

    assert new_path.name == "ke-phe-vat-mang-linh-hon-than-co.mp4"
    assert new_path.exists()
    assert not video_path.exists()


def test_rename_video_file_refuses_to_overwrite_existing_destination(tmp_path):
    video_path = tmp_path / "phe_vat_nghich_tap-20260722T083627Z.mp4"
    video_path.write_bytes(b"fake video content")

    # Create an existing file at the destination slug path
    destination = tmp_path / "ke-phe-vat-mang-linh-hon-than-co.mp4"
    destination.write_bytes(b"existing video that should not be overwritten")

    # Should raise VideoRenameError instead of silently overwriting
    with pytest.raises(VideoRenameError):
        rename_video_file(video_path, "Kẻ Phế Vật Mang Linh Hồn Thần Cổ")

    # Verify the original video file still exists (rename did NOT happen)
    assert video_path.exists()
    assert video_path.read_bytes() == b"fake video content"

    # Verify the destination was not modified
    assert destination.exists()
    assert destination.read_bytes() == b"existing video that should not be overwritten"
