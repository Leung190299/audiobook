# Flux Images Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Flux images module — script JSON (from the script-generation module) → per-chapter scene description via Gemini → background art via FLUX.1-schnell-Free (Together AI) → 8 PNGs + metadata JSON per story — as sub-project 3 of the channel pipeline.

**Architecture:** An `images/` Python package with clearly separated responsibilities: `style.py` (the fixed visual-style suffix appended to every prompt), `scene_prompt.py` (Gemini: chapter prose → short English scene description), `generator.py` (Together AI FLUX.1-schnell-Free call → PNG bytes), `storage.py` (saves the 8 images + one metadata JSON), and `cli.py` (wires it all together). Automated tests never call the real Gemini or Together AI APIs — they always inject fake clients; only the final manual smoke-test step exercises the real APIs.

**Tech Stack:** Python 3.11+ (existing `uv` project), `gemini-webapi` (already a dependency, reused from the script-generation module), `together` (Together AI Python SDK) for FLUX.1-schnell-Free.

## Global Constraints

- Test tự động **không được gọi Gemini hoặc Together AI thật** — luôn dùng client giả (mock/fake).
- Model Flux: `black-forest-labs/FLUX.1-schnell-Free` qua Together AI, kích thước **1024×576** (16:9), **4 steps**.
- Mô tả cảnh (scene description) phải bằng **tiếng Anh**, chỉ mô tả **bối cảnh/không khí** — không mô tả nhân vật, không kể cốt truyện, không dùng tên riêng.
- Mọi ảnh dùng chung một `STYLE_SUFFIX` cố định (watercolor/flat-illustration, tông màu ấm, không chữ/logo, không cận mặt người) ghép vào cuối prompt.
- **1 ảnh/chương**, tổng 8 ảnh/truyện.
- Input: file JSON kịch bản theo schema `Script.to_dict()` đã có (`scripts/models.py`): `{"trope": str, "title": str, "chapters": [{"index": int, "heading": str, "text": str}, ...]}`.
- Cả Gemini client và Together AI client khởi tạo **1 lần**, tái sử dụng cho toàn bộ 8 chương trong một lần chạy CLI.
- `.env` cần thêm `TOGETHER_API_KEY` (bên cạnh `SECURE_1PSID`/`SECURE_1PSIDTS` đã có).

---

### Task 1: Project setup for Flux images module

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `images/__init__.py`
- Create: `tests/images/__init__.py`

**Interfaces:**
- Consumes: nothing (first task of this plan).
- Produces: an importable `images` package, `TOGETHER_API_KEY` documented in `.env.example`, and an environment with `together` installed for later tasks.

- [ ] **Step 1: Add the `together` dependency to `pyproject.toml`**

Update the existing `dependencies` list under `[project]` to (keep every existing entry, only add `together`):

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

- [ ] **Step 2: Run `uv sync` and verify it succeeds**

Run: `uv sync`
Expected: installs `together` and its dependencies, no errors.

- [ ] **Step 3: Update `.env.example`**

Add a `TOGETHER_API_KEY` line to the existing file (keep the existing `SECURE_1PSID`/`SECURE_1PSIDTS` lines):

```
SECURE_1PSID=your_secure_1psid_cookie_value
SECURE_1PSIDTS=your_secure_1psidts_cookie_value
TOGETHER_API_KEY=your_together_api_key
```

- [ ] **Step 4: Create package directories and markers**

```bash
mkdir -p images tests/images output/images
touch images/__init__.py tests/images/__init__.py
```

- [ ] **Step 5: Verify imports**

Run: `uv run python -c "import images, together; print('ok')"`
Expected: prints `ok`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .env.example images/__init__.py tests/images/__init__.py
git commit -m "chore: scaffold Flux images module project (together)"
```

---

### Task 2: Scene prompt generator (Gemini)

**Files:**
- Create: `images/scene_prompt.py`
- Test: `tests/images/test_scene_prompt.py`

**Interfaces:**
- Consumes: `Chapter` from `scripts/models.py` (existing: `Chapter(index: int, heading: str, text: str)`).
- Produces: `async def generate_scene_description(chapter: Chapter, client: "GeminiClient | None" = None) -> str` (raises `ScenePromptError`). Used by `images/cli.py` (Task 5).

- [ ] **Step 1: Write the failing test**

```python
# tests/images/test_scene_prompt.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from images.scene_prompt import ScenePromptError, generate_scene_description
from scripts.models import Chapter


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


async def test_generate_scene_description_returns_cleaned_text():
    fake_client = _make_fake_client('"cozy living room at dusk"')

    description = await generate_scene_description(
        Chapter(index=1, heading="Chương 1", text="Nội dung chương một."),
        client=fake_client,
    )

    assert description == "cozy living room at dusk"
    fake_client.generate_content.assert_called_once()


async def test_generate_scene_description_raises_on_empty_response():
    fake_client = _make_fake_client("   ")

    with pytest.raises(ScenePromptError):
        await generate_scene_description(
            Chapter(index=2, heading="Chương 2", text="Nội dung."), client=fake_client
        )


async def test_generate_scene_description_wraps_api_error():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("boom"))

    with pytest.raises(ScenePromptError, match="chương 3"):
        await generate_scene_description(
            Chapter(index=3, heading="Chương 3", text="Nội dung."), client=fake_client
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/images/test_scene_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'images.scene_prompt'`

- [ ] **Step 3: Write minimal implementation**

```python
# images/scene_prompt.py
import os

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Chapter


class ScenePromptError(Exception):
    pass


def build_scene_prompt_request(chapter_text: str) -> str:
    return (
        "Đọc đoạn truyện tiếng Việt sau và mô tả LẠI bằng tiếng Anh, NGẮN GỌN (1-2 câu), "
        "chỉ tập trung vào KHÔNG GIAN/BỐI CẢNH và KHÔNG KHÍ của cảnh (ví dụ: phòng khách ấm "
        "cúng buổi tối, cánh đồng hoa lúc hoàng hôn, bờ biển vắng buổi sáng...). KHÔNG mô tả "
        "nhân vật, KHÔNG kể lại cốt truyện, KHÔNG dùng tên riêng. Chỉ trả về câu mô tả bối "
        "cảnh bằng tiếng Anh, không kèm giải thích gì khác, không kèm dấu ngoặc kép.\n\n"
        f"Đoạn truyện:\n{chapter_text}"
    )


async def generate_scene_description(
    chapter: Chapter, client: "GeminiClient | None" = None
) -> str:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    try:
        response = await client.generate_content(build_scene_prompt_request(chapter.text))
    except (GeminiError, APIError, AuthError) as exc:
        raise ScenePromptError(
            f"Gemini lỗi khi tạo mô tả cảnh cho chương {chapter.index}: {exc}"
        ) from exc

    description = response.text.strip().strip('"').strip()
    if not description:
        raise ScenePromptError(
            f"Gemini trả về mô tả cảnh rỗng cho chương {chapter.index}"
        )

    return description
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/images/test_scene_prompt.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add images/scene_prompt.py tests/images/test_scene_prompt.py
git commit -m "feat: add Gemini-based scene description generator"
```

---

### Task 3: Flux image generator (style + Together AI wrapper)

**Files:**
- Create: `images/style.py`
- Create: `images/generator.py`
- Test: `tests/images/test_generator.py`

**Interfaces:**
- Consumes: nothing beyond the `together` SDK.
- Produces: `STYLE_SUFFIX: str` (in `images/style.py`); `generate_background_image(scene_description: str, client: "Together | None" = None) -> bytes` (raises `ImageGenerationError`, in `images/generator.py`). Used by `images/cli.py` (Task 5).

- [ ] **Step 1: Write `images/style.py`**

```python
# images/style.py
STYLE_SUFFIX = (
    "soft watercolor and flat illustration style, warm pastel color palette, "
    "cozy atmospheric lighting, wide scenic shot, gentle painterly texture, "
    "no text, no logos, no words, no human faces in close-up"
)
```

- [ ] **Step 2: Write the failing test**

```python
# tests/images/test_generator.py
import base64
from unittest.mock import MagicMock

import pytest

from images.generator import ImageGenerationError, generate_background_image


def _make_fake_client(b64_data: "str | None"):
    fake_image = MagicMock()
    fake_image.b64_json = b64_data
    fake_response = MagicMock()
    fake_response.data = [fake_image] if b64_data is not None else []
    fake_client = MagicMock()
    fake_client.images.generate.return_value = fake_response
    return fake_client


def test_generate_background_image_returns_decoded_bytes():
    original_bytes = b"fake png bytes"
    b64_data = base64.b64encode(original_bytes).decode("ascii")
    fake_client = _make_fake_client(b64_data)

    image_bytes = generate_background_image("cozy living room at dusk", client=fake_client)

    assert image_bytes == original_bytes
    call_kwargs = fake_client.images.generate.call_args.kwargs
    assert call_kwargs["prompt"].startswith("cozy living room at dusk, ")
    assert "no text" in call_kwargs["prompt"]
    assert call_kwargs["model"] == "black-forest-labs/FLUX.1-schnell-Free"
    assert call_kwargs["width"] == 1024
    assert call_kwargs["height"] == 576


def test_generate_background_image_raises_on_client_error():
    fake_client = MagicMock()
    fake_client.images.generate.side_effect = RuntimeError("API down")

    with pytest.raises(ImageGenerationError):
        generate_background_image("a scene", client=fake_client)


def test_generate_background_image_raises_on_missing_data():
    fake_client = _make_fake_client(None)

    with pytest.raises(ImageGenerationError):
        generate_background_image("a scene", client=fake_client)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/images/test_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'images.generator'`

- [ ] **Step 4: Write minimal implementation**

```python
# images/generator.py
import base64
import os

from together import Together

from images.style import STYLE_SUFFIX

MODEL = "black-forest-labs/FLUX.1-schnell-Free"
WIDTH = 1024
HEIGHT = 576
STEPS = 4


class ImageGenerationError(Exception):
    pass


def generate_background_image(
    scene_description: str, client: "Together | None" = None
) -> bytes:
    client = client or Together(api_key=os.environ["TOGETHER_API_KEY"])

    prompt = f"{scene_description}, {STYLE_SUFFIX}"

    try:
        response = client.images.generate(
            model=MODEL,
            prompt=prompt,
            width=WIDTH,
            height=HEIGHT,
            steps=STEPS,
            n=1,
            response_format="base64",
        )
    except Exception as exc:
        raise ImageGenerationError(f"Lỗi khi gọi Flux sinh ảnh: {exc}") from exc

    try:
        b64_data = response.data[0].b64_json
    except (AttributeError, IndexError, TypeError) as exc:
        raise ImageGenerationError(
            f"Kết quả Together AI không đúng định dạng mong đợi: {exc}"
        ) from exc

    return base64.b64decode(b64_data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/images/test_generator.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add images/style.py images/generator.py tests/images/test_generator.py
git commit -m "feat: add FLUX.1-schnell-Free background image generator"
```

---

### Task 4: Storage

**Files:**
- Create: `images/storage.py`
- Test: `tests/images/test_storage.py`

**Interfaces:**
- Consumes: nothing beyond stdlib.
- Produces: `save_chapter_images(trope: str, title: str, images: list[tuple[int, str, bytes]], output_dir: Path) -> tuple[list[Path], Path]` (returns `(image_paths, metadata_path)`). Used by `images/cli.py` (Task 5). Each tuple in `images` is `(chapter_index, scene_description, image_bytes)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/images/test_storage.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/images/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'images.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# images/storage.py
import json
from datetime import datetime, timezone
from pathlib import Path


def save_chapter_images(
    trope: str,
    title: str,
    images: list[tuple[int, str, bytes]],
    output_dir: Path,
) -> tuple[list[Path], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    image_paths = []
    metadata_chapters = []
    for chapter_index, scene_description, image_bytes in images:
        image_path = output_dir / f"{trope}-{timestamp}-chapter-{chapter_index}.png"
        image_path.write_bytes(image_bytes)
        image_paths.append(image_path)
        metadata_chapters.append(
            {
                "index": chapter_index,
                "filename": image_path.name,
                "scene_description": scene_description,
            }
        )

    metadata_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {"trope": trope, "title": title, "chapters": metadata_chapters}
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return image_paths, metadata_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/images/test_storage.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add images/storage.py tests/images/test_storage.py
git commit -m "feat: add chapter image storage (PNGs + metadata)"
```

---

### Task 5: CLI entrypoint

**Files:**
- Create: `images/cli.py`
- Test: `tests/images/test_cli.py`

**Interfaces:**
- Consumes: `Script`, `Chapter` from `scripts/models.py` (existing); `generate_scene_description` (Task 2); `generate_background_image` (Task 3); `save_chapter_images` (Task 4).
- Produces: `main() -> None`; `async def _run(script_path: Path, gemini_client=None, flux_client=None) -> None`; module-level `OUTPUT_DIR: Path` (overridable via monkeypatch for testing). This is the last piece of sub-project 3 — the eventual Remotion video-assembly sub-project will consume the `.png`/`.json` files this CLI writes to `output/images/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/images/test_cli.py
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
    fake_flux_client = object()

    async def fake_generate_scene_description(chapter, client):
        assert client is fake_gemini_client
        return f"scene for chapter {chapter.index}"

    def fake_generate_background_image(scene_description, client):
        assert client is fake_flux_client
        return f"fake image bytes for {scene_description}".encode("utf-8")

    monkeypatch.setattr(cli, "generate_scene_description", fake_generate_scene_description)
    monkeypatch.setattr(cli, "generate_background_image", fake_generate_background_image)

    await cli._run(script_path, gemini_client=fake_gemini_client, flux_client=fake_flux_client)

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

    async def fake_run(script_path, gemini_client=None, flux_client=None):
        calls.append(script_path)

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/images/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'images.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# images/cli.py
import argparse
import asyncio
import json
import os
from pathlib import Path

from gemini_webapi import GeminiClient
from together import Together

from images.generator import generate_background_image
from images.scene_prompt import generate_scene_description
from images.storage import save_chapter_images
from scripts.models import Script

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "images"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


def _load_flux_client() -> Together:
    return Together(api_key=os.environ["TOGETHER_API_KEY"])


async def _run(script_path: Path, gemini_client=None, flux_client=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    if flux_client is None:
        flux_client = _load_flux_client()

    images = []
    for chapter in script.chapters:
        scene_description = await generate_scene_description(chapter, gemini_client)
        image_bytes = generate_background_image(scene_description, flux_client)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/images/test_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS (all tests across the script-generation module, the TTS module, and this plan's Tasks 2–5, no real Gemini/Together AI calls)

- [ ] **Step 6: Commit**

```bash
git add images/cli.py tests/images/test_cli.py
git commit -m "feat: add Flux images CLI entrypoint"
```

- [ ] **Step 7: Manual smoke test with the real Gemini and Together AI APIs (not automated — requires real cookies and a real TOGETHER_API_KEY)**

1. Ensure `.env` has `SECURE_1PSID`/`SECURE_1PSIDTS` (already set up from the script-generation module) and a real `TOGETHER_API_KEY` (sign up at together.ai, copy the API key).
2. Ensure a script JSON file exists from the script-generation module, e.g. `output/scripts/trong_sinh_bao_thu-<timestamp>.json`.
3. Run: `uv run python -m images.cli output/scripts/trong_sinh_bao_thu-<timestamp>.json`
4. Expected: prints `Đã lưu 8 ảnh vào output/images` and `Metadata: output/images/trong_sinh_bao_thu-<timestamp>.json`.
5. Open all 8 saved `.png` files and confirm: they match the approved visual style (watercolor/flat-illustration, warm tones), none of them contain stray text/logos/watermarks that Flux sometimes hallucinates, and the 8 images feel visually consistent as a set (not wildly different styles from each other).
6. Open the saved `.json` file and read the `scene_description` for each chapter — confirm they describe settings/mood (not characters or plot), consistent with what `scene_prompt.py`'s prompt asked for.

---

## Self-Review Notes

- **Spec coverage**: implements all of the Flux images module spec — API-based Flux via Together AI instead of local (Task 1/3, `device`-free design avoids the MPS issues found in the TTS module), 1 scene description + 1 image per chapter via Gemini reuse (Task 2) and FLUX.1-schnell-Free (Task 3), consistent `STYLE_SUFFIX` across all images (Task 3), 8 PNGs + metadata JSON output (Task 4), end-to-end CLI wiring with client reuse across chapters and a real-API smoke test (Task 5). Channel avatar, waveform/caption overlays, and Remotion video assembly are correctly out of scope per the spec — no task builds them.
- **Placeholder scan**: no TBD/TODO; every step has runnable code or an exact command with expected output.
- **Type consistency**: `generate_scene_description(chapter, client=None) -> str` (Task 2) is called by `cli._run` exactly as defined. `generate_background_image(scene_description, client=None) -> bytes` (Task 3) matches its use in `cli._run`. `save_chapter_images(trope, title, images, output_dir) -> (list[Path], Path)` (Task 4) matches how `cli._run` calls it and unpacks the result. The `images` list shape `list[tuple[int, str, bytes]]` (chapter_index, scene_description, image_bytes) is built identically in `cli._run` and consumed identically in `storage.save_chapter_images`.
