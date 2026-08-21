# tests/scripts/test_cli.py
import json
from unittest.mock import AsyncMock

from scripts import cli
from scripts.models import Chapter, Script
from scripts.trope_bank import Trope


def test_main_generates_validates_and_saves_script(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "CONFIG_PATH", tmp_path / "tropes.yaml")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_trope = Trope(id="demo", name="Demo", description="Mô tả demo")
    monkeypatch.setattr(cli, "get_trope", lambda path, trope_id: fake_trope)

    fake_script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung " * 10)],
    )
    monkeypatch.setattr(cli, "generate_script", AsyncMock(return_value=fake_script))

    validated_scripts = []
    monkeypatch.setattr(cli, "validate_script", validated_scripts.append)

    monkeypatch.setattr("sys.argv", ["cli.py", "demo"])
    cli.main()

    assert validated_scripts == [fake_script]
    saved_files = list((tmp_path / "output").glob("*.json"))
    assert len(saved_files) == 1
    data = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"

    out = capsys.readouterr().out
    assert "Đã lưu kịch bản" in out


def test_main_generates_from_idea_file_without_trope_lookup(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "CONFIG_PATH", tmp_path / "tropes.yaml")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    def _fail_get_trope(path, trope_id):
        raise AssertionError("get_trope không được gọi khi dùng --idea-file")

    monkeypatch.setattr(cli, "get_trope", _fail_get_trope)

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("  Trọng sinh làm sát thủ báo thù nhà giàu  \n", encoding="utf-8")

    fake_script = Script(
        trope="idea",
        title="Tiêu đề từ ý tưởng",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung " * 10)],
    )
    generate_mock = AsyncMock(return_value=fake_script)
    monkeypatch.setattr(cli, "generate_script", generate_mock)
    monkeypatch.setattr(cli, "validate_script", lambda script: None)

    monkeypatch.setattr("sys.argv", ["cli.py", "--idea-file", str(idea_file)])
    cli.main()

    generate_mock.assert_awaited_once_with(
        "idea",
        "Trọng sinh làm sát thủ báo thù nhà giàu",
        "Trọng sinh làm sát thủ báo thù nhà giàu",
    )
    saved_files = list((tmp_path / "output").glob("*.json"))
    assert len(saved_files) == 1

    out = capsys.readouterr().out
    assert "Đã lưu kịch bản" in out


def test_label_chi_doi_ten_file_khong_doi_noi_dung(tmp_path, monkeypatch):
    """--label đặt nhãn thể loại cho lượt chạy bắt trend, nội dung vẫn từ idea file."""
    monkeypatch.setattr(cli, "CONFIG_PATH", tmp_path / "tropes.yaml")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("Mẹ chồng giấu sổ đỏ", encoding="utf-8")

    fake_script = Script(
        trope="me_chong_giau_so_do",
        title="Tiêu đề",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung " * 10)],
    )
    generate_mock = AsyncMock(return_value=fake_script)
    monkeypatch.setattr(cli, "generate_script", generate_mock)
    monkeypatch.setattr(cli, "validate_script", lambda script: None)

    monkeypatch.setattr(
        "sys.argv",
        ["cli.py", "--idea-file", str(idea_file), "--label", "me_chong_giau_so_do"],
    )
    cli.main()

    generate_mock.assert_awaited_once_with(
        "me_chong_giau_so_do", "Mẹ chồng giấu sổ đỏ", "Mẹ chồng giấu sổ đỏ"
    )
    saved = list((tmp_path / "output").glob("*.json"))
    assert len(saved) == 1
    # Tên file phải mang nhãn để lần lại được tập nào là tập nào khi chạy tự động.
    assert saved[0].name.startswith("me_chong_giau_so_do-")
