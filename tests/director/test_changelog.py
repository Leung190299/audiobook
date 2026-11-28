from datetime import datetime

from director.changelog import record
from director.paths import VN


def test_record_ghi_mot_dong_tsv(tmp_path):
    line = record("config/keywords.yaml", "thêm hạt giống", "", "mẹ kế\nvay tiền",
                  now=datetime(2026, 11, 28, 8, 0, tzinfo=VN), log=tmp_path / "l.log")
    assert line.split("\t") == ["2026-11-28T08:00:00+07:00", "config/keywords.yaml", "thêm hạt giống", "", "mẹ kế\\nvay tiền"]
    assert (tmp_path / "l.log").read_text(encoding="utf-8") == line + "\n"


def test_record_noi_them_dong(tmp_path):
    record("a", "b", "1", "2", log=tmp_path / "l.log")
    record("a", "b", "2", "3", log=tmp_path / "l.log")
    assert (tmp_path / "l.log").read_text(encoding="utf-8").count("\n") == 2
