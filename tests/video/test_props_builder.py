from pathlib import Path

import pytest

from scripts.models import Chapter, Script
from video.props_builder import PropsBuildError, build_video_props


def _make_script():
    return Script(
        trope="demo",
        title="Tieu de demo",
        chapters=[
            Chapter(index=1, heading="Chuong 1", text="Noi dung mot."),
            Chapter(index=2, heading="Chuong 2", text="Noi dung hai."),
        ],
    )


def test_build_video_props_joins_all_sources():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0},
            {"index": 2, "heading": "Chuong 2", "start_seconds": 2.5, "end_seconds": 4.5},
        ],
    }
    images_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "chapters": [
            {"index": 1, "filename": "demo-chapter-1.png", "scene_description": "a"},
            {"index": 2, "filename": "demo-chapter-2.png", "scene_description": "b"},
        ],
    }

    repo_root = Path("/repo")
    props = build_video_props(
        script,
        tts_metadata,
        images_metadata,
        audio_path=Path("/repo/output/audio/demo.wav"),
        images_dir=Path("/repo/output/images"),
        repo_root=repo_root,
    )

    assert props["trope"] == "demo"
    assert props["title"] == "Tieu de demo"
    assert props["audioPath"] == str(Path("output/audio/demo.wav"))
    assert props["sampleRate"] == 24000
    assert len(props["chapters"]) == 2
    assert props["chapters"][0] == {
        "index": 1,
        "heading": "Chuong 1",
        "text": "Noi dung mot.",
        "startSeconds": 0.0,
        "endSeconds": 2.0,
        "imagePath": str(Path("output/images/demo-chapter-1.png")),
    }
    assert props["chapters"][1]["imagePath"] == str(Path("output/images/demo-chapter-2.png"))


def test_build_video_props_raises_on_title_mismatch():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "TIEU DE KHAC",
        "sample_rate": 24000,
        "chapters": [],
    }
    images_metadata = {"trope": "demo", "title": "Tieu de demo", "chapters": []}

    with pytest.raises(PropsBuildError, match="trope/title"):
        build_video_props(
            script,
            tts_metadata,
            images_metadata,
            audio_path=Path("/repo/a.wav"),
            images_dir=Path("/repo/images"),
            repo_root=Path("/repo"),
        )


def test_build_video_props_raises_on_missing_chapter():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0}
        ],
    }
    images_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "chapters": [
            {"index": 1, "filename": "a.png", "scene_description": "a"},
            {"index": 2, "filename": "b.png", "scene_description": "b"},
        ],
    }

    with pytest.raises(PropsBuildError, match="Thiếu chương"):
        build_video_props(
            script,
            tts_metadata,
            images_metadata,
            audio_path=Path("/repo/a.wav"),
            images_dir=Path("/repo/images"),
            repo_root=Path("/repo"),
        )
