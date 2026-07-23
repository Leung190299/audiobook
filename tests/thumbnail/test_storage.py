# tests/thumbnail/test_storage.py
from thumbnail.storage import save_thumbnail


def test_save_thumbnail_writes_png(tmp_path):
    image_bytes = b"fake png bytes"

    output_path = save_thumbnail("demo", image_bytes, tmp_path)

    assert output_path.exists()
    assert output_path.suffix == ".png"
    assert "demo" in output_path.name
    assert output_path.read_bytes() == image_bytes


def test_save_thumbnail_creates_output_dir_if_missing(tmp_path):
    missing_dir = tmp_path / "nested" / "output"

    output_path = save_thumbnail("demo", b"bytes", missing_dir)

    assert output_path.exists()
