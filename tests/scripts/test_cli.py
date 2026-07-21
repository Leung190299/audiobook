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
