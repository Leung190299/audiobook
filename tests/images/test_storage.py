import json

from images.storage import save_chapter_images


def test_save_chapter_images_writes_pngs_and_metadata(tmp_path):
    images = [
        (1, "cozy living room at dusk", b"fake png bytes 1"),
        (2, "misty mountain valley at dawn", b"fake png bytes 2"),
    ]

    image_paths, metadata_path = save_chapter_images(
        trope="test_trope", title="Tiêu đề", images=images, output_dir=tmp_path
    )

    assert len(image_paths) == 2
    for path in image_paths:
        assert path.exists()
        assert path.suffix == ".png"

    assert metadata_path.exists()
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["trope"] == "test_trope"
    assert data["title"] == "Tiêu đề"
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["index"] == 1
    assert data["chapters"][0]["scene_description"] == "cozy living room at dusk"
    assert data["chapters"][0]["filename"] == image_paths[0].name


def test_save_chapter_images_creates_output_dir_if_missing(tmp_path):
    missing_dir = tmp_path / "nested" / "output"
    images = [(1, "a scene", b"bytes")]

    image_paths, _ = save_chapter_images(
        trope="t", title="T", images=images, output_dir=missing_dir
    )

    assert image_paths[0].exists()
