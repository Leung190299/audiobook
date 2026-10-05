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


def test_rename_trung_ten_thi_them_hau_to_khong_ghi_de_khong_chet(tmp_path):
    """Sáng 05/10 lượt dựng truyện #9 chết ở stage 6 sau gần 1 tiếng, chỉ vì
    bản dựng #9 hôm 30/09 còn nằm đúng tên đó. Tên file chỉ để nhìn trên máy
    (tiêu đề YouTube là chuyện riêng) -- không đáng làm mất cả lượt dựng.

    Thuộc tính cũ vẫn giữ: KHÔNG BAO GIỜ ghi đè file đang có."""
    video_path = tmp_path / "phe_vat_nghich_tap-20260722T083627Z.mp4"
    video_path.write_bytes(b"fake video content")
    destination = tmp_path / "ke-phe-vat-mang-linh-hon-than-co.mp4"
    destination.write_bytes(b"existing video that should not be overwritten")

    new_path = rename_video_file(video_path, "Kẻ Phế Vật Mang Linh Hồn Thần Cổ")

    assert new_path.name == "ke-phe-vat-mang-linh-hon-than-co-2.mp4"
    assert new_path.read_bytes() == b"fake video content"
    assert destination.read_bytes() == b"existing video that should not be overwritten"
    assert not video_path.exists()


def test_rename_trung_nhieu_lan_thi_tang_dan_hau_to(tmp_path):
    for name in ("abc.mp4", "abc-2.mp4", "abc-3.mp4"):
        (tmp_path / name).write_bytes(b"cu")
    video_path = tmp_path / "moi.mp4"
    video_path.write_bytes(b"moi")

    assert rename_video_file(video_path, "abc").name == "abc-4.mp4"


def test_rename_dung_ten_cua_chinh_no_thi_giu_nguyen(tmp_path):
    """Chạy lại stage 6 trên video đã đổi tên rồi: đừng tự đổi thành -2."""
    video_path = tmp_path / "abc.mp4"
    video_path.write_bytes(b"x")

    assert rename_video_file(video_path, "abc") == video_path
