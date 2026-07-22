# Thumbnail Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically generate a 1280×720 YouTube thumbnail (mflux-rendered emotional close-up + reliably-overlaid hook text) right after the video render stage, as a new `thumbnail/` module.

**Architecture:** `thumbnail/prompt_generator.py` asks Gemini once for a short Vietnamese hook phrase plus an English visual description (label-parsed, same pattern as `metadata/seo_generator.py`). `thumbnail/generator.py` renders that description via the same `mflux-generate-flux2` CLI already used by `images/generator.py`, but with its own style/resolution/step-count constants (1280×720, 8 steps, a style suffix that *allows* close-up faces — the opposite of `images/style.py`'s constraint). `thumbnail/compositor.py` then uses Pillow (new dependency) to draw the hook text reliably on top, since mflux cannot be trusted to render legible text. `thumbnail/cli.py` wires these together and takes only a script path — no dependency on the TTS/images/video/metadata stages' output.

**Tech Stack:** Python 3.11 + `uv` (existing), `mflux` CLI (existing), `gemini-webapi` (existing), Pillow (new), a bundled Be Vietnam Pro Black TTF font (new, SIL OFL license).

## Global Constraints

- Spec: [docs/superpowers/specs/2026-07-22-thumbnail-module-design.md](../specs/2026-07-22-thumbnail-module-design.md)
- Model: `Runpod/FLUX.2-klein-4B-mflux-4bit`, `--base-model flux2-klein-4b` (same as `images/generator.py`).
- Image params for thumbnails: `--width 1280 --height 720 --steps 8` (different from `images/`'s 1024×576×4 — higher fidelity for close-up faces).
- CLI resolution, no-op-bug guard, temp-dir cleanup: identical pattern to `images/generator.py` — prefer `.venv/bin/mflux-generate-flux2` else PATH; treat success as `returncode == 0 AND output file exists`; never pass an already-existing `--output` path (use `tempfile.mkdtemp()`, never `NamedTemporaryFile()`); clean up the temp dir in a `finally` block.
- No JSON from Gemini — label format `HOOK:`/`VISUAL:`, parsed the same way `metadata/seo_generator.py` parses `TITLE:`/`DESCRIPTION:`/`TAGS:`/`HASHTAGS:` (regex anchored to line-start, error on missing/empty label).
- Gemini input is a summary only (title + trope + chapter headings), never the full script text.
- Hook text is rendered via Pillow, never left to mflux to draw — `THUMBNAIL_STYLE_SUFFIX` includes "no text, no logos, no watermark".
- `thumbnail/cli.py` takes only `script_path` — no dependency on TTS/images/video/metadata JSON output.
- No real Gemini or mflux calls in automated tests — mock the Gemini client and `subprocess.run`. Pillow compositing IS tested for real (fast, deterministic, no external calls) — same principle already applied to `pyloudnorm` audio processing in the TTS module.
- `thumbnail/generator.py` and `images/generator.py` intentionally duplicate the mflux-calling structure (constants differ) — this is a deliberate choice recorded in the spec, not an oversight; do not attempt to extract shared code between them in this plan.

---

### Task 1: `thumbnail/style.py` + `thumbnail/generator.py`

**Files:**
- Create: `thumbnail/__init__.py`
- Create: `thumbnail/style.py`
- Create: `thumbnail/generator.py`
- Test: `tests/thumbnail/__init__.py`
- Test: `tests/thumbnail/test_generator.py`

**Interfaces:**
- Produces: `THUMBNAIL_STYLE_SUFFIX: str` (in `thumbnail/style.py`), `generate_thumbnail_image(visual_description: str) -> bytes` and `ThumbnailGenerationError(Exception)` (in `thumbnail/generator.py`) — relied on by Task 5's `thumbnail/cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/thumbnail/__init__.py` (empty file).

Create `tests/thumbnail/test_generator.py`:

```python
# tests/thumbnail/test_generator.py
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from thumbnail.generator import ThumbnailGenerationError, generate_thumbnail_image


def _fake_run_writing_output(png_bytes: bytes):
    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        output_path.write_bytes(png_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    return _run


def test_generate_thumbnail_image_returns_bytes_from_output_file():
    fake_bytes = b"fake png bytes"

    with patch(
        "thumbnail.generator.subprocess.run",
        side_effect=_fake_run_writing_output(fake_bytes),
    ) as mock_run:
        result = generate_thumbnail_image("a shocked young woman, dramatic lighting")

    assert result == fake_bytes

    cmd = mock_run.call_args.args[0]
    assert cmd[0].endswith("mflux-generate-flux2")
    assert cmd[cmd.index("--model") + 1] == "Runpod/FLUX.2-klein-4B-mflux-4bit"
    assert cmd[cmd.index("--base-model") + 1] == "flux2-klein-4b"
    assert cmd[cmd.index("--width") + 1] == "1280"
    assert cmd[cmd.index("--height") + 1] == "720"
    assert cmd[cmd.index("--steps") + 1] == "8"
    prompt = cmd[cmd.index("--prompt") + 1]
    assert prompt.startswith("a shocked young woman, dramatic lighting, ")
    assert "no text" in prompt
    assert "close-up" in prompt


def test_generate_thumbnail_image_raises_on_nonzero_returncode():
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, returncode=1, stdout="", stderr="model load failed"
        )

    with patch("thumbnail.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ThumbnailGenerationError, match="model load failed"):
            generate_thumbnail_image("a scene")


def test_generate_thumbnail_image_raises_on_missing_binary():
    with patch(
        "thumbnail.generator.subprocess.run",
        side_effect=FileNotFoundError("mflux-generate-flux2 not found"),
    ):
        with pytest.raises(ThumbnailGenerationError) as exc_info:
            generate_thumbnail_image("a scene")

        error_msg = str(exc_info.value)
        assert "mflux-generate-flux2" in error_msg
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, FileNotFoundError)


def test_generate_thumbnail_image_raises_when_output_file_missing_despite_success_code():
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("thumbnail.generator.subprocess.run", side_effect=_run):
        with pytest.raises(ThumbnailGenerationError) as exc_info:
            generate_thumbnail_image("a scene")

        error_msg = str(exc_info.value)
        assert "returncode 0" in error_msg
        assert "no-op" in error_msg.lower() or "không ghi ra" in error_msg


def test_generate_thumbnail_image_cleans_up_temp_dir():
    fake_bytes = b"fake png bytes"
    captured_dirs = {}

    def _run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output") + 1])
        captured_dirs["dir"] = output_path.parent
        output_path.write_bytes(fake_bytes)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("thumbnail.generator.subprocess.run", side_effect=_run):
        generate_thumbnail_image("a scene")

    assert not captured_dirs["dir"].exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/thumbnail/test_generator.py -v`

Expected: FAIL — collection error, `thumbnail/style.py` and `thumbnail/generator.py` don't exist yet.

- [ ] **Step 3: Write the implementation**

Create `thumbnail/__init__.py` (empty file).

Create `thumbnail/style.py`:

```python
# thumbnail/style.py
THUMBNAIL_STYLE_SUFFIX = (
    "dramatic close-up portrait, intense emotional expression, cinematic lighting, "
    "vivid warm color palette, high contrast, YouTube thumbnail style, "
    "no text, no logos, no watermark"
)
```

Create `thumbnail/generator.py`:

```python
# thumbnail/generator.py
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from thumbnail.style import THUMBNAIL_STYLE_SUFFIX

MODEL = "Runpod/FLUX.2-klein-4B-mflux-4bit"
BASE_MODEL = "flux2-klein-4b"
WIDTH = 1280
HEIGHT = 720
STEPS = 8


class ThumbnailGenerationError(Exception):
    pass


def _resolve_mflux_cli() -> str:
    venv_cli = os.path.join(".venv", "bin", "mflux-generate-flux2")
    return venv_cli if os.path.exists(venv_cli) else "mflux-generate-flux2"


def generate_thumbnail_image(visual_description: str) -> bytes:
    prompt = f"{visual_description}, {THUMBNAIL_STYLE_SUFFIX}"

    tmp_dir = tempfile.mkdtemp(prefix="mflux-thumbnail-")
    try:
        output_path = Path(tmp_dir) / "thumbnail.png"

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

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as exc:
            raise ThumbnailGenerationError(
                f"Không thể gọi {_resolve_mflux_cli()}: {exc}"
            ) from exc

        if result.returncode != 0:
            raise ThumbnailGenerationError(
                f"Lỗi khi gọi mflux sinh thumbnail: {result.stderr or result.stdout}"
            )

        if not output_path.exists():
            raise ThumbnailGenerationError(
                "mflux-generate-flux2 trả về thành công (returncode 0) nhưng không ghi ra file output — "
                "có thể do lỗi no-op đã biết của công cụ"
            )

        return output_path.read_bytes()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/thumbnail/test_generator.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add thumbnail/__init__.py thumbnail/style.py thumbnail/generator.py tests/thumbnail/__init__.py tests/thumbnail/test_generator.py
git commit -m "feat: generate thumbnail background image via mflux"
```

---

### Task 2: `thumbnail/prompt_generator.py`

**Files:**
- Create: `thumbnail/prompt_generator.py`
- Test: `tests/thumbnail/test_prompt_generator.py`

**Interfaces:**
- Consumes: `scripts.models.Script` (existing: `.trope: str`, `.title: str`, `.chapters: list[Chapter]`; `Chapter.heading: str`).
- Produces: `ThumbnailPrompt` (dataclass: `hook_text: str`, `visual_description: str`), `generate_thumbnail_prompt(script: Script, client: GeminiClient | None = None) -> ThumbnailPrompt`, `ThumbnailPromptError(Exception)` — relied on by Task 5's `thumbnail/cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/thumbnail/test_prompt_generator.py`:

```python
# tests/thumbnail/test_prompt_generator.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.models import Chapter, Script
from thumbnail.prompt_generator import ThumbnailPromptError, generate_thumbnail_prompt


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


def _sample_script() -> Script:
    return Script(
        trope="phe_vat_nghich_tap",
        title="Kẻ Phế Vật Mang Linh Hồn Thần Cổ",
        chapters=[
            Chapter(index=1, heading="Chương 1: Phế Vật Họ Lâm", text="..."),
            Chapter(index=2, heading="Chương 2: Biến Cố", text="..."),
        ],
    )


async def test_generate_thumbnail_prompt_parses_both_labels():
    response_text = (
        "HOOK: SỐC NẶNG\n"
        "VISUAL: a young man with a shocked expression, dramatic backlighting"
    )
    fake_client = _make_fake_client(response_text)

    prompt = await generate_thumbnail_prompt(_sample_script(), client=fake_client)

    assert prompt.hook_text == "SỐC NẶNG"
    assert prompt.visual_description == (
        "a young man with a shocked expression, dramatic backlighting"
    )
    fake_client.generate_content.assert_called_once()


async def test_generate_thumbnail_prompt_raises_on_missing_label():
    fake_client = _make_fake_client("HOOK: Chỉ có hook\n")

    with pytest.raises(ThumbnailPromptError, match="VISUAL"):
        await generate_thumbnail_prompt(_sample_script(), client=fake_client)


async def test_generate_thumbnail_prompt_raises_on_empty_label_value():
    fake_client = _make_fake_client("HOOK: \nVISUAL: a scene")

    with pytest.raises(ThumbnailPromptError):
        await generate_thumbnail_prompt(_sample_script(), client=fake_client)


async def test_generate_thumbnail_prompt_wraps_api_error():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("boom"))

    with pytest.raises(ThumbnailPromptError):
        await generate_thumbnail_prompt(_sample_script(), client=fake_client)


async def test_generate_thumbnail_prompt_ignores_embedded_label_substring():
    response_text = (
        "HOOK: PHẢN ĐÒN\n"
        "VISUAL: a scene mentioning HOOK: not a real label, dramatic lighting"
    )
    fake_client = _make_fake_client(response_text)

    prompt = await generate_thumbnail_prompt(_sample_script(), client=fake_client)

    assert prompt.hook_text == "PHẢN ĐÒN"
    assert prompt.visual_description == (
        "a scene mentioning HOOK: not a real label, dramatic lighting"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/thumbnail/test_prompt_generator.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'thumbnail.prompt_generator'`.

- [ ] **Step 3: Write the implementation**

Create `thumbnail/prompt_generator.py`:

```python
# thumbnail/prompt_generator.py
import os
import re
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Script


class ThumbnailPromptError(Exception):
    pass


@dataclass
class ThumbnailPrompt:
    hook_text: str
    visual_description: str


_LABELS = ("HOOK", "VISUAL")


def build_thumbnail_prompt_request(script: Script) -> str:
    headings = "\n".join(f"- {c.heading}" for c in script.chapters)
    return (
        "Bạn là chuyên gia thiết kế thumbnail YouTube. Dựa trên thông tin truyện "
        "audio tiếng Việt sau, hãy tạo nội dung cho thumbnail hấp dẫn.\n\n"
        f"Tiêu đề truyện: {script.title}\n"
        f"Thể loại: {script.trope}\n"
        f"Danh sách chương:\n{headings}\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "HOOK: <câu hook 2-4 từ tiếng Việt, IN HOA, giật gân nhưng đúng nội dung "
        "truyện, phù hợp làm chữ nổi bật trên thumbnail>\n"
        "VISUAL: <mô tả bằng tiếng Anh, 1-2 câu, một cảnh cận cảnh nhân vật thể "
        "hiện cảm xúc chủ đạo/cao trào của truyện (ví dụ: shocked expression, "
        "triumphant smirk, tearful determination) - KHÔNG dùng tên riêng, KHÔNG "
        "mô tả toàn bộ cốt truyện>"
    )


def _parse_label(text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise ThumbnailPromptError(
            f"Gemini không trả về nhãn '{label}:' trong output thumbnail"
        )
    start = match.end()

    next_positions = []
    for other in _LABELS:
        if other == label:
            continue
        other_pattern = re.compile(rf"^{re.escape(other)}:", re.MULTILINE)
        other_match = other_pattern.search(text, start)
        if other_match is not None:
            next_positions.append(other_match.start())

    end = min(next_positions) if next_positions else len(text)
    value = text[start:end].strip()
    if not value:
        raise ThumbnailPromptError(f"Gemini trả về nhãn '{label}:' rỗng")
    return value


async def generate_thumbnail_prompt(
    script: Script, client: "GeminiClient | None" = None
) -> ThumbnailPrompt:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    try:
        response = await client.generate_content(build_thumbnail_prompt_request(script))
    except (GeminiError, APIError, AuthError) as exc:
        raise ThumbnailPromptError(
            f"Gemini lỗi khi sinh nội dung thumbnail: {exc}"
        ) from exc

    text = response.text.strip()

    hook_text = _parse_label(text, "HOOK")
    visual_description = _parse_label(text, "VISUAL")

    return ThumbnailPrompt(hook_text=hook_text, visual_description=visual_description)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/thumbnail/test_prompt_generator.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add thumbnail/prompt_generator.py tests/thumbnail/test_prompt_generator.py
git commit -m "feat: generate thumbnail hook text + visual description via Gemini"
```

---

### Task 3: Pillow dependency, bundled font, and `thumbnail/compositor.py`

**Files:**
- Modify: `pyproject.toml`
- Create: `assets/fonts/BeVietnamPro-Black.ttf`
- Create: `assets/fonts/OFL.txt`
- Create: `thumbnail/compositor.py`
- Test: `tests/thumbnail/test_compositor.py`

**Interfaces:**
- Produces: `overlay_hook_text(image_bytes: bytes, hook_text: str) -> bytes` — relied on by Task 5's `thumbnail/cli.py`. Also produces internal helper `_fit_font` and constants `MAX_FONT_SIZE`, `TEXT_WIDTH_RATIO`, `STROKE_WIDTH`, `FONT_PATH` — used directly by this task's own tests only.

- [ ] **Step 1: Add the Pillow dependency**

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
    "mflux",
]
```

Add `"Pillow"` as a new entry at the end:

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
    "Pillow",
]
```

Run: `uv sync`

Expected: completes successfully. Verify: `uv run python3 -c "import PIL; print(PIL.__version__)"` prints a version number (Pillow may already be present transitively, but this makes it an explicit, guaranteed dependency).

- [ ] **Step 2: Download and commit the bundled font**

```bash
mkdir -p assets/fonts
curl -sL "https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/BeVietnamPro-Black.ttf" -o assets/fonts/BeVietnamPro-Black.ttf
curl -sL "https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/OFL.txt" -o assets/fonts/OFL.txt
file assets/fonts/BeVietnamPro-Black.ttf
```

Expected: `file` reports `TrueType Font data` (confirms a real font file was downloaded, not an HTML error page). `assets/fonts/OFL.txt` should start with `Copyright 2021 The Be Vietnam Pro Project Authors` — this is the SIL Open Font License text, kept alongside the font file for attribution.

- [ ] **Step 3: Write the failing tests**

Create `tests/thumbnail/test_compositor.py`:

```python
# tests/thumbnail/test_compositor.py
import io

from PIL import Image

from thumbnail.compositor import (
    MAX_FONT_SIZE,
    STROKE_WIDTH,
    TEXT_WIDTH_RATIO,
    _fit_font,
    overlay_hook_text,
)


def _make_test_image_bytes(width: int = 1280, height: int = 720) -> bytes:
    image = Image.new("RGB", (width, height), "gray")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_overlay_hook_text_returns_valid_png_same_size():
    image_bytes = _make_test_image_bytes()

    result = overlay_hook_text(image_bytes, "PHẢN ĐÒN")

    result_image = Image.open(io.BytesIO(result))
    assert result_image.format == "PNG"
    assert result_image.size == (1280, 720)


def test_overlay_hook_text_uppercases_input():
    image_bytes = _make_test_image_bytes()

    # Should not raise regardless of input case.
    result = overlay_hook_text(image_bytes, "chữ thường")

    result_image = Image.open(io.BytesIO(result))
    assert result_image.size == (1280, 720)


def test_fit_font_uses_max_size_for_short_text():
    image = Image.new("RGB", (1280, 720), "gray")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)

    font = _fit_font(draw, "SỐC", image.width)

    assert font.size == MAX_FONT_SIZE


def test_fit_font_shrinks_long_text_to_fit_width():
    image = Image.new("RGB", (1280, 720), "gray")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    long_hook = "MỘT CÂU HOOK RẤT LÀ DÀI ĐỂ KIỂM TRA CO CHỮ TỰ ĐỘNG THU NHỎ LẠI"

    font = _fit_font(draw, long_hook, image.width)

    bbox = draw.textbbox((0, 0), long_hook, font=font, stroke_width=STROKE_WIDTH)
    text_width = bbox[2] - bbox[0]
    assert text_width <= image.width * TEXT_WIDTH_RATIO
    assert font.size < MAX_FONT_SIZE
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/thumbnail/test_compositor.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'thumbnail.compositor'`.

- [ ] **Step 5: Write the implementation**

Create `thumbnail/compositor.py`:

```python
# thumbnail/compositor.py
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "BeVietnamPro-Black.ttf"
)
MAX_FONT_SIZE = 100
MIN_FONT_SIZE = 40
TEXT_WIDTH_RATIO = 0.9
STROKE_WIDTH = 6


def _fit_font(
    draw: "ImageDraw.ImageDraw", text: str, image_width: int
) -> "ImageFont.FreeTypeFont":
    max_text_width = image_width * TEXT_WIDTH_RATIO
    size = MAX_FONT_SIZE
    while size > MIN_FONT_SIZE:
        font = ImageFont.truetype(str(FONT_PATH), size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
        text_width = bbox[2] - bbox[0]
        if text_width <= max_text_width:
            return font
        size -= 4
    return ImageFont.truetype(str(FONT_PATH), MIN_FONT_SIZE)


def overlay_hook_text(image_bytes: bytes, hook_text: str) -> bytes:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)

    text = hook_text.upper()
    font = _fit_font(draw, text, image.width)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (image.width - text_width) / 2 - bbox[0]
    y = image.height * (2 / 3) - text_height / 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        font=font,
        fill="white",
        stroke_width=STROKE_WIDTH,
        stroke_fill="black",
    )

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/thumbnail/test_compositor.py -v`

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock assets/fonts/BeVietnamPro-Black.ttf assets/fonts/OFL.txt thumbnail/compositor.py tests/thumbnail/test_compositor.py
git commit -m "feat: overlay hook text onto thumbnail image with Pillow"
```

---

### Task 4: `thumbnail/storage.py`

**Files:**
- Create: `thumbnail/storage.py`
- Test: `tests/thumbnail/test_storage.py`

**Interfaces:**
- Produces: `save_thumbnail(trope: str, image_bytes: bytes, output_dir: Path) -> Path` — relied on by Task 5's `thumbnail/cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/thumbnail/test_storage.py`:

```python
# tests/thumbnail/test_storage.py
from thumbnail.storage import save_thumbnail


def test_save_thumbnail_writes_png(tmp_path):
    image_bytes = b"fake png bytes"

    output_path = save_thumbnail("demo", image_bytes, tmp_path)

    assert output_path.exists()
    assert output_path.suffix == ".png"
    assert "demo" in output_path.name
    assert output_path.read_bytes() == image_bytes


def test_save_thumbnail_creates_output_dir_if_missing(tmp_path):
    missing_dir = tmp_path / "nested" / "output"

    output_path = save_thumbnail("demo", b"bytes", missing_dir)

    assert output_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/thumbnail/test_storage.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'thumbnail.storage'`.

- [ ] **Step 3: Write the implementation**

Create `thumbnail/storage.py`:

```python
# thumbnail/storage.py
from datetime import datetime, timezone
from pathlib import Path


def save_thumbnail(trope: str, image_bytes: bytes, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    output_path = output_dir / f"{trope}-{timestamp}.png"
    output_path.write_bytes(image_bytes)

    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/thumbnail/test_storage.py -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add thumbnail/storage.py tests/thumbnail/test_storage.py
git commit -m "feat: persist generated thumbnail PNG to output/thumbnails/"
```

---

### Task 5: `thumbnail/cli.py`

**Files:**
- Create: `thumbnail/cli.py`
- Test: `tests/thumbnail/test_cli.py`

**Interfaces:**
- Consumes: `scripts.models.Script.from_dict(dict) -> Script` (existing), `generate_thumbnail_prompt(script, client) -> ThumbnailPrompt` from Task 2, `generate_thumbnail_image(visual_description: str) -> bytes` from Task 1, `overlay_hook_text(image_bytes: bytes, hook_text: str) -> bytes` from Task 3, `save_thumbnail(trope, image_bytes, output_dir) -> Path` from Task 4.
- Produces: `thumbnail.cli._run(script_path: Path, gemini_client=None) -> None`, `thumbnail.cli.main() -> None`, module constant `thumbnail.cli.OUTPUT_DIR: Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/thumbnail/test_cli.py`:

```python
# tests/thumbnail/test_cli.py
import json
from pathlib import Path

from scripts.models import Chapter, Script
from thumbnail import cli
from thumbnail.prompt_generator import ThumbnailPrompt


async def test_run_generates_and_saves_thumbnail(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_prompt = ThumbnailPrompt(hook_text="SỐC", visual_description="a shocked face")

    async def fake_generate_thumbnail_prompt(script, client):
        return fake_prompt

    def fake_generate_thumbnail_image(visual_description):
        assert visual_description == "a shocked face"
        return b"fake raw image bytes"

    def fake_overlay_hook_text(image_bytes, hook_text):
        assert image_bytes == b"fake raw image bytes"
        assert hook_text == "SỐC"
        return b"fake final image bytes"

    monkeypatch.setattr(cli, "generate_thumbnail_prompt", fake_generate_thumbnail_prompt)
    monkeypatch.setattr(cli, "generate_thumbnail_image", fake_generate_thumbnail_image)
    monkeypatch.setattr(cli, "overlay_hook_text", fake_overlay_hook_text)

    fake_gemini_client = object()
    await cli._run(script_path, gemini_client=fake_gemini_client)

    saved = list((tmp_path / "output").glob("*.png"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"fake final image bytes"

    out = capsys.readouterr().out
    assert "Đã lưu thumbnail" in out


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, gemini_client=None):
        calls.append(script_path)

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "script.json"])

    cli.main()

    assert calls == [Path("script.json")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/thumbnail/test_cli.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'thumbnail.cli'`.

- [ ] **Step 3: Write the implementation**

Create `thumbnail/cli.py`:

```python
# thumbnail/cli.py
import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gemini_webapi import GeminiClient

from scripts.models import Script
from thumbnail.compositor import overlay_hook_text
from thumbnail.generator import generate_thumbnail_image
from thumbnail.prompt_generator import generate_thumbnail_prompt
from thumbnail.storage import save_thumbnail

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "thumbnails"


async def _load_gemini_client() -> GeminiClient:
    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client


async def _run(script_path: Path, gemini_client=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    prompt = await generate_thumbnail_prompt(script, gemini_client)
    image_bytes = generate_thumbnail_image(prompt.visual_description)
    final_bytes = overlay_hook_text(image_bytes, prompt.hook_text)

    output_path = save_thumbnail(script.trope, final_bytes, OUTPUT_DIR)

    print(f"Đã lưu thumbnail: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh thumbnail cho video truyện audio."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/thumbnail/test_cli.py -v`

Expected: 2 passed

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`

Expected: all tests pass (existing suite plus the new `tests/thumbnail/` tests), pristine output.

- [ ] **Step 6: Commit**

```bash
git add thumbnail/cli.py tests/thumbnail/test_cli.py
git commit -m "feat: add thumbnail CLI orchestrating prompt + image + text overlay"
```

---

### Task 6: Document the new stage in the `generating-audiobook-video` skill

**Files:**
- Modify: `.claude/skills/generating-audiobook-video/SKILL.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Update the overview line and stage count**

Find:

```markdown
Chains this repo's five pipeline modules — `scripts` → `tts` → `images` → `video` → `metadata` — into one finished MP4.
```

Replace with:

```markdown
Chains this repo's six pipeline modules — `scripts` → `tts` → `images` → `video` → `thumbnail` → `metadata` — into one finished MP4 (plus a thumbnail PNG).
```

- [ ] **Step 2: Rename the stages table header and renumber stage 5 (metadata) to stage 6**

Find:

```markdown
## The Five Stages
```

Replace with:

```markdown
## The Six Stages
```

Find the table:

```markdown
| # | Command | Reads | Writes (path printed to stdout) |
|---|---------|-------|----------------------------------|
| 1 | `uv run python -m scripts.cli <trope_id>` | `config/tropes.yaml` | `output/scripts/<trope>-<ts>.json` |
| 2 | `uv run python -m tts.cli <script_path>` | stage 1's JSON | `output/audio/<trope>-<ts>.wav` + `.json` (line 2 of stdout, after "Metadata:") |
| 3 | `uv run python -m images.cli <script_path>` | stage 1's JSON | `output/images/<trope>-<ts>.json` + 8 `.png` (metadata path after "Metadata:") |
| 4 | `uv run python -m video.cli <script_path> <tts_metadata_path> <images_metadata_path>` | stage 1 + 2 + 3's JSON | `output/video/<trope>-<ts>.mp4` |
| 5 | `uv run python -m metadata.cli <script_path> <tts_metadata_path> <video_path>` | stage 1 + 2 + 4's output | `output/metadata/<trope>-<ts>.txt` + `.json`; also renames stage 4's `.mp4` in place to an SEO slug |
```

Replace with:

```markdown
| # | Command | Reads | Writes (path printed to stdout) |
|---|---------|-------|----------------------------------|
| 1 | `uv run python -m scripts.cli <trope_id>` | `config/tropes.yaml` | `output/scripts/<trope>-<ts>.json` |
| 2 | `uv run python -m tts.cli <script_path>` | stage 1's JSON | `output/audio/<trope>-<ts>.wav` + `.json` (line 2 of stdout, after "Metadata:") |
| 3 | `uv run python -m images.cli <script_path>` | stage 1's JSON | `output/images/<trope>-<ts>.json` + 8 `.png` (metadata path after "Metadata:") |
| 4 | `uv run python -m video.cli <script_path> <tts_metadata_path> <images_metadata_path>` | stage 1 + 2 + 3's JSON | `output/video/<trope>-<ts>.mp4` |
| 5 | `uv run python -m thumbnail.cli <script_path>` | stage 1's JSON only | `output/thumbnails/<trope>-<ts>.png` |
| 6 | `uv run python -m metadata.cli <script_path> <tts_metadata_path> <video_path>` | stage 1 + 2 + 4's output | `output/metadata/<trope>-<ts>.txt` + `.json`; also renames stage 4's `.mp4` in place to an SEO slug |
```

- [ ] **Step 3: Rename the SEO metadata section header**

Find:

```markdown
## SEO metadata (stage 5)
```

Replace with:

```markdown
## SEO metadata (stage 6)
```

- [ ] **Step 4: Add a Thumbnail section and remove the now-stale manual-thumbnail bullet**

Find:

```markdown
**Manual checklist — do these yourself in YouTube Studio at upload time, this pipeline does not automate them:**

- **Thumbnail**: create a 1280×720 image, high contrast, an emotive face if applicable, ≤4 words of large text. Not generated by this pipeline.
- **Cards & End Screens**: add in YouTube Studio after upload, pointing to related videos/playlists and a subscribe prompt.
```

Replace with:

```markdown
**Manual checklist — do these yourself in YouTube Studio at upload time, this pipeline does not automate them:**

- **Uploading the generated thumbnail**: stage 5 generates `output/thumbnails/<trope>-<ts>.png` automatically — you still have to upload it as the video's thumbnail in YouTube Studio yourself (no API upload).
- **Cards & End Screens**: add in YouTube Studio after upload, pointing to related videos/playlists and a subscribe prompt.
```

Then, right before the `## Example` section, insert a new section:

```markdown
## Thumbnail (stage 5)

Stage 5 generates one `output/thumbnails/<trope>-<ts>.png` (1280×720): mflux renders a dramatic close-up emotional portrait (different style from the background images in stage 3 — those explicitly forbid close-up faces, thumbnails want the opposite), then a short Vietnamese hook phrase (2-4 words, from Gemini) is drawn on top with Pillow using a bundled bold Vietnamese font (`assets/fonts/BeVietnamPro-Black.ttf`) — mflux is never trusted to render the text itself.

Stage 5 only needs the script JSON — it does not depend on stages 2-4's output, so it can run any time after stage 1, though the natural point in a full run is right after stage 4 (video render) finishes.
```

- [ ] **Step 5: Add the thumbnail command to the Example section**

Find:

```markdown
uv run python -m video.cli \
  output/scripts/trong_sinh_bao_thu-20260722T090000Z.json \
  output/audio/trong_sinh_bao_thu-20260722T091500Z.json \
  output/images/trong_sinh_bao_thu-20260722T093000Z.json
# Đã render video vào output/video/trong_sinh_bao_thu-20260722T094500Z.mp4
```
```

Replace with:

```markdown
uv run python -m video.cli \
  output/scripts/trong_sinh_bao_thu-20260722T090000Z.json \
  output/audio/trong_sinh_bao_thu-20260722T091500Z.json \
  output/images/trong_sinh_bao_thu-20260722T093000Z.json
# Đã render video vào output/video/trong_sinh_bao_thu-20260722T094500Z.mp4

uv run python -m thumbnail.cli output/scripts/trong_sinh_bao_thu-20260722T090000Z.json
# Đã lưu thumbnail: output/thumbnails/trong_sinh_bao_thu-20260722T094600Z.png
```
```

- [ ] **Step 6: Add a Common Mistakes bullet**

Find:

```markdown
- **Running stage 5 before stage 4.** It needs the actual rendered `.mp4` path to rename, and the real TTS metadata for chapter timestamps — both only exist after stages 2 and 4 finish.
```

Replace with:

```markdown
- **Running stage 6 (metadata) before stage 4.** It needs the actual rendered `.mp4` path to rename, and the real TTS metadata for chapter timestamps — both only exist after stages 2 and 4 finish. Stage 5 (thumbnail) has no such ordering requirement — it only needs stage 1's script JSON.
```

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/generating-audiobook-video/SKILL.md
git commit -m "docs: document thumbnail as stage 5 in generating-audiobook-video skill"
```

---

### Task 7: Manual smoke test (not automated)

**Files:** none (verification only, no code changes)

**Interfaces:** none — exercises the public entry point `python -m thumbnail.cli <script_path>` built by Tasks 1-5.

- [ ] **Step 1: Confirm a real script JSON is available**

```bash
ls output/scripts/*.json
```

A real one should already exist in this repo from a prior full pipeline run (e.g. `output/scripts/xuyen_khong_gia_toc-*.json`). If none exists, generate one first via `uv run python -m scripts.cli <trope_id>`.

- [ ] **Step 2: Run the thumbnail CLI for real**

```bash
uv run python -m thumbnail.cli output/scripts/<pick-one>.json
```

Expected: no crash. Prints `Đã lưu thumbnail: output/thumbnails/<trope>-<ts>.png`.

- [ ] **Step 3: Review the generated thumbnail**

Open the PNG and confirm:
- Hook text is legible, high contrast, doesn't overflow the frame
- The character/emotion image roughly matches the story's mood, no obviously broken face/anatomy
- No stray text/logos baked in by mflux itself (only the Pillow-drawn hook text should be present)
- Image is exactly 1280×720
