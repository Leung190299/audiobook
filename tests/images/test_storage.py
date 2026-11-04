import json

from images.scene_planner import ScenePlan
from images.storage import save_scene_images


def _scene(chapter, number, start, end):
    return ScenePlan(chapter, number, start, end, f"text {chapter}.{number}")


def test_save_scene_images_ghi_png_va_metadata_theo_chuong_va_canh(tmp_path):
    images = [
        (_scene(1, 1, 0.0, 50.0), "cozy living room at dusk", b"png 1.1"),
        (_scene(1, 2, 50.0, 100.0), "empty kitchen at night", b"png 1.2"),
        (_scene(2, 1, 100.0, 140.0), "misty valley at dawn", b"png 2.1"),
    ]

    image_paths, metadata_path = save_scene_images(
        trope="test_trope", title="Tiêu đề", images=images, output_dir=tmp_path
    )

    assert [p.name.split("-", 2)[2] for p in image_paths] == [
        "chapter-1-scene-1.png", "chapter-1-scene-2.png", "chapter-2-scene-1.png",
    ]
    assert image_paths[1].read_bytes() == b"png 1.2"

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["trope"] == "test_trope"
    assert data["title"] == "Tiêu đề"
    assert [c["index"] for c in data["chapters"]] == [1, 2]
    assert data["chapters"][0]["scenes"] == [
        {"number": 1, "start_seconds": 0.0, "end_seconds": 50.0,
         "filename": image_paths[0].name, "scene_description": "cozy living room at dusk"},
        {"number": 2, "start_seconds": 50.0, "end_seconds": 100.0,
         "filename": image_paths[1].name, "scene_description": "empty kitchen at night"},
    ]
    assert data["chapters"][1]["scenes"][0]["filename"] == image_paths[2].name


def test_save_scene_images_tao_thu_muc_neu_chua_co(tmp_path):
    missing_dir = tmp_path / "nested" / "output"

    image_paths, _ = save_scene_images(
        trope="t", title="T",
        images=[(_scene(1, 1, 0.0, 10.0), "a scene", b"bytes")],
        output_dir=missing_dir,
    )

    assert image_paths[0].exists()


def test_save_scene_images_sap_chuong_va_canh_theo_thu_tu_du_dau_vao_lon_xon(tmp_path):
    # Vẽ song song có thể trả kết quả theo thứ tự hoàn thành, không theo kịch bản.
    images = [
        (_scene(2, 1, 100.0, 140.0), "b", b"2.1"),
        (_scene(1, 2, 50.0, 100.0), "a2", b"1.2"),
        (_scene(1, 1, 0.0, 50.0), "a1", b"1.1"),
    ]

    _, metadata_path = save_scene_images(trope="t", title="T", images=images, output_dir=tmp_path)

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert [c["index"] for c in data["chapters"]] == [1, 2]
    assert [s["number"] for s in data["chapters"][0]["scenes"]] == [1, 2]
