# tests/shorts/test_storage.py
import json
import re
from pathlib import Path

import pytest

from shorts.storage import (
    make_stem,
    part_stem,
    save_short_metadata,
    save_short_props,
    short_audio_path,
    short_thumbnail_path,
    short_video_path,
)


def test_stem_gom_trope_va_timestamp_utc():
    stem = make_stem("trong_sinh_bao_thu")

    assert re.fullmatch(r"trong_sinh_bao_thu-\d{8}T\d{6}Z", stem)


def test_part_stem_dem_hai_chu_so_de_sap_xep_dung():
    stem = "trong_sinh_bao_thu-20260822T010000Z"

    assert part_stem(stem, 7) == f"{stem}-part-07"
    assert part_stem(stem, 30) == f"{stem}-part-30"
    assert part_stem(stem, 1) == f"{stem}-part-01"


def test_moi_file_cua_mot_phan_dung_chung_part_stem(tmp_path: Path):
    stem = part_stem("trong_sinh_bao_thu-20260822T010000Z", 7)

    props_path = save_short_props(stem, {"trope": "x"}, tmp_path)
    audio_path = short_audio_path(stem, tmp_path)
    video_path = short_video_path(stem, tmp_path)

    assert props_path.name == f"{stem}-props.json"
    assert audio_path.name == f"{stem}.wav"
    assert video_path.name == f"{stem}.mp4"


def test_short_thumbnail_path_dat_ten_dung_quy_tac(tmp_path: Path):
    stem = part_stem("trong_sinh_bao_thu-20260822T010000Z", 7)

    thumbnail_path = short_thumbnail_path(stem, tmp_path)

    assert thumbnail_path.name == f"{stem}.jpg"
    assert thumbnail_path.parent == tmp_path


def test_luu_props_giu_nguyen_tieng_viet(tmp_path: Path):
    props = {"hookText": "CÔ ẤY BIẾT HẾT RỒI"}
    stem = part_stem("abc-20260822T010000Z", 1)

    path = save_short_props(stem, props, tmp_path)

    assert json.loads(path.read_text(encoding="utf-8")) == props
    assert "CÔ ẤY BIẾT HẾT RỒI" in path.read_text(encoding="utf-8")


def test_file_metadata_du_bon_muc_va_dung_phan_n_tren_tong(tmp_path: Path):
    stem = part_stem("abc-20260822T010000Z", 7)

    txt_path, json_path = save_short_metadata(
        stem,
        trope="trong_sinh_bao_thu",
        episode_title="Trọng Sinh Báo Thù",
        number=7,
        total=30,
        output_dir=tmp_path,
    )

    content = txt_path.read_text(encoding="utf-8")
    assert txt_path.name == f"{stem}.txt"
    assert json_path.name == f"{stem}.json"
    assert "TIÊU ĐỀ:\nTrọng Sinh Báo Thù — Trích đoạn 7/30" in content
    assert "MÔ TẢ:\nTrọng Sinh Báo Thù — Trích đoạn 7/30." in content
    assert "Nghe trọn tập trên kênh — link ở phần mô tả kênh." in content
    # Không hashtag trong mô tả: YouTube xếp Shorts theo khung dọc và thời lượng,
    # còn "#TruyenAudio" chỉ làm mô tả trông như spam. Yêu cầu của người dùng 16/09.
    assert "#" not in content.split("MÔ TẢ:")[1].split("TÊN FILE VIDEO:")[0]
    assert f"TÊN FILE VIDEO:\n{stem}.mp4" in content


def test_file_metadata_phan_khac_nhau_ra_so_khac_nhau(tmp_path: Path):
    stem_1 = part_stem("abc-20260822T010000Z", 1)
    stem_2 = part_stem("abc-20260822T010000Z", 2)

    txt_path_1, _ = save_short_metadata(
        stem_1, trope="abc", episode_title="Tên Tập", number=1, total=12, output_dir=tmp_path
    )
    txt_path_2, _ = save_short_metadata(
        stem_2, trope="abc", episode_title="Tên Tập", number=2, total=12, output_dir=tmp_path
    )

    assert "Trích đoạn 1/12" in txt_path_1.read_text(encoding="utf-8")
    assert "Trích đoạn 2/12" in txt_path_2.read_text(encoding="utf-8")


def test_file_metadata_json_du_khoa_upload_cli_can(tmp_path: Path):
    stem = part_stem("trong_sinh_bao_thu-20260822T010000Z", 7)

    txt_path, json_path = save_short_metadata(
        stem,
        trope="trong_sinh_bao_thu",
        episode_title="Trọng Sinh Báo Thù",
        number=7,
        total=30,
        output_dir=tmp_path,
    )

    data = json.loads(json_path.read_text(encoding="utf-8"))
    txt_content = txt_path.read_text(encoding="utf-8")

    assert data["trope"] == "trong_sinh_bao_thu"
    assert data["title"] == "Trọng Sinh Báo Thù — Trích đoạn 7/30"
    assert data["part_number"] == 7
    assert data["total_parts"] == 30
    assert data["video_filename"] == f"{stem}.mp4"
    assert isinstance(data["tags"], list) and data["tags"]

    # description trong .json phải khớp đúng phần MÔ TẢ trong .txt (giữa "MÔ
    # TẢ:\n" và "\n\nTÊN FILE VIDEO:") -- upload/cli.py đọc "description" thẳng
    # từ .json, không được lệch với bản .txt cho người đọc tay.
    mo_ta_section = txt_content.split("MÔ TẢ:\n", 1)[1].split("\n\nTÊN FILE VIDEO:", 1)[0]
    assert data["description"] == mo_ta_section


def test_file_metadata_json_tags_giong_nhau_giua_cac_phan(tmp_path: Path):
    stem_1 = part_stem("abc-20260822T010000Z", 1)
    stem_2 = part_stem("abc-20260822T010000Z", 2)

    _, json_path_1 = save_short_metadata(
        stem_1, trope="abc", episode_title="Tên Tập", number=1, total=12, output_dir=tmp_path
    )
    _, json_path_2 = save_short_metadata(
        stem_2, trope="abc", episode_title="Tên Tập", number=2, total=12, output_dir=tmp_path
    )

    data_1 = json.loads(json_path_1.read_text(encoding="utf-8"))
    data_2 = json.loads(json_path_2.read_text(encoding="utf-8"))
    assert data_1["tags"] == data_2["tags"]


def test_tu_tao_thu_muc_neu_chua_co(tmp_path: Path):
    output_dir = tmp_path / "chua" / "ton" / "tai"

    path = save_short_props("abc-20260822T010000Z-part-01", {}, output_dir)

    assert path.exists()


def test_so_phan_ngoai_khoang_1_99_thi_bao_loi():
    # Từ phần 100 trở đi, "part-100" sắp trước "part-99" theo thứ tự chữ cái.
    with pytest.raises(ValueError, match="1-99"):
        part_stem("abc-20260823T010000Z", 100)

    with pytest.raises(ValueError, match="1-99"):
        part_stem("abc-20260823T010000Z", 0)
