"""Fixture chung cho tests/episodes: một 'truyện' 6 chương, mỗi chương 8 câu x 3s
(24s/chương), wav thật đủ dài, ảnh giả, để plan_episodes(6) ra 3 tập 2 chương."""

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

TROPE = "trong_sinh_bao_thu"
TITLE = "Trọng Sinh Báo Thù"
SAMPLE_RATE = 24000
CHAPTER_COUNT = 6
SENTENCES_PER_CHAPTER = 8
SENTENCE_SECONDS = 3.0
CHAPTER_GAP = 0.5


def make_tts_metadata() -> dict:
    chapters, sentences = [], []
    t = 0.0
    for ci in range(1, CHAPTER_COUNT + 1):
        start = t
        for si in range(1, SENTENCES_PER_CHAPTER + 1):
            sentences.append(
                {
                    "chapter_index": ci,
                    "index": si,
                    "text": f"Câu {ci}.{si}.",
                    "start_seconds": t,
                    "end_seconds": t + SENTENCE_SECONDS,
                }
            )
            t += SENTENCE_SECONDS
        chapters.append(
            {"index": ci, "heading": f"Chương {ci}", "start_seconds": start, "end_seconds": t}
        )
        t += CHAPTER_GAP
    return {
        "trope": TROPE,
        "title": TITLE,
        "sample_rate": SAMPLE_RATE,
        "chapters": chapters,
        "sentences": sentences,
    }


def make_script_dict(hook: str = "Cô bị tráo phôi", question: str = "Bạn sẽ tha thứ chứ?") -> dict:
    return {
        "trope": TROPE,
        "title": TITLE,
        "hook": hook,
        "comment_question": question,
        "chapters": [
            {"index": ci, "heading": f"Chương {ci}", "text": "nội dung " * 50}
            for ci in range(1, CHAPTER_COUNT + 1)
        ],
    }


@pytest.fixture
def sandbox(tmp_path: Path):
    repo_root = tmp_path
    tts_metadata = make_tts_metadata()
    audio_dir = repo_root / "output" / "audio"
    audio_dir.mkdir(parents=True)
    tts_path = audio_dir / f"{TROPE}-20260922T000000Z.json"
    tts_path.write_text(json.dumps(tts_metadata, ensure_ascii=False), encoding="utf-8")
    total = tts_metadata["chapters"][-1]["end_seconds"] + 1.0
    # Sóng sin để test đọc được biên độ khác 0 ở đoạn thân tập.
    n = int(total * SAMPLE_RATE)
    wave = 0.5 * np.sin(np.linspace(0, 2 * np.pi * 440 * total, n)).astype("float32")
    sf.write(tts_path.with_suffix(".wav"), wave, SAMPLE_RATE)

    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    image_chapters = []
    for c in tts_metadata["chapters"]:
        mid = (c["start_seconds"] + c["end_seconds"]) / 2
        scenes = []
        for number, (s, e) in enumerate(
            [(c["start_seconds"], mid), (mid, c["end_seconds"])], start=1
        ):
            filename = f"{TROPE}-chapter-{c['index']}-scene-{number}.png"
            (images_dir / filename).write_bytes(b"png")
            scenes.append(
                {"number": number, "start_seconds": s, "end_seconds": e, "filename": filename}
            )
        image_chapters.append({"index": c["index"], "scenes": scenes})
    images_metadata = {"trope": TROPE, "title": TITLE, "chapters": image_chapters}
    images_path = images_dir / f"{TROPE}-20260922T000000Z.json"
    images_path.write_text(json.dumps(images_metadata, ensure_ascii=False), encoding="utf-8")

    script_path = repo_root / "output" / "scripts" / f"{TROPE}-20260922T000000Z.json"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(json.dumps(make_script_dict(), ensure_ascii=False), encoding="utf-8")

    return {
        "repo_root": repo_root,
        "tts_metadata": tts_metadata,
        "tts_path": tts_path,
        "wav_path": tts_path.with_suffix(".wav"),
        "images_metadata": images_metadata,
        "images_path": images_path,
        "images_dir": images_dir,
        "script_path": script_path,
    }
