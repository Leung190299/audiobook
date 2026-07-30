# VieNeu-TTS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the OmniVoice TTS engine with VieNeu-TTS across the `tts/` module, remove the now-unnecessary per-chapter/merge parallelism infrastructure, and update the living pipeline skill doc.

**Architecture:** Keep the existing `tts/` module shape (`voice_profile.py` → `synthesizer.py` → `audio_postprocess.py` → `storage.py` → `cli.py`). Swap the model-loading and per-chapter synthesis call to VieNeu-TTS's `vieneu` SDK, change `VoiceProfile`'s config fields to match VieNeu-TTS's API (preset `voice` + `style` instead of OmniVoice's `instruction`/`ref_audio_path`), delete `tts/merge_cli.py` and the `--chapter` CLI flag (no longer needed — VieNeu-TTS is fast enough to synthesize a full 16-chapter script sequentially in one process), and update `.claude/skills/generating-audiobook-video/SKILL.md` to match.

**Tech Stack:** Python 3.11+ (existing `uv` project), [vieneu](https://github.com/pnnbao97/VieNeu-TTS) SDK (v3 Turbo, ONNX Runtime backend — torch-free, CPU), `pyloudnorm`, `soundfile`, `numpy` (all unchanged).

## Global Constraints

- Spec: [docs/superpowers/specs/2026-07-30-vieneu-tts-migration-design.md](../specs/2026-07-30-vieneu-tts-migration-design.md)
- Voice: preset `"Ngọc Linh"` (Nữ · Bắc · kể chuyện), no voice cloning.
- Style: `"doc_truyen"`.
- Backend: `Vieneu(backend="onnx")` — explicit, torch-free, no PyTorch/MPS dependency.
- Sample rate: `48000` (VieNeu-TTS v3 Turbo's fixed output rate) — replaces the old `24000` default in `config/voice.yaml`.
- No automated test may load the real `vieneu` model — always inject a fake/mock model object exposing `.infer(text, voice=None, style=None) -> np.ndarray`.
- Remove `omnivoice` and `torch` from `pyproject.toml`; add `vieneu`. Confirmed (via repo-wide grep) no other file imports `torch` besides the old `tts/cli.py`.
- Delete `tts/merge_cli.py`, `tests/tts/test_merge_cli.py`, and the `--chapter` CLI flag entirely — do not keep them behind a flag or deprecate gradually.

---

### Task 1: Dependencies + `VoiceProfile` config schema

**Files:**
- Modify: `pyproject.toml:10-11`
- Modify: `tts/voice_profile.py` (whole file)
- Modify: `config/voice.yaml` (whole file)
- Test: `tests/tts/test_voice_profile.py` (whole file)

**Interfaces:**
- Produces: `VoiceProfile(voice: str, style: str, target_lufs: float, sample_rate: int, gap_seconds: float)` dataclass and `load_voice_profile(path: Path) -> VoiceProfile`, both consumed by Task 2 (`synthesizer.py`) and Task 3 (`cli.py`).

- [ ] **Step 1: Write the failing test for the new `VoiceProfile` schema**

Replace the full contents of `tests/tts/test_voice_profile.py` with:

```python
from tts.voice_profile import VoiceProfile, load_voice_profile


def test_load_voice_profile_reads_all_fields(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(
        'voice: "Ngọc Linh"\n'
        'style: "doc_truyen"\n'
        "target_lufs: -16.0\n"
        "sample_rate: 48000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile == VoiceProfile(
        voice="Ngọc Linh",
        style="doc_truyen",
        target_lufs=-16.0,
        sample_rate=48000,
        gap_seconds=0.5,
    )
```

This replaces the 3 old tests (2 of which tested `ref_audio_path` path resolution — no longer applicable, VieNeu-TTS preset voices need no file path).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tts/test_voice_profile.py -v`
Expected: FAIL — `VoiceProfile` still has the old `instruction`/`ref_audio_path` fields, so the equality assertion fails (or `TypeError: unexpected keyword argument 'voice'`).

- [ ] **Step 3: Rewrite `tts/voice_profile.py`**

Replace the full file with:

```python
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class VoiceProfile:
    voice: str
    style: str
    target_lufs: float
    sample_rate: int
    gap_seconds: float


def load_voice_profile(path: Path) -> VoiceProfile:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return VoiceProfile(
        voice=data["voice"],
        style=data["style"],
        target_lufs=data["target_lufs"],
        sample_rate=data["sample_rate"],
        gap_seconds=data["gap_seconds"],
    )
```

- [ ] **Step 4: Update `config/voice.yaml`**

Replace the full file with:

```yaml
voice: "Ngọc Linh"
style: "doc_truyen"
target_lufs: -16.0
sample_rate: 48000
gap_seconds: 0.5  # Must match CROSSFADE_SECONDS in remotion/src/MainVideo.tsx
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/tts/test_voice_profile.py -v`
Expected: PASS (1 test)

- [ ] **Step 6: Update `pyproject.toml` dependencies**

In `pyproject.toml`, replace:

```toml
    "omnivoice>=0.1.0",
    "torch>=2.0.0",
```

with:

```toml
    "vieneu",
```

- [ ] **Step 7: Sync the environment and confirm no import errors**

Run: `uv sync`
Expected: resolves and installs `vieneu` (and its ONNX Runtime dependency), removes `omnivoice`/`torch`. No errors.

Run: `uv run python -c "import tts.voice_profile; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 8: Run the full test suite to confirm nothing else broke**

Run: `uv run pytest -v`
Expected: PASS everywhere except `tests/tts/test_synthesizer.py` and `tests/tts/test_cli.py`, which still reference the old `instruction`/`ref_audio_path` fields and old OmniVoice-shaped fake models — these are fixed in Tasks 2 and 3. `tests/tts/test_merge_cli.py` still passes at this point (untouched until Task 4).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock tts/voice_profile.py config/voice.yaml tests/tts/test_voice_profile.py
git commit -m "feat: swap TTS dependency omnivoice/torch -> vieneu, update VoiceProfile schema"
```

---

### Task 2: `synthesizer.py` — VieNeu-TTS synthesis call

**Files:**
- Modify: `tts/synthesizer.py` (whole file)
- Test: `tests/tts/test_synthesizer.py` (whole file)

**Interfaces:**
- Consumes: `VoiceProfile` from Task 1 (fields `voice`, `style`).
- Produces: `synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray` and `SynthesisError` — unchanged signature/name, consumed by Task 3 (`cli.py`). `model` is any object exposing `.infer(text: str, voice: str | None = None, style: str | None = None) -> np.ndarray` (matches the real `vieneu.Vieneu` instance in production, a fake in tests).

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/tts/test_synthesizer.py` with:

```python
# tests/tts/test_synthesizer.py
import numpy as np
import pytest

from scripts.models import Chapter
from tts.synthesizer import SynthesisError, synthesize_chapter
from tts.voice_profile import VoiceProfile


def _voice_profile() -> VoiceProfile:
    return VoiceProfile(
        voice="Ngọc Linh",
        style="doc_truyen",
        target_lufs=-16.0,
        sample_rate=48000,
        gap_seconds=0.5,
    )


class _FakeModel:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def infer(self, text, voice=None, style=None):
        self.calls.append((text, voice, style))
        return self.result


def test_synthesize_chapter_returns_audio_array():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel(fake_audio)

    audio = synthesize_chapter(chapter, model, _voice_profile())

    assert isinstance(audio, np.ndarray)
    assert audio.shape == (1000,)
    assert model.calls == [("Nội dung chương một.", "Ngọc Linh", "doc_truyen")]


def test_synthesize_chapter_raises_synthesis_error_on_model_failure():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")

    class _FailingModel:
        def infer(self, text, voice=None, style=None):
            raise RuntimeError("model crashed")

    with pytest.raises(SynthesisError, match="chương 1"):
        synthesize_chapter(chapter, _FailingModel(), _voice_profile())


def test_synthesize_chapter_raises_synthesis_error_on_none_result():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")
    model = _FakeModel(None)

    with pytest.raises(SynthesisError):
        synthesize_chapter(chapter, model, _voice_profile())
```

Note: the old voice-cloning test (`test_synthesize_chapter_uses_ref_audio_when_voice_clone_configured`) is dropped — `VoiceProfile` no longer has `ref_audio_path` (Task 1) and cloning is out of scope per the spec.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tts/test_synthesizer.py -v`
Expected: FAIL — `synthesizer.py` still calls `model.generate(...)` and expects a sequence result (`result[0]`), not `model.infer(...)` returning an array directly.

- [ ] **Step 3: Rewrite `tts/synthesizer.py`**

Replace the full file with:

```python
# tts/synthesizer.py
import numpy as np

from scripts.models import Chapter
from tts.voice_profile import VoiceProfile


class SynthesisError(Exception):
    pass


def synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray:
    try:
        audio = model.infer(
            text=chapter.text, voice=voice_profile.voice, style=voice_profile.style
        )
    except Exception as exc:
        raise SynthesisError(
            f"Lỗi khi lồng tiếng chương {chapter.index} ({chapter.heading}): {exc}"
        ) from exc

    if audio is None or not hasattr(audio, "__len__"):
        raise SynthesisError(
            f"Kết quả VieNeu-TTS cho chương {chapter.index} không đúng định dạng mong đợi"
        )

    return np.asarray(audio, dtype=np.float32)
```

Note: `np.asarray(None, dtype=np.float32)` does NOT raise — it silently returns `array(nan, dtype=float32)` — so the explicit `audio is None or not hasattr(audio, "__len__")` guard before conversion is required to correctly reject a malformed model result (verified interactively: `np.asarray(None, dtype=np.float32)` gives `array(nan)`, not an exception).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tts/test_synthesizer.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tts/synthesizer.py tests/tts/test_synthesizer.py
git commit -m "feat: rewrite synthesizer.py to call VieNeu-TTS's infer() API"
```

---

### Task 3: `cli.py` — VieNeu-TTS model loading, drop per-chapter mode

**Files:**
- Modify: `tts/cli.py` (whole file)
- Test: `tests/tts/test_cli.py` (whole file)

**Interfaces:**
- Consumes: `load_voice_profile` from Task 1, `synthesize_chapter`/`SynthesisError` from Task 2, `normalize_loudness`/`concatenate_chapters` from `tts/audio_postprocess.py` (unchanged), `save_audio` from `tts/storage.py` (unchanged).
- Produces: `_run(script_path: Path, model=None) -> None` (drops the `chapter_index` parameter) and `main()` — consumed only by the CLI entrypoint itself and its tests.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/tts/test_cli.py` with:

```python
import json
from pathlib import Path

import numpy as np

from scripts.models import Chapter, Script
from tts import cli


def _fake_chapter_audio(duration_seconds=1.0, sample_rate=48000, amplitude=0.1) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class _FakeModel:
    def infer(self, text, voice=None, style=None):
        return _fake_chapter_audio()


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
        'voice: "Ngọc Linh"\nstyle: "doc_truyen"\ntarget_lufs: -16.0\n'
        "sample_rate: 48000\ngap_seconds: 0.1\n",
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
    monkeypatch.setattr(
        cli,
        "_run",
        lambda script_path, model=None: calls.append(script_path),
    )
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
```

This drops `test_run_with_chapter_index_synthesizes_only_that_chapter`, `test_run_with_unknown_chapter_index_raises`, and `test_main_parses_chapter_flag` — the `--chapter` flag and `ChapterNotFoundError` no longer exist.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tts/test_cli.py -v`
Expected: FAIL — `_run` still requires the old signature and `_load_model` still imports `omnivoice`/`torch`.

- [ ] **Step 3: Rewrite `tts/cli.py`**

Replace the full file with:

```python
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
    from vieneu import Vieneu

    return Vieneu(backend="onnx")


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
        description="Lồng tiếng kịch bản truyện audio bằng VieNeu-TTS."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    _run(Path(args.script_path))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tts/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tts/cli.py tests/tts/test_cli.py
git commit -m "feat: load VieNeu-TTS in cli.py, drop --chapter mode"
```

---

### Task 4: Remove `merge_cli.py` and its test

**Files:**
- Delete: `tts/merge_cli.py`
- Delete: `tests/tts/test_merge_cli.py`

**Interfaces:**
- Consumes: nothing (pure deletion).
- Produces: nothing — no other file imports `tts.merge_cli` (confirmed via repo-wide grep during spec research; only `.claude/skills/generating-audiobook-video/SKILL.md` references it in prose, updated in Task 5).

- [ ] **Step 1: Delete the files**

```bash
git rm tts/merge_cli.py tests/tts/test_merge_cli.py
```

- [ ] **Step 2: Confirm nothing else references `merge_cli`**

Run: `grep -rn "merge_cli" --include="*.py" . 2>/dev/null | grep -v ".venv"`
Expected: no output (empty).

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (all tests; `tts` test count drops by the 3 tests that were in `test_merge_cli.py`).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove tts/merge_cli.py, no longer needed with VieNeu-TTS's single-process speed"
```

---

### Task 5: Update the living skill doc

**Files:**
- Modify: `.claude/skills/generating-audiobook-video/SKILL.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Remove the per-chapter-mode sentence and the entire "Parallel TTS" section**

In `.claude/skills/generating-audiobook-video/SKILL.md`, find this block (currently lines 44-56, immediately before `## SEO metadata (stage 6)`):

```markdown
Stage 2 and 3 both take stage 1's script path directly — they don't depend on each other and could run in parallel, but running them sequentially is simpler to reason about and this repo has no orchestration for concurrent runs.

**Stage 2 also has a per-chapter mode** for speeding up a 16-chapter run (see "Parallel TTS" below): `uv run python -m tts.cli <script_path> --chapter N` synthesizes only chapter N, writing to `output/audio/chapters/` instead of `output/audio/`. A separate merge step, `uv run python -m tts.merge_cli <script_path> <chapter_audio_dir>`, combines all per-chapter files back into one full-story `output/audio/<trope>-<ts>.wav` + `.json` in the exact same format stage 4 expects — so stage 4 is unaffected either way.

### Parallel TTS (stage 2), real findings

Running all 16 chapters through `tts.cli --chapter N` lets you parallelize stage 2, which otherwise dominates total pipeline time (TTS is CPU-only on this machine). Real findings from doing this on the operator's 16GB MacBook Air (8 cores):

- **Run at most 2 chapters concurrently.** Each `tts.cli` process loads OmniVoice (~2.5GB RSS) plus, on first use, a Whisper ASR model for auto-transcribing the voice-clone reference. 2 concurrent processes work reliably; going higher risks OOM on this machine (only ~3.5GB free RAM was observed even with nothing else running).
- **Measured throughput: ~24 minutes per round of 2 chapters** (~12 min effective per chapter). Timed across all 4 rounds of a real 8-chapter run on 2026-07-22 — the rounds took 25, 24, 23, and 23 minutes, so 8 chapters took ~1.6 hours end to end; expect **~3.2 hours for 16 chapters** (8 rounds). An earlier version of this doc claimed pairing inflates each chapter to "~44-54 min" and yields only a 15-25% saving; the measurements above contradict that. Note there is no clean solo-chapter measurement from the same run, so the exact parallel-vs-sequential speedup ratio is unknown — only the paired throughput above is measured.
- **Do NOT dispatch these long-running (20+ min) background jobs through the Agent/subagent tool.** In practice, subagents that start a `run_in_background: true` Bash command and then end their own turn cause that background job to vanish silently sometime later — no Python traceback, no exit code, no crash report, no OS-level jetsam/OOM log entry matching it. It just disappears. Launch these jobs directly from the main session's own Bash tool with `run_in_background: true` instead — that has run reliably for every long job in this project (TTS, image generation, video rendering all take many minutes to tens of minutes).
- **Practical batching that worked:** rounds of `[1,2]`, `[3,4]`, `[5,6]`, `[7,8]`, `[9,10]`, `[11,12]`, `[13,14]`, `[15,16]` — 8 rounds for a 16-chapter script. Each round is launched as two separate direct (non-agent) `Bash` calls with `run_in_background: true` in the same turn, then wait for both completion notifications before starting the next round. Any chapter already synthesized can be reused as-is and skipped.

## SEO metadata (stage 6)
```

Replace it with:

```markdown
Stage 2 and 3 both take stage 1's script path directly — they don't depend on each other and could run in parallel, but running them sequentially is simpler to reason about and this repo has no orchestration for concurrent runs.

**Stage 2 runs entirely CPU-side, torch-free** (VieNeu-TTS v3 Turbo via ONNX Runtime) — one `tts.cli` process loads the model once and synthesizes every chapter sequentially, no per-chapter mode or merge step needed. Measured 2026-07-30 on the operator's 16GB MacBook Air: a real 865-word chapter took ~30 seconds to synthesize (~220s of audio, RTF 0.136) — a full 16-chapter script is expected to finish in well under 10 minutes. (The previous OmniVoice engine needed ~12 min/chapter and a 2-process-parallel + merge workaround to stay under ~3.2 hours for 16 chapters; that workaround, including `tts/merge_cli.py`, is gone.)

## SEO metadata (stage 6)
```

- [ ] **Step 2: Update the "Expecting this to be fast" common-mistake entry**

Find:

```markdown
- **Expecting this to be fast.** A full 16-chapter run is a multi-hour job, dominated by TTS (~3.2 hours; CPU-only, no GPU/MPS on this project's dev machine). Image generation reloads the mflux model from scratch per chapter (~10 min total for stage 3's 16 images, more on the very first run while weights download) — don't assume a hang is a failure.
```

Replace with:

```markdown
- **Expecting this to be fast.** A full 16-chapter run still takes tens of minutes, now dominated by stage 3 (images) and stage 4 (video render), not stage 2 (TTS is ~30s/chapter with VieNeu-TTS, well under 10 minutes total). Image generation reloads the mflux model from scratch per chapter (~10 min total for stage 3's 16 images, more on the very first run while weights download) — don't assume a hang is a failure.
```

- [ ] **Step 3: Update the Agent/subagent background-job warning (it referenced the now-deleted "Parallel TTS" section)**

Find:

```markdown
- **Using the Agent/subagent tool to run a long TTS/image/video job in the background.** See "Parallel TTS" above — this has caused jobs to silently vanish. Use the main session's own `Bash` tool with `run_in_background: true` instead.
```

Replace with:

```markdown
- **Using the Agent/subagent tool to run a long image/video job in the background.** Subagents that start a `run_in_background: true` Bash command and then end their own turn cause that background job to vanish silently sometime later — no traceback, no exit code, no crash report. Launch these jobs directly from the main session's own `Bash` tool with `run_in_background: true` instead — that has run reliably for every long job in this project (image generation, video rendering).
```

- [ ] **Step 4: Remove the merge-ordering common-mistake entry**

Find and delete this line entirely (the merge step it describes no longer exists):

```markdown
- **Merging per-chapter TTS audio out of order.** `tts.merge_cli` orders chapters by the *original script's* chapter index, not by filename or discovery order — it's safe to run chapters in any order/any batching, but always pass the same original multi-chapter script JSON as its first argument.
```

- [ ] **Step 5: Verify no remaining references to OmniVoice, merge_cli, or --chapter in the doc**

Run: `grep -ni "omnivoice\|merge_cli\|--chapter" .claude/skills/generating-audiobook-video/SKILL.md`
Expected: no output (empty).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/generating-audiobook-video/SKILL.md
git commit -m "docs: update skill doc for VieNeu-TTS, remove parallel-TTS/merge guidance"
```

---

### Task 6: Manual smoke test (not automated)

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Run the real TTS CLI against an existing multi-chapter script**

Run: `uv run python -m tts.cli output/scripts/trong_sinh_mat_the-20260729T165258Z.json`

(Substitute the newest file under `output/scripts/*.json` if that one no longer exists — check with `ls -t output/scripts/*.json | head -1`.)

Expected: prints `Đã lưu audio: output/audio/<trope>-<ts>.wav (N giây, 16 chương)` and `Metadata: output/audio/<trope>-<ts>.json`, completing in well under 10 minutes (per the Task 5 measurement, expect somewhere around 8 minutes for 16 chapters run sequentially).

- [ ] **Step 2: Confirm the output metadata is well-formed**

Run: `uv run python -c "import json; d = json.load(open('<the .json path printed above>')); print(d['sample_rate']); print(len(d['chapters'])); print([c['heading'] for c in d['chapters'][:3]])"`

Expected: `sample_rate` is `48000`, `len(d['chapters'])` is `16`, headings match the original script's chapter headings in order.

- [ ] **Step 3: Listen to the audio and confirm quality**

Play `output/audio/<trope>-<ts>.wav` (or a few chapter-boundary excerpts) and confirm:
- The voice sounds like a consistent female Northern-Vietnamese storytelling narrator throughout.
- No audible glitches, cutoffs, or garbled words.
- Chapter transitions have a natural short pause (no abrupt cut, no overlap).

If quality is unacceptable, this is a config-only fix — try a different `voice` in `config/voice.yaml` from the 14 presets (list via `uv run python -c "from vieneu import Vieneu; [print(l, '|', v) for l, v in Vieneu(backend='onnx').list_preset_voices()]"`) and re-run this task. Do not change any code for this.

- [ ] **Step 4: Note actual timing for the record**

No commit needed for this task — it's verification only. If timing or quality meaningfully differs from what Task 5's doc update claims, correct the numbers in `.claude/skills/generating-audiobook-video/SKILL.md` and commit that fix under its own `docs:` commit.

---

### Task 7: Final whole-branch review

**Files:** none (review only).

**Interfaces:** none.

- [ ] **Step 1: Run the complete test suite**

Run: `uv run pytest -v`
Expected: PASS, 0 failures.

- [ ] **Step 2: Confirm no leftover references to the removed engine/architecture**

Run: `grep -rn "omnivoice\|OmniVoice\|merge_cli\|--chapter\b" --include="*.py" --include="*.md" . 2>/dev/null | grep -v ".venv\|__pycache__\|docs/superpowers/specs/2026-07-21\|docs/superpowers/plans/2026-07-21\|docs/superpowers/plans/2026-07-22"`

Expected: no output. (The `2026-07-21`/`2026-07-22` spec/plan files documenting the original OmniVoice build are historical records and intentionally excluded — they describe what was built at the time, not the current state.)

- [ ] **Step 3: Review the diff for scope creep**

Run: `git diff master --stat` (or the appropriate base branch)
Expected: only `pyproject.toml`, `uv.lock`, `tts/*.py` (minus `merge_cli.py`), `tests/tts/*.py` (minus `test_merge_cli.py`), `config/voice.yaml`, and `.claude/skills/generating-audiobook-video/SKILL.md` are touched. No unrelated files.

- [ ] **Step 4: Confirm `config/voices/female_ngochuyen.mp3` was left untouched**

Run: `git status config/voices/`
Expected: no changes reported (per spec, the file stays on disk unreferenced — not deleted).
