# TTS Module (OmniVoice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the TTS module — script JSON (from the script-generation module) → per-chapter narration via OmniVoice (voice design, no cloning) → loudness-normalized, concatenated audio file with chapter timestamps — as sub-project 2 of the channel pipeline.

**Architecture:** A `tts/` Python package with clearly separated responsibilities: `voice_profile.py` (loads the voice config), `synthesizer.py` (wraps OmniVoice's `generate()` per chapter), `audio_postprocess.py` (loudness normalization + concatenation + timestamp tracking), `storage.py` (saves the final WAV + timestamp JSON), and `cli.py` (wires it all together). Automated tests never load the real OmniVoice model — they always inject a fake model object; only the final manual smoke-test step exercises the real model on real hardware.

**Tech Stack:** Python 3.11+ (existing `uv` project), [OmniVoice](https://github.com/k2-fsa/OmniVoice) (local TTS, Apple Silicon/MPS), `pyloudnorm` (ITU-R BS.1770 loudness normalization), `soundfile` (WAV I/O), `numpy`.

## Global Constraints

- Giọng đọc: **voice design** bằng mô tả text (không dùng voice cloning từ audio mẫu có sẵn).
- Hạ tầng: chạy **local trên Apple Silicon (MPS)**, không dùng GPU cloud trả phí.
- Module gộp cả TTS (đọc từng chương) và hậu kỳ (chuẩn hoá loudness + nối chương) — output là **một file audio hoàn chỉnh** kèm **một file JSON timestamp từng chương**.
- Nhạc nền/SFX: **ngoài phạm vi** module này.
- Test tự động **không được load model OmniVoice thật** — luôn dùng model giả (fake/mock), giống nguyên tắc "không tốn tài nguyên thật trong test" đã áp dụng cho module sinh kịch bản.
- Cấu hình giọng đọc tại `config/voice.yaml`: `instruction` (mô tả giọng), `target_lufs` (mức loudness mục tiêu), `sample_rate`, `gap_seconds` (khoảng lặng giữa chương).
- Input: file JSON kịch bản theo schema `Script.to_dict()` đã có từ module trước (`scripts/models.py`): `{"trope": str, "title": str, "chapters": [{"index": int, "heading": str, "text": str}, ...]}`.

---

### Task 1: Project setup for TTS module

**Files:**
- Modify: `pyproject.toml`
- Create: `config/voice.yaml`
- Create: `tts/__init__.py`
- Create: `tests/tts/__init__.py`

**Interfaces:**
- Consumes: nothing (first task of this plan).
- Produces: an importable `tts` package, `config/voice.yaml` for Task 2 to read, and an environment with `omnivoice`, `torch`, `pyloudnorm`, `soundfile` installed for later tasks.

- [ ] **Step 1: Add TTS dependencies to `pyproject.toml`**

Update the existing `dependencies` list under `[project]` to (keep every existing entry, only add the four new ones):

```toml
dependencies = [
    "gemini-webapi>=1.0.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "omnivoice>=0.1.0",
    "torch>=2.0.0",
    "pyloudnorm>=0.1.1",
    "soundfile>=0.12.1",
]
```

- [ ] **Step 2: Run `uv sync` and verify it succeeds**

Run: `uv sync`
Expected: installs `omnivoice`, `torch`, `pyloudnorm`, `soundfile` and their dependencies with no errors. This can take several minutes — `torch` is a large download.

- [ ] **Step 3: Create `config/voice.yaml`**

```yaml
instruction: "giọng nữ, ấm áp, tốc độ đọc vừa phải, ngữ điệu tự nhiên như đang kể chuyện cho người nghe"
target_lufs: -16.0
sample_rate: 24000
gap_seconds: 0.5
```

- [ ] **Step 4: Create package directories and markers**

```bash
mkdir -p tts tests/tts output/audio
touch tts/__init__.py tests/tts/__init__.py
```

- [ ] **Step 5: Verify imports**

Run: `uv run python -c "import tts, torch, pyloudnorm, soundfile; from omnivoice import OmniVoice; print('ok')"`
Expected: prints `ok`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock config/voice.yaml tts/__init__.py tests/tts/__init__.py
git commit -m "chore: scaffold TTS module project (omnivoice, pyloudnorm, soundfile)"
```

---

### Task 2: Voice profile loader

**Files:**
- Create: `tts/voice_profile.py`
- Test: `tests/tts/test_voice_profile.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `VoiceProfile(instruction: str, target_lufs: float, sample_rate: int, gap_seconds: float)`; `load_voice_profile(path: Path) -> VoiceProfile`. Used by `tts/synthesizer.py` (Task 3, via a `VoiceProfile` argument) and `tts/cli.py` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# tests/tts/test_voice_profile.py
from tts.voice_profile import VoiceProfile, load_voice_profile


def test_load_voice_profile_reads_all_fields(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(
        "instruction: giọng nữ ấm áp\n"
        "target_lufs: -16.0\n"
        "sample_rate: 24000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile == VoiceProfile(
        instruction="giọng nữ ấm áp",
        target_lufs=-16.0,
        sample_rate=24000,
        gap_seconds=0.5,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tts/test_voice_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tts.voice_profile'`

- [ ] **Step 3: Write minimal implementation**

```python
# tts/voice_profile.py
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class VoiceProfile:
    instruction: str
    target_lufs: float
    sample_rate: int
    gap_seconds: float


def load_voice_profile(path: Path) -> VoiceProfile:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return VoiceProfile(
        instruction=data["instruction"],
        target_lufs=data["target_lufs"],
        sample_rate=data["sample_rate"],
        gap_seconds=data["gap_seconds"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tts/test_voice_profile.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add tts/voice_profile.py tests/tts/test_voice_profile.py
git commit -m "feat: add voice profile config loader"
```

---

### Task 3: Synthesizer (OmniVoice wrapper)

**Files:**
- Create: `tts/synthesizer.py`
- Test: `tests/tts/test_synthesizer.py`

**Interfaces:**
- Consumes: `Chapter` from `scripts/models.py` (existing: `Chapter(index: int, heading: str, text: str)`); `VoiceProfile` from `tts/voice_profile.py` (Task 2).
- Produces: `synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray` (raises `SynthesisError`). `model` is any object exposing `.generate(text: str, instruct: str) -> Sequence[np.ndarray]` (matches OmniVoice's real API — a fake in tests, the real `OmniVoice` instance in production). Used by `tts/cli.py` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# tests/tts/test_synthesizer.py
import numpy as np
import pytest

from scripts.models import Chapter
from tts.synthesizer import SynthesisError, synthesize_chapter
from tts.voice_profile import VoiceProfile


def _voice_profile() -> VoiceProfile:
    return VoiceProfile(
        instruction="giọng nữ ấm áp", target_lufs=-16.0, sample_rate=24000, gap_seconds=0.5
    )


class _FakeModel:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate(self, text, instruct):
        self.calls.append((text, instruct))
        return self.result


def test_synthesize_chapter_returns_audio_array():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel([fake_audio])

    audio = synthesize_chapter(chapter, model, _voice_profile())

    assert isinstance(audio, np.ndarray)
    assert audio.shape == (1000,)
    assert model.calls == [("Nội dung chương một.", "giọng nữ ấm áp")]


def test_synthesize_chapter_raises_synthesis_error_on_model_failure():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")

    class _FailingModel:
        def generate(self, text, instruct):
            raise RuntimeError("model crashed")

    with pytest.raises(SynthesisError, match="chương 1"):
        synthesize_chapter(chapter, _FailingModel(), _voice_profile())


def test_synthesize_chapter_raises_synthesis_error_on_unexpected_result_shape():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")
    model = _FakeModel(None)

    with pytest.raises(SynthesisError):
        synthesize_chapter(chapter, model, _voice_profile())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tts/test_synthesizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tts.synthesizer'`

- [ ] **Step 3: Write minimal implementation**

```python
# tts/synthesizer.py
import numpy as np

from scripts.models import Chapter
from tts.voice_profile import VoiceProfile


class SynthesisError(Exception):
    pass


def synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray:
    try:
        result = model.generate(text=chapter.text, instruct=voice_profile.instruction)
    except Exception as exc:
        raise SynthesisError(
            f"Lỗi khi lồng tiếng chương {chapter.index} ({chapter.heading}): {exc}"
        ) from exc

    try:
        audio = result[0]
    except (TypeError, IndexError, KeyError) as exc:
        raise SynthesisError(
            f"Kết quả OmniVoice cho chương {chapter.index} không đúng định dạng mong đợi: {exc}"
        ) from exc

    return np.asarray(audio, dtype=np.float32)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tts/test_synthesizer.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tts/synthesizer.py tests/tts/test_synthesizer.py
git commit -m "feat: add OmniVoice chapter synthesizer"
```

---

### Task 4: Audio post-processing (loudness normalization + concatenation)

**Files:**
- Create: `tts/audio_postprocess.py`
- Test: `tests/tts/test_audio_postprocess.py`

**Interfaces:**
- Consumes: nothing beyond `numpy`/`pyloudnorm`.
- Produces: `ChapterTiming(index: int, heading: str, start_seconds: float, end_seconds: float)`; `normalize_loudness(audio: np.ndarray, sample_rate: int, target_lufs: float) -> np.ndarray`; `concatenate_chapters(chapters: list[tuple[int, str, np.ndarray]], sample_rate: int, gap_seconds: float) -> tuple[np.ndarray, list[ChapterTiming]]`. Used by `tts/cli.py` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# tests/tts/test_audio_postprocess.py
import numpy as np
import pyloudnorm as pyln

from tts.audio_postprocess import ChapterTiming, concatenate_chapters, normalize_loudness


def _sine_wave(duration_seconds: float, sample_rate: int, amplitude: float = 0.1) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_normalize_loudness_moves_audio_toward_target_lufs():
    sample_rate = 24000
    audio = _sine_wave(1.0, sample_rate, amplitude=0.01)

    normalized = normalize_loudness(audio, sample_rate, target_lufs=-16.0)

    meter = pyln.Meter(sample_rate)
    result_lufs = meter.integrated_loudness(normalized)
    assert abs(result_lufs - (-16.0)) < 0.5


def test_concatenate_chapters_inserts_gap_and_computes_timestamps():
    sample_rate = 24000
    gap_seconds = 0.5
    chapter1_audio = np.ones(sample_rate, dtype=np.float32)
    chapter2_audio = np.ones(sample_rate * 2, dtype=np.float32)

    full_audio, timings = concatenate_chapters(
        [(1, "Chương 1", chapter1_audio), (2, "Chương 2", chapter2_audio)],
        sample_rate=sample_rate,
        gap_seconds=gap_seconds,
    )

    expected_length = sample_rate + int(gap_seconds * sample_rate) + sample_rate * 2
    assert len(full_audio) == expected_length

    assert timings[0] == ChapterTiming(
        index=1, heading="Chương 1", start_seconds=0.0, end_seconds=1.0
    )
    assert timings[1].index == 2
    assert timings[1].start_seconds == 1.5
    assert timings[1].end_seconds == 3.5


def test_concatenate_chapters_no_trailing_gap_after_last_chapter():
    sample_rate = 24000
    chapter_audio = np.ones(sample_rate, dtype=np.float32)

    full_audio, _ = concatenate_chapters(
        [(1, "Chương 1", chapter_audio)],
        sample_rate=sample_rate,
        gap_seconds=0.5,
    )

    assert len(full_audio) == sample_rate
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tts/test_audio_postprocess.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tts.audio_postprocess'`

- [ ] **Step 3: Write minimal implementation**

```python
# tts/audio_postprocess.py
from dataclasses import dataclass

import numpy as np
import pyloudnorm as pyln


@dataclass
class ChapterTiming:
    index: int
    heading: str
    start_seconds: float
    end_seconds: float


def normalize_loudness(audio: np.ndarray, sample_rate: int, target_lufs: float) -> np.ndarray:
    meter = pyln.Meter(sample_rate)
    loudness = meter.integrated_loudness(audio)
    return pyln.normalize.loudness(audio, loudness, target_lufs)


def concatenate_chapters(
    chapters: list[tuple[int, str, np.ndarray]],
    sample_rate: int,
    gap_seconds: float,
) -> tuple[np.ndarray, list[ChapterTiming]]:
    gap_samples = int(gap_seconds * sample_rate)
    gap = np.zeros(gap_samples, dtype=np.float32)

    segments = []
    timings = []
    cursor_samples = 0

    for i, (index, heading, audio) in enumerate(chapters):
        start_seconds = cursor_samples / sample_rate
        segments.append(audio)
        cursor_samples += len(audio)
        end_seconds = cursor_samples / sample_rate
        timings.append(
            ChapterTiming(
                index=index, heading=heading, start_seconds=start_seconds, end_seconds=end_seconds
            )
        )

        if i < len(chapters) - 1:
            segments.append(gap)
            cursor_samples += gap_samples

    full_audio = np.concatenate(segments) if segments else np.zeros(0, dtype=np.float32)
    return full_audio, timings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tts/test_audio_postprocess.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tts/audio_postprocess.py tests/tts/test_audio_postprocess.py
git commit -m "feat: add loudness normalization and chapter concatenation"
```

---

### Task 5: Storage

**Files:**
- Create: `tts/storage.py`
- Test: `tests/tts/test_storage.py`

**Interfaces:**
- Consumes: `ChapterTiming` from `tts/audio_postprocess.py` (Task 4).
- Produces: `save_audio(trope: str, title: str, audio: np.ndarray, sample_rate: int, timings: list[ChapterTiming], output_dir: Path) -> tuple[Path, Path]` (returns `(audio_path, metadata_path)`). Used by `tts/cli.py` (Task 6).

- [ ] **Step 1: Write the failing test**

```python
# tests/tts/test_storage.py
import json

import numpy as np

from tts.audio_postprocess import ChapterTiming
from tts.storage import save_audio


def test_save_audio_writes_wav_and_metadata_json(tmp_path):
    audio = np.zeros(24000, dtype=np.float32)
    timings = [ChapterTiming(index=1, heading="Chương 1", start_seconds=0.0, end_seconds=1.0)]

    audio_path, metadata_path = save_audio(
        trope="test_trope",
        title="Tiêu đề",
        audio=audio,
        sample_rate=24000,
        timings=timings,
        output_dir=tmp_path,
    )

    assert audio_path.exists()
    assert audio_path.suffix == ".wav"
    assert metadata_path.exists()

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề"
    assert data["trope"] == "test_trope"
    assert data["chapters"][0]["heading"] == "Chương 1"
    assert data["chapters"][0]["end_seconds"] == 1.0


def test_save_audio_creates_output_dir_if_missing(tmp_path):
    audio = np.zeros(100, dtype=np.float32)
    missing_dir = tmp_path / "nested" / "output"

    audio_path, _ = save_audio(
        trope="t", title="T", audio=audio, sample_rate=24000, timings=[], output_dir=missing_dir
    )

    assert audio_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tts/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tts.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# tts/storage.py
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from tts.audio_postprocess import ChapterTiming


def save_audio(
    trope: str,
    title: str,
    audio: np.ndarray,
    sample_rate: int,
    timings: list[ChapterTiming],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    audio_path = output_dir / f"{trope}-{timestamp}.wav"
    sf.write(audio_path, audio, sample_rate)

    metadata_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {
        "trope": trope,
        "title": title,
        "chapters": [
            {
                "index": t.index,
                "heading": t.heading,
                "start_seconds": t.start_seconds,
                "end_seconds": t.end_seconds,
            }
            for t in timings
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return audio_path, metadata_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tts/test_storage.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tts/storage.py tests/tts/test_storage.py
git commit -m "feat: add audio storage (WAV + timestamp metadata)"
```

---

### Task 6: CLI entrypoint

**Files:**
- Create: `tts/cli.py`
- Test: `tests/tts/test_cli.py`

**Interfaces:**
- Consumes: `Script`, `Chapter` from `scripts/models.py` (existing); `load_voice_profile` (Task 2); `synthesize_chapter` (Task 3); `normalize_loudness`, `concatenate_chapters` (Task 4); `save_audio` (Task 5).
- Produces: `main() -> None`; `_run(script_path: Path, model=None) -> None`; module-level `VOICE_CONFIG_PATH: Path` and `OUTPUT_DIR: Path` (overridable via monkeypatch for testing). This is the last piece of sub-project 2 — later sub-projects (Flux image generation, Remotion video assembly) will consume the `.wav`/`.json` files this CLI writes to `output/audio/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/tts/test_cli.py
import json
from pathlib import Path

import numpy as np

from scripts.models import Chapter, Script
from tts import cli


def _fake_chapter_audio(duration_seconds=1.0, sample_rate=24000, amplitude=0.1) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class _FakeModel:
    def generate(self, text, instruct):
        return [_fake_chapter_audio()]


def test_run_generates_normalizes_concatenates_and_saves(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    voice_path = tmp_path / "voice.yaml"
    voice_path.write_text(
        "instruction: test voice\ntarget_lufs: -16.0\nsample_rate: 24000\ngap_seconds: 0.1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "VOICE_CONFIG_PATH", voice_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    cli._run(script_path, model=_FakeModel())

    saved_audio = list((tmp_path / "output").glob("*.wav"))
    assert len(saved_audio) == 1

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    assert len(saved_metadata) == 1
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["heading"] == "Chương 1"

    out = capsys.readouterr().out
    assert "Đã lưu audio" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda script_path, model=None: calls.append(script_path))
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tts/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tts.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# tts/cli.py
import argparse
import json
from pathlib import Path

from scripts.models import Script
from tts.audio_postprocess import concatenate_chapters, normalize_loudness
from tts.storage import save_audio
from tts.synthesizer import synthesize_chapter
from tts.voice_profile import load_voice_profile

VOICE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "voice.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "audio"


def _load_model():
    import torch
    from omnivoice import OmniVoice

    return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="mps", dtype=torch.float16)


def _run(script_path: Path, model=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    voice_profile = load_voice_profile(VOICE_CONFIG_PATH)

    if model is None:
        model = _load_model()

    normalized_chapters = []
    for chapter in script.chapters:
        audio = synthesize_chapter(chapter, model, voice_profile)
        normalized_audio = normalize_loudness(
            audio, voice_profile.sample_rate, voice_profile.target_lufs
        )
        normalized_chapters.append((chapter.index, chapter.heading, normalized_audio))

    full_audio, timings = concatenate_chapters(
        normalized_chapters,
        sample_rate=voice_profile.sample_rate,
        gap_seconds=voice_profile.gap_seconds,
    )

    audio_path, metadata_path = save_audio(
        trope=script.trope,
        title=script.title,
        audio=full_audio,
        sample_rate=voice_profile.sample_rate,
        timings=timings,
        output_dir=OUTPUT_DIR,
    )

    duration_seconds = len(full_audio) / voice_profile.sample_rate
    print(
        f"Đã lưu audio: {audio_path} ({duration_seconds:.1f} giây, {len(script.chapters)} chương)\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lồng tiếng kịch bản truyện audio bằng OmniVoice."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    _run(Path(args.script_path))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tts/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS (all tests across the script-generation module plus this plan's Tasks 2–6, no real OmniVoice model loaded)

- [ ] **Step 6: Commit**

```bash
git add tts/cli.py tests/tts/test_cli.py
git commit -m "feat: add TTS CLI entrypoint"
```

- [ ] **Step 7: Manual smoke test with the real OmniVoice model (not automated — requires downloading model weights and real inference)**

1. Ensure a script JSON file exists from the script-generation module, e.g. `output/scripts/trong_sinh_bao_thu-<timestamp>.json`.
2. Run: `uv run python -m tts.cli output/scripts/trong_sinh_bao_thu-<timestamp>.json`
3. Expected: downloads OmniVoice model weights on first run (may take a while), then prints `Đã lưu audio: output/audio/trong_sinh_bao_thu-<timestamp>.wav (N giây, M chương)` and `Metadata: output/audio/trong_sinh_bao_thu-<timestamp>.json`.
4. Play the saved `.wav` file and listen to at least 2 chapters to confirm: voice sounds natural and matches the `config/voice.yaml` description, volume is consistent across chapters (loudness normalization worked), and there's a clean short pause at chapter boundaries (no abrupt cut or overlap).
5. Open the saved `.json` file and confirm chapter timestamps look correct (monotonically increasing, roughly matching the audio's actual chapter boundaries by ear).

---

## Self-Review Notes

- **Spec coverage**: implements all of the TTS module spec — voice design via `config/voice.yaml` + `VoiceProfile` (Task 2), per-chapter synthesis via OmniVoice wrapped with clear error handling (Task 3), loudness normalization and chapter concatenation with timestamp tracking (Task 4), final WAV + timestamp-JSON output (Task 5), end-to-end CLI wiring with a real-model smoke test (Task 6). Background music and voice cloning are correctly out of scope per the spec — no task builds them. Apple Silicon/MPS is the target device in `_load_model()` (Task 6), matching the spec's infra decision.
- **Placeholder scan**: no TBD/TODO; every step has runnable code or an exact command with expected output.
- **Type consistency**: `VoiceProfile(instruction, target_lufs, sample_rate, gap_seconds)` from Task 2 is used identically in Task 3 (`synthesize_chapter`) and Task 6 (`cli._run`). `ChapterTiming(index, heading, start_seconds, end_seconds)` from Task 4 is used identically in Task 5 (`save_audio`) and produced by `concatenate_chapters`. `synthesize_chapter(chapter, model, voice_profile) -> np.ndarray`, `normalize_loudness(audio, sample_rate, target_lufs) -> np.ndarray`, `concatenate_chapters(chapters, sample_rate, gap_seconds) -> (np.ndarray, list[ChapterTiming])`, and `save_audio(trope, title, audio, sample_rate, timings, output_dir) -> (Path, Path)` signatures all match how `tts/cli.py` calls them in Task 6.
