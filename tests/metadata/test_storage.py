import json

from metadata.seo_generator import SeoCopy
from metadata.storage import build_full_description, save_seo_metadata


def test_build_full_description_appends_cta_chapters_and_hashtags():
    result = build_full_description(
        "Mô tả truyện hấp dẫn.", ["0:00 Chương 1", "3:10 Chương 2"],
        hashtags=["#TruyenAudio", "#NgonTinh"],
    )

    assert result.startswith("Mô tả truyện hấp dẫn.")
    assert "Đăng ký kênh" in result
    assert "0:00 Chương 1" in result
    assert "3:10 Chương 2" in result
    # Hashtag ở dòng cuối cùng: YouTube tự lấy 3 cái đầu hiện trên tiêu đề, còn
    # phần đầu mô tả phải là văn xuôi để người xem đọc được.
    assert result.splitlines()[-1] == "#TruyenAudio #NgonTinh"


def test_build_full_description_khong_hashtag_thi_khong_them_dong_trong():
    result = build_full_description("Mô tả.", ["0:00 Chương 1"], hashtags=[])

    assert result.splitlines()[-1] == "0:00 Chương 1"


def test_save_seo_metadata_writes_txt_and_json(tmp_path):
    seo_copy = SeoCopy(
        title="Tiêu đề video",
        description_draft="Mô tả nháp.",
        tags=["tag1", "tag2"],
        hashtags=["#tag1", "#tag2"],
    )

    txt_path, json_path = save_seo_metadata(
        trope="demo",
        seo_copy=seo_copy,
        chapter_lines=["0:00 Chương 1"],
        new_video_filename="tieu-de-video.mp4",
        output_dir=tmp_path,
    )

    assert txt_path.exists()
    assert json_path.exists()

    txt_content = txt_path.read_text(encoding="utf-8")
    assert "Tiêu đề video" in txt_content
    assert "tag1, tag2" in txt_content

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề video"
    assert data["tags"] == ["tag1", "tag2"]
    assert data["video_filename"] == "tieu-de-video.mp4"
    # Hashtag phải nằm TRONG description -- đây là thứ upload/cli.py đưa lên
    # YouTube; trường "hashtags" riêng chỉ để đọc tay.
    assert data["description"].endswith("#tag1 #tag2")


def test_save_seo_metadata_creates_output_dir_if_missing(tmp_path):
    seo_copy = SeoCopy(title="T", description_draft="D", tags=["a"], hashtags=["#a"])
    output_dir = tmp_path / "nested" / "metadata"

    save_seo_metadata("demo", seo_copy, ["0:00 Chương 1"], "t.mp4", output_dir)

    assert output_dir.exists()
