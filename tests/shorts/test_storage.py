# tests/shorts/test_storage.py
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from shorts.excerpt import ShortExcerpt
from shorts.storage import (
    make_stem,
    save_short_audio,
    save_short_metadata,
    save_short_props,
    short_video_path,
)


def _excerpt() -> ShortExcerpt:
    return ShortExcerpt(
        chapter_index=2,
        hook_text="CÔ ẤY BIẾT HẾT RỒI",
        excerpt_text="Cô ấy đến.",
        short_title="Trọng sinh báo thù - đoạn gay cấn nhất",
        short_description="Nghe full trên kênh nhé. #shorts",
    )


def test_stem_gom_trope_va_timestamp_utc():
    stem = make_stem("trong_sinh_bao_thu")

    assert re.fullmatch(r"trong_sinh_bao_thu-\d{8}T\d{6}Z", stem)


def test_moi_file_dung_chung_mot_stem(tmp_path: Path):
    stem = "trong_sinh_bao_thu-20260822T010000Z"
    audio = np.zeros(2400, dtype=np.float32)

    audio_path = save_short_audio(stem, audio, 24000, tmp_path)
    props_path = save_short_props(stem, {"trope": "x"}, tmp_path)
    video_path = short_video_path(stem, tmp_path)

    assert audio_path.name == f"{stem}.wav"
    assert props_path.name == f"{stem}-props.json"
    assert video_path.name == f"{stem}.mp4"


def test_luu_audio_doc_lai_duoc(tmp_path: Path):
    audio = np.zeros(2400, dtype=np.float32)

    path = save_short_audio("abc-20260822T010000Z", audio, 24000, tmp_path)

    data, sample_rate = sf.read(path)
    assert sample_rate == 24000
    assert len(data) == 2400


def test_luu_props_giu_nguyen_tieng_viet(tmp_path: Path):
    props = {"hookText": "CÔ ẤY BIẾT HẾT RỒI"}

    path = save_short_props("abc-20260822T010000Z", props, tmp_path)

    assert json.loads(path.read_text(encoding="utf-8")) == props
    assert "CÔ ẤY BIẾT HẾT RỒI" in path.read_text(encoding="utf-8")


def test_file_metadata_du_bon_muc(tmp_path: Path):
    path = save_short_metadata(
        "abc-20260822T010000Z",
        _excerpt(),
        episode_title="Trọng Sinh Báo Thù",
        video_filename="abc-20260822T010000Z.mp4",
        output_dir=tmp_path,
    )

    content = path.read_text(encoding="utf-8")
    assert path.name == "abc-20260822T010000Z.txt"
    assert "TIÊU ĐỀ:\nTrọng sinh báo thù - đoạn gay cấn nhất" in content
    assert "MÔ TẢ:\nNghe full trên kênh nhé. #shorts" in content
    assert "TẬP ĐẦY ĐỦ:\nTrọng Sinh Báo Thù" in content
    assert "TÊN FILE VIDEO:\nabc-20260822T010000Z.mp4" in content


def test_tu_tao_thu_muc_neu_chua_co(tmp_path: Path):
    output_dir = tmp_path / "chua" / "ton" / "tai"

    path = save_short_props("abc-20260822T010000Z", {}, output_dir)

    assert path.exists()
