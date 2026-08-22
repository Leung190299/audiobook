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


def _sentence(chapter_index, index, text, start, end):
    return {
        "chapter_index": chapter_index,
        "index": index,
        "text": text,
        "start_seconds": start,
        "end_seconds": end,
    }


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
        "sentences": [
            _sentence(1, 1, "Cau mot.", 0.0, 1.0),
            _sentence(1, 2, "Cau hai.", 1.0, 2.0),
            _sentence(2, 1, "Cau ba.", 2.5, 4.5),
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
        "startSeconds": 0.0,
        "endSeconds": 2.0,
        "imagePath": str(Path("output/images/demo-chapter-1.png")),
        "sentences": [
            {"text": "Cau mot.", "startSeconds": 0.0, "endSeconds": 1.0},
            {"text": "Cau hai.", "startSeconds": 1.0, "endSeconds": 2.0},
        ],
    }
    assert props["chapters"][1]["imagePath"] == str(Path("output/images/demo-chapter-2.png"))
    assert props["chapters"][1]["sentences"] == [
        {"text": "Cau ba.", "startSeconds": 2.5, "endSeconds": 4.5},
    ]


def test_build_video_props_keeps_sentences_on_whole_episode_timeline():
    # Chương 2 bắt đầu ở giây 100 trên trục toàn tập -- mốc câu của nó phải
    # giữ nguyên giá trị đó, không bị trừ về 0 (gốc chương).
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 100.0},
            {"index": 2, "heading": "Chuong 2", "start_seconds": 100.0, "end_seconds": 110.0},
        ],
        "sentences": [
            _sentence(1, 1, "Cau mot.", 0.0, 100.0),
            _sentence(2, 1, "Cau hai.", 100.0, 105.0),
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

    props = build_video_props(
        script,
        tts_metadata,
        images_metadata,
        audio_path=Path("/repo/a.wav"),
        images_dir=Path("/repo/images"),
        repo_root=Path("/repo"),
    )

    assert props["chapters"][1]["sentences"] == [
        {"text": "Cau hai.", "startSeconds": 100.0, "endSeconds": 105.0},
    ]


def test_build_video_props_raises_on_missing_sentences_key():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0},
            {"index": 2, "heading": "Chuong 2", "start_seconds": 2.5, "end_seconds": 4.5},
        ],
        # Không có "sentences" -- metadata dựng trước khi stage 2 ghi mốc câu.
    }
    images_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "chapters": [
            {"index": 1, "filename": "a.png", "scene_description": "a"},
            {"index": 2, "filename": "b.png", "scene_description": "b"},
        ],
    }

    with pytest.raises(PropsBuildError, match="chạy lại stage 2"):
        build_video_props(
            script,
            tts_metadata,
            images_metadata,
            audio_path=Path("/repo/a.wav"),
            images_dir=Path("/repo/images"),
            repo_root=Path("/repo"),
        )


def test_build_video_props_raises_on_chapter_without_sentences():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0},
            {"index": 2, "heading": "Chuong 2", "start_seconds": 2.5, "end_seconds": 4.5},
        ],
        "sentences": [
            _sentence(1, 1, "Cau mot.", 0.0, 2.0),
            # Chương 2 không có câu nào.
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

    with pytest.raises(PropsBuildError, match="chạy lại stage 2"):
        build_video_props(
            script,
            tts_metadata,
            images_metadata,
            audio_path=Path("/repo/a.wav"),
            images_dir=Path("/repo/images"),
            repo_root=Path("/repo"),
        )


def test_build_video_props_raises_on_title_mismatch():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "TIEU DE KHAC",
        "sample_rate": 24000,
        "chapters": [],
        "sentences": [],
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
        "sentences": [_sentence(1, 1, "Cau mot.", 0.0, 2.0)],
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
