import json

from video.storage import save_video_props


def test_save_video_props_writes_json(tmp_path):
    video_props = {
        "trope": "demo",
        "title": "T",
        "audioPath": "/a.wav",
        "sampleRate": 24000,
        "chapters": [],
    }

    props_path = save_video_props(video_props, tmp_path)

    assert props_path.exists()
    assert props_path.suffix == ".json"
    assert "demo" in props_path.name
    data = json.loads(props_path.read_text(encoding="utf-8"))
    assert data == video_props


def test_save_video_props_creates_output_dir_if_missing(tmp_path):
    missing_dir = tmp_path / "nested" / "output"
    video_props = {
        "trope": "t",
        "title": "T",
        "audioPath": "/a.wav",
        "sampleRate": 24000,
        "chapters": [],
    }

    props_path = save_video_props(video_props, missing_dir)

    assert props_path.exists()
