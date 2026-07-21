# Images Module: Together AI → mflux Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Together AI FLUX.1-schnell backend in the `images/` module with a local `mflux-generate-flux2` CLI (FLUX.2 Klein 4B), so background-image generation runs entirely on-device with no third-party API key.

**Architecture:** `images/generator.py` calls `mflux-generate-flux2` as a subprocess, writing the PNG to a throwaway temp directory, reading it back into `bytes`, then deleting the temp directory. The rest of the pipeline (`scene_prompt.py`, `style.py`, `storage.py`, and the chapter loop in `cli.py`) is untouched except for dropping the now-unnecessary Together AI client plumbing in `cli.py`.

**Tech Stack:** Python 3.11, `uv` for dependency management, `pytest` + `pytest-asyncio` (already configured with `asyncio_mode = "auto"`), `subprocess` (stdlib), `mflux` (MIT license, MLX-native, installed as a project dependency via `uv`).

## Global Constraints

- Spec: [docs/superpowers/specs/2026-07-21-images-mflux-migration-design.md](../specs/2026-07-21-images-mflux-migration-design.md)
- Model: `Runpod/FLUX.2-klein-4B-mflux-4bit`, `--base-model flux2-klein-4b`.
- Image params unchanged from the original spec: `--width 1024 --height 576 --steps 4`.
- `generate_background_image` keeps a `bytes`-returning signature (no `client` argument) — `storage.py` and `cli.py`'s call site must not need to change their data shapes.
- CLI resolution: prefer `.venv/bin/mflux-generate-flux2` if it exists, else fall back to `mflux-generate-flux2` on `PATH`.
- Known gotcha: `mflux-generate-flux2` exits 0 and silently no-ops if `--output` already points at an existing file. Never pass an already-existing path; treat success as `returncode == 0 AND output file exists afterward`.
- No real `mflux` or subprocess calls in automated tests — always mock `subprocess.run`.
- Together AI is fully removed, not kept as a fallback: drop the `together` dependency and `TOGETHER_API_KEY`.
- No new config file (matches the original spec's decision) — model name, base model, width, height, steps stay as constants in `images/generator.py`.

---

### Task 1: Swap project dependency from `together` to `mflux`

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

**Interfaces:**
- Produces: a project virtualenv (`.venv/bin/`) containing `mflux-generate-flux2` (and mflux's other CLI entry points), available for Task 2's subprocess calls and for the manual smoke test in Task 4.

- [ ] **Step 1: Remove the `together` dependency and add `mflux`**

In `pyproject.toml`, the `dependencies` list currently ends with:

```toml
dependencies = [
    "gemini-webapi>=1.0.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "omnivoice>=0.1.0",
    "torch>=2.0.0",
    "pyloudnorm>=0.1.1",
    "soundfile>=0.12.1",
    "together>=1.3.0",
]
```

Change the last line so the list reads:

```toml
dependencies = [
    "gemini-webapi>=1.0.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "omnivoice>=0.1.0",
    "torch>=2.0.0",
    "pyloudnorm>=0.1.1",
    "soundfile>=0.12.1",
    "mflux",
]
```

- [ ] **Step 2: Remove `TOGETHER_API_KEY` from the env template**

In `.env.example`, delete the line:

```
TOGETHER_API_KEY=your_together_api_key
```

The file should only contain `SECURE_1PSID` and `SECURE_1PSIDTS` afterward.

- [ ] **Step 3: Install the updated dependencies**

Run: `uv sync`

Expected: command completes successfully, creates/updates `.venv/`, and `together` is no longer installed while `mflux` is. Verify with:

```bash
ls .venv/bin | grep mflux-generate-flux2
```

Expected output: `mflux-generate-flux2`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example uv.lock
git commit -m "chore: replace together dependency with mflux"
```

---

### Task 2: Rewrite `images/generator.py` to call mflux via subprocess

**Files:**
- Modify: `images/generator.py`
- Test: `tests/images/test_generator.py` (full rewrite)

**Interfaces:**
- Consumes: `images.style.STYLE_SUFFIX` (str constant, unchanged).
- Produces: `generate_background_image(scene_description: str) -> bytes` and `ImageGenerationError(Exception)` — both names and this exact signature are relied on by Task 3's `images/cli.py`.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/images/test_generator.py` with:

```python
# tests/images/test_generator.py
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from images.generator import ImageGenerationError, generate_background_image


def _fake_run_writing_output(png_bytes: bytes):
    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_bytes(png_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    return _run


def test_generate_background_image_returns_bytes_from_output_file():
    fake_bytes = b"fake png bytes"

    with patch(
        "images.generator.subprocess.run",
        side_effect=_fake_run_writing_output(fake_bytes),
    ) as mock_run:
        result = generate_background_image("cozy living room at dusk")

    assert result == fake_bytes

    cmd = mock_run.call_args.args[0]
    assert cmd[0].endswith("mflux-generate-flux2")
    assert cmd[cmd.index("--model") + 1] == "Runpod/FLUX.2-klein-4B-mflux-4bit"
    assert cmd[cmd.index("--base-model") + 1] == "flux2-klein-4b"
    assert cmd[cmd.index("--width") + 1] == "1024"
    assert cmd[cmd.index("--height") + 1] == "576"
    assert cmd[cmd.index("--steps") + 1] == "4"
    prompt = cmd[cmd.index("--prompt") + 1]
    assert prompt.startswith("cozy living room at dusk, ")
    assert "no text" in prompt


def test_generate_background_image_raises_on_nonzero_returncode():
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="", stderr="model load failed"
        )

    with patch("images.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ImageGenerationError, match="model load failed"):
            generate_background_image("a scene")


def test_generate_background_image_raises_when_output_file_missing_despite_success_code():
    def _run(cmd, **kwargs):
        # Simulates the known mflux-generate-flux2 no-op bug: returncode 0
        # but no file actually written.
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("images.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ImageGenerationError):
            generate_background_image("a scene")


def test_generate_background_image_cleans_up_temp_dir():
    fake_bytes = b"fake png bytes"
    captured_dirs = {}

    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        captured_dirs["dir"] = output_path.parent
        output_path.write_bytes(fake_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("images.generator.subprocess.run", side_effect=_run):
        generate_background_image("a scene")

    assert not captured_dirs["dir"].exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/images/test_generator.py -v`

Expected: collection error or failures — `images.generator` still imports `together`/`Together` and has no `subprocess`-based implementation, so these tests fail (either an `ImportError` from the old `from together import Together` line, or `AttributeError`/assertion failures once that's resolved).

- [ ] **Step 3: Write the implementation**

Replace the full contents of `images/generator.py` with:

```python
# images/generator.py
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from images.style import STYLE_SUFFIX

MODEL = "Runpod/FLUX.2-klein-4B-mflux-4bit"
BASE_MODEL = "flux2-klein-4b"
WIDTH = 1024
HEIGHT = 576
STEPS = 4


class ImageGenerationError(Exception):
    pass


def _resolve_mflux_cli() -> str:
    venv_cli = os.path.join(".venv", "bin", "mflux-generate-flux2")
    return venv_cli if os.path.exists(venv_cli) else "mflux-generate-flux2"


def generate_background_image(scene_description: str) -> bytes:
    prompt = f"{scene_description}, {STYLE_SUFFIX}"

    tmp_dir = tempfile.mkdtemp(prefix="mflux-image-")
    try:
        output_path = Path(tmp_dir) / "scene.png"

        cmd = [
            _resolve_mflux_cli(),
            "--model", MODEL,
            "--base-model", BASE_MODEL,
            "--prompt", prompt,
            "--steps", str(STEPS),
            "--width", str(WIDTH),
            "--height", str(HEIGHT),
            "--output", str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not output_path.exists():
            raise ImageGenerationError(
                f"Lỗi khi gọi mflux sinh ảnh: {result.stderr or result.stdout}"
            )

        return output_path.read_bytes()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/images/test_generator.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add images/generator.py tests/images/test_generator.py
git commit -m "feat: generate background images via local mflux-generate-flux2"
```

---

### Task 3: Drop the Together AI client from `images/cli.py`

**Files:**
- Modify: `images/cli.py`
- Test: `tests/images/test_cli.py`

**Interfaces:**
- Consumes: `generate_background_image(scene_description: str) -> bytes` from Task 2 (no `client` argument).
- Produces: `cli._run(script_path: Path, gemini_client=None) -> None` (drops the `flux_client` parameter that existed before this task) and `cli.main() -> None`, unchanged in shape otherwise.

- [ ] **Step 1: Write the failing test**

Replace the full contents of `tests/images/test_cli.py` with:

```python
import json
from pathlib import Path

from images import cli
from scripts.models import Chapter, Script


async def test_run_generates_scene_descriptions_and_images_and_saves(
    tmp_path, monkeypatch, capsys
):
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

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_gemini_client = object()

    async def fake_generate_scene_description(chapter, client):
        assert client is fake_gemini_client
        return f"scene for chapter {chapter.index}"

    def fake_generate_background_image(scene_description):
        return f"fake image bytes for {scene_description}".encode("utf-8")

    monkeypatch.setattr(cli, "generate_scene_description", fake_generate_scene_description)
    monkeypatch.setattr(cli, "generate_background_image", fake_generate_background_image)

    await cli._run(script_path, gemini_client=fake_gemini_client)

    saved_images = sorted((tmp_path / "output").glob("*.png"))
    assert len(saved_images) == 2

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    assert len(saved_metadata) == 1
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"
    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["scene_description"] == "scene for chapter 1"

    out = capsys.readouterr().out
    assert "Đã lưu 2 ảnh" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, gemini_client=None):
        calls.append(script_path)

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/images/test_cli.py -v`

Expected: FAIL — `cli._run` still requires/accepts a `flux_client` and calls `generate_background_image(scene_description, flux_client)`, and `fake_generate_background_image` above only accepts one argument, so calling it raises `TypeError: fake_generate_background_image() takes 1 positional argument but 2 were given`.

- [ ] **Step 3: Write the implementation**

Replace the full contents of `images/cli.py` with:

```python
import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from images.generator import generate_background_image
from images.scene_prompt import generate_scene_description
from images.storage import save_chapter_images
from scripts.models import Script

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "images"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


async def _run(script_path: Path, gemini_client=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    images = []
    for chapter in script.chapters:
        scene_description = await generate_scene_description(chapter, gemini_client)
        image_bytes = generate_background_image(scene_description)
        images.append((chapter.index, scene_description, image_bytes))

    image_paths, metadata_path = save_chapter_images(
        script.trope, script.title, images, OUTPUT_DIR
    )

    print(
        f"Đã lưu {len(image_paths)} ảnh vào {OUTPUT_DIR}\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh ảnh nền cho kịch bản truyện audio bằng Flux."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/images/test_cli.py -v`

Expected: 2 passed

- [ ] **Step 5: Run the full images test suite**

Run: `uv run pytest tests/images/ -v`

Expected: all tests in `tests/images/test_generator.py`, `tests/images/test_cli.py`, `tests/images/test_storage.py`, and `tests/images/test_scene_prompt.py` pass (the latter two are untouched by this migration and should be unaffected).

- [ ] **Step 6: Commit**

```bash
git add images/cli.py tests/images/test_cli.py
git commit -m "refactor: drop Together AI client plumbing from images CLI"
```

---

### Task 4: Manual smoke test (not automated)

**Files:** none (verification only, no code changes)

**Interfaces:** none — this task only exercises the public entry point `python -m images.cli <script_path>` built by Tasks 1-3.

- [ ] **Step 1: Confirm a real script JSON is available**

Look for an existing output from the script-generation module:

```bash
ls output/scripts/*.json
```

If none exists, generate one first per `docs/superpowers/plans/2026-07-21-script-generation-module.md`, or ask the user for a sample script JSON path.

- [ ] **Step 2: Run the images CLI for real**

```bash
uv run python -m images.cli output/scripts/<pick-one>.json
```

Expected: no crash/hang (this is the specific thing to watch for, since the TTS module hit an MPS crash on this same machine — mflux uses MLX instead, but this is the first real confirmation it's stable here). Command prints `Đã lưu 8 ảnh vào .../output/images` and a metadata path.

Note the first run will download the `Runpod/FLUX.2-klein-4B-mflux-4bit` weights from HuggingFace (several GB) — this is expected and only happens once.

- [ ] **Step 3: Review the generated images**

Open the 8 PNGs in `output/images/` and confirm:
- Style matches the approved template (watercolor/flat-illustration, warm tones)
- No stray text/logos baked into the images
- All 8 images are visually consistent with each other in tone/color

- [ ] **Step 4: Note generation time**

Record wall-clock time for the 8-image run (`time uv run python -m images.cli ...`). This measures the per-chapter model-reload cost flagged as a known trade-off in the spec — needed to judge whether it's acceptable for the 2-3 videos/week production pace. No pass/fail threshold defined yet; just capture the number for the operator to evaluate.
