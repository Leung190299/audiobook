import json

from scripts.models import Chapter, Script
from scripts.storage import save_script


def test_save_script_writes_json_file(tmp_path):
    script = Script(
        trope="test_trope",
        title="Tiêu đề",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung")],
    )

    out_path = save_script(script, tmp_path)

    assert out_path.exists()
    assert out_path.parent == tmp_path
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề"
    assert data["trope"] == "test_trope"


def test_save_script_creates_output_dir_if_missing(tmp_path):
    script = Script(trope="t", title="T", chapters=[Chapter(1, "C1", "nội dung")])
    missing_dir = tmp_path / "nested" / "output"

    out_path = save_script(script, missing_dir)

    assert out_path.exists()
