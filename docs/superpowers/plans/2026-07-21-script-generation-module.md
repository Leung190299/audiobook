# Script Generation Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the script-generation module — trope → original Vietnamese story (5,000–8,000 words, 6–10 chapters) generated via Claude API, automatically QA-checked, saved as JSON — as the foundation the TTS/image/video modules will consume later.

**Architecture:** A `scripts/` Python package with clearly separated responsibilities: `models.py` (data classes), `trope_bank.py` (loads the trope config), `prompts.py` + `generator.py` (calls Claude API with forced tool-use for structured output), `qa.py` (automated validation), `storage.py` (saves to disk), and `cli.py` (wires it all together). This is sub-project 1 of the full pipeline in `docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md` — TTS (OmniVoice), image generation (Flux), video assembly (Remotion), metadata, and upload are separate future plans that will consume the JSON files this module produces.

**Tech Stack:** Python 3.11+, `uv` (env/dependency management), `anthropic` SDK (model `claude-sonnet-5`), PyYAML, python-dotenv, pytest.

## Global Constraints

- Kịch bản phải do AI sáng tác **gốc**, lấy cảm hứng từ trope chứ không chuyển thể/dịch một tác phẩm có sẵn cụ thể — bắt buộc thể hiện trong system prompt gửi cho Claude.
- Độ dài kịch bản: 5.000–8.000 từ/tập, chia thành 6–10 chương.
- LLM dùng Claude API (Anthropic), model `claude-sonnet-5`.
- Quản lý môi trường Python bằng `uv`.
- Ngân sách thấp: test tự động không được gọi API Claude thật — luôn dùng mock/fake client.
- Cấu trúc thư mục theo spec đã duyệt: `config/`, `scripts/`, `output/` ở gốc project.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `scripts/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/scripts/__init__.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: an installable `scripts` package and a working `uv` environment that later tasks add modules into.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "audiobook"
version = "0.1.0"
description = "Pipeline sản xuất video truyện audio cho YouTube"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 2: Create package/test directories and `__init__.py` markers**

```bash
mkdir -p config scripts tests/scripts output/scripts
touch scripts/__init__.py tests/__init__.py tests/scripts/__init__.py
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
output/
uv.lock.bak
```

- [ ] **Step 4: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 5: Run `uv sync` and verify the environment builds**

Run: `uv sync`
Expected: creates `.venv/` and `uv.lock`, output ends with something like `Resolved N packages` / `Installed N packages` and no errors.

- [ ] **Step 6: Verify the package imports**

Run: `uv run python -c "import scripts; print('ok')"`
Expected: prints `ok`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example scripts/__init__.py tests/__init__.py tests/scripts/__init__.py uv.lock
git commit -m "chore: scaffold script-generation module project"
```

---

### Task 2: Script & Chapter data models

**Files:**
- Create: `scripts/models.py`
- Test: `tests/scripts/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Chapter(index: int, heading: str, text: str)` with `.word_count`; `Script(trope: str, title: str, chapters: list[Chapter])` with `.word_count`, `.full_text`, `.to_dict() -> dict`, and classmethod `Script.from_dict(data: dict) -> Script`. Used by every later task in this plan.

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_models.py
from scripts.models import Chapter, Script


def test_chapter_word_count():
    chapter = Chapter(index=1, heading="Chương 1", text="một hai ba bốn năm")
    assert chapter.word_count == 5


def test_script_word_count_sums_chapters():
    script = Script(
        trope="trong_sinh_bao_thu",
        title="Tiêu đề",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="một hai ba"),
            Chapter(index=2, heading="Chương 2", text="bốn năm"),
        ],
    )
    assert script.word_count == 5


def test_script_full_text_joins_chapters_with_blank_line():
    script = Script(
        trope="trong_sinh_bao_thu",
        title="Tiêu đề",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    assert script.full_text == "Nội dung một.\n\nNội dung hai."


def test_script_to_dict_and_from_dict_round_trip():
    original = Script(
        trope="trong_sinh_bao_thu",
        title="Tiêu đề",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung.")],
    )
    restored = Script.from_dict(original.to_dict())
    assert restored == original
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/models.py
from dataclasses import dataclass, field


@dataclass
class Chapter:
    index: int
    heading: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class Script:
    trope: str
    title: str
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(chapter.word_count for chapter in self.chapters)

    @property
    def full_text(self) -> str:
        return "\n\n".join(chapter.text for chapter in self.chapters)

    def to_dict(self) -> dict:
        return {
            "trope": self.trope,
            "title": self.title,
            "chapters": [
                {"index": c.index, "heading": c.heading, "text": c.text}
                for c in self.chapters
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Script":
        return cls(
            trope=data["trope"],
            title=data["title"],
            chapters=[
                Chapter(index=c["index"], heading=c["heading"], text=c["text"])
                for c in data["chapters"]
            ],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/models.py tests/scripts/test_models.py
git commit -m "feat: add Script and Chapter data models"
```

---

### Task 3: Trope bank config + loader

**Files:**
- Create: `config/tropes.yaml`
- Create: `scripts/trope_bank.py`
- Test: `tests/scripts/test_trope_bank.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Trope(id: str, name: str, description: str)`; `load_tropes(path: Path) -> list[Trope]`; `get_trope(path: Path, trope_id: str) -> Trope` (raises `KeyError` if not found). Used by `cli.py` in Task 7.

- [ ] **Step 1: Write `config/tropes.yaml`**

```yaml
tropes:
  - id: trong_sinh_bao_thu
    name: "Trọng sinh báo thù"
    description: >
      Nhân vật chính chết oan hoặc bị hại ở kiếp trước, trọng sinh về quá khứ
      với ký ức nguyên vẹn, dùng hiểu biết đó để thay đổi số phận và trả thù
      những kẻ đã hãm hại mình.
  - id: xuyen_khong_gia_toc
    name: "Xuyên không vào gia tộc hào môn"
    description: >
      Nhân vật chính xuyên không vào thân phận một tiểu thư/thiếu gia bị coi
      thường trong gia tộc giàu có, dần bộc lộ thực lực khiến cả nhà kinh ngạc.
  - id: duong_nu_phan_don
    name: "Dưỡng nữ bị hắt hủi rồi phản đòn"
    description: >
      Con nuôi bị gia đình đối xử bất công so với con ruột, sau biến cố phát
      hiện thân thế thật hoặc năng lực đặc biệt, phản đòn ngoạn mục.
  - id: tong_tai_sung_vo
    name: "Tổng tài lạnh lùng sủng vợ"
    description: >
      Vị tổng tài lạnh lùng, quyền lực bất ngờ hết lòng cưng chiều người vợ
      bị xem thường, khiến những kẻ từng coi thường cô phải trả giá.
  - id: anh_chi_em_tranh_sung
    name: "Anh chị em ruột tranh sủng"
    description: >
      Trong một gia đình nhiều anh chị em, nhân vật chính bị lép vế tình cảm
      cha mẹ dành cho anh/chị/em khác, đến khi sự thật và tài năng thật sự
      của nhân vật chính được phơi bày.
```

- [ ] **Step 2: Write the failing test**

```python
# tests/scripts/test_trope_bank.py
import pytest

from scripts.trope_bank import get_trope, load_tropes


def test_load_tropes_returns_all_entries(tmp_path):
    yaml_path = tmp_path / "tropes.yaml"
    yaml_path.write_text(
        "tropes:\n"
        "  - id: demo_id\n"
        "    name: Demo Name\n"
        "    description: Demo description\n",
        encoding="utf-8",
    )

    tropes = load_tropes(yaml_path)

    assert len(tropes) == 1
    assert tropes[0].id == "demo_id"
    assert tropes[0].name == "Demo Name"
    assert tropes[0].description == "Demo description"


def test_get_trope_returns_matching_entry(tmp_path):
    yaml_path = tmp_path / "tropes.yaml"
    yaml_path.write_text(
        "tropes:\n"
        "  - id: a\n    name: A\n    description: desc a\n"
        "  - id: b\n    name: B\n    description: desc b\n",
        encoding="utf-8",
    )

    trope = get_trope(yaml_path, "b")

    assert trope.name == "B"


def test_get_trope_raises_key_error_when_missing(tmp_path):
    yaml_path = tmp_path / "tropes.yaml"
    yaml_path.write_text("tropes:\n  - id: a\n    name: A\n    description: desc\n", encoding="utf-8")

    with pytest.raises(KeyError):
        get_trope(yaml_path, "missing")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_trope_bank.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.trope_bank'`

- [ ] **Step 4: Write minimal implementation**

```python
# scripts/trope_bank.py
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Trope:
    id: str
    name: str
    description: str


def load_tropes(path: Path) -> list[Trope]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [
        Trope(id=t["id"], name=t["name"], description=t["description"])
        for t in data["tropes"]
    ]


def get_trope(path: Path, trope_id: str) -> Trope:
    for trope in load_tropes(path):
        if trope.id == trope_id:
            return trope
    raise KeyError(f"Không tìm thấy trope id={trope_id} trong {path}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_trope_bank.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add config/tropes.yaml scripts/trope_bank.py tests/scripts/test_trope_bank.py
git commit -m "feat: add trope bank config and loader"
```

---

### Task 4: Script QA validation

**Files:**
- Create: `scripts/qa.py`
- Test: `tests/scripts/test_qa.py`

**Interfaces:**
- Consumes: `Script` from `scripts/models.py` (Task 2).
- Produces: `validate_script(script: Script) -> None` (raises `ScriptQAError` on failure); constants `MIN_WORDS=5000`, `MAX_WORDS=8000`, `MIN_CHAPTERS=6`, `MAX_CHAPTERS=10`. Used by `cli.py` in Task 7.

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_qa.py
import pytest

from scripts.models import Chapter, Script
from scripts.qa import ScriptQAError, validate_script


def _make_script(word_count: int, num_chapters: int, extra_text: str = "") -> Script:
    words_per_chapter = word_count // num_chapters
    chapters = [
        Chapter(index=i + 1, heading=f"Chương {i + 1}", text=" ".join(["từ"] * words_per_chapter))
        for i in range(num_chapters)
    ]
    if extra_text:
        chapters[0].text += " " + extra_text
    return Script(trope="demo", title="Tiêu đề", chapters=chapters)


def test_validate_script_passes_for_valid_script():
    script = _make_script(word_count=6000, num_chapters=8)
    validate_script(script)  # không raise


def test_validate_script_raises_when_too_short():
    script = _make_script(word_count=1000, num_chapters=8)
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_many_chapters():
    script = _make_script(word_count=6000, num_chapters=12)
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_when_banned_term_present():
    script = _make_script(word_count=6000, num_chapters=8, extra_text="phù mỏ audio")
    with pytest.raises(ScriptQAError, match="từ khoá bị cấm"):
        validate_script(script)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_qa.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.qa'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/qa.py
from scripts.models import Script

MIN_WORDS = 5000
MAX_WORDS = 8000
MIN_CHAPTERS = 6
MAX_CHAPTERS = 10

BANNED_TERMS = [
    "phù mỏ audio",
]


class ScriptQAError(Exception):
    pass


def validate_script(script: Script) -> None:
    errors = []

    if not (MIN_WORDS <= script.word_count <= MAX_WORDS):
        errors.append(
            f"Độ dài {script.word_count} từ nằm ngoài khoảng {MIN_WORDS}-{MAX_WORDS}."
        )

    if not (MIN_CHAPTERS <= len(script.chapters) <= MAX_CHAPTERS):
        errors.append(
            f"Số chương {len(script.chapters)} nằm ngoài khoảng {MIN_CHAPTERS}-{MAX_CHAPTERS}."
        )

    lowered_text = script.full_text.lower()
    for term in BANNED_TERMS:
        if term in lowered_text:
            errors.append(f"Nội dung chứa từ khoá bị cấm: '{term}'.")

    if errors:
        raise ScriptQAError("; ".join(errors))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_qa.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/qa.py tests/scripts/test_qa.py
git commit -m "feat: add automated script QA validation"
```

---

### Task 5: Script generator (Claude API)

**Files:**
- Create: `scripts/prompts.py`
- Create: `scripts/generator.py`
- Test: `tests/scripts/test_generator.py`

**Interfaces:**
- Consumes: `Script`, `Chapter` from `scripts/models.py` (Task 2).
- Produces: `generate_script(trope_id: str, trope_name: str, trope_description: str, client: anthropic.Anthropic | None = None) -> Script` (raises `ScriptGenerationError`). Used by `cli.py` in Task 7. Tests never call the real Claude API — always pass a fake `client`.

- [ ] **Step 1: Write `scripts/prompts.py`**

```python
# scripts/prompts.py
SYSTEM_PROMPT = """Bạn là biên kịch chuyên viết truyện audio tiếng Việt cho kênh YouTube.
Nhiệm vụ: sáng tác một truyện HOÀN TOÀN GỐC (nguyên tác của bạn), lấy cảm hứng từ
motif/trope được cung cấp — KHÔNG được chuyển thể, dịch, hay mô phỏng sát nội dung
của bất kỳ tiểu thuyết/tác phẩm có sẵn nào. Nhân vật, tên riêng, tình tiết cụ thể
phải do bạn tự sáng tạo.

Yêu cầu:
- Độ dài: 5.000–8.000 từ tiếng Việt.
- Chia thành 6–10 chương, mỗi chương có tiêu đề ngắn gọn.
- Văn phong ưu tiên thoại và diễn biến tâm lý nhân vật hơn là mô tả thị giác thuần
  tuý, vì người nghe không nhìn màn hình khi nghe.
- Có cao trào rõ ràng và kết thúc thoả mãn (không bỏ lửng trừ khi được yêu cầu).
- Không dùng tên nhân vật, địa danh, hoặc chi tiết cốt truyện trùng với tác phẩm nổi
  tiếng nào đang tồn tại.
"""


def build_user_prompt(trope_name: str, trope_description: str) -> str:
    return (
        f"Motif: {trope_name}\n"
        f"Mô tả motif: {trope_description}\n\n"
        "Hãy sáng tác một truyện gốc theo motif trên, tuân thủ đúng yêu cầu trong "
        "system prompt. Gọi tool `output_script` với kết quả."
    )
```

- [ ] **Step 2: Write the failing test**

```python
# tests/scripts/test_generator.py
from unittest.mock import MagicMock

import pytest

from scripts.generator import ScriptGenerationError, generate_script


def test_generate_script_parses_tool_use_response():
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.input = {
        "title": "Ký ức không thể xoá",
        "chapters": [
            {"heading": f"Chương {i}", "text": "Nội dung." * 50} for i in range(1, 7)
        ],
    }
    fake_response = MagicMock()
    fake_response.content = [fake_block]

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    script = generate_script(
        trope_id="trong_sinh_bao_thu",
        trope_name="Trọng sinh báo thù",
        trope_description="Mô tả test.",
        client=fake_client,
    )

    assert script.title == "Ký ức không thể xoá"
    assert script.trope == "trong_sinh_bao_thu"
    assert len(script.chapters) == 6
    assert script.chapters[0].index == 1
    assert script.chapters[0].heading == "Chương 1"
    fake_client.messages.create.assert_called_once()


def test_generate_script_raises_when_no_tool_use_block():
    fake_response = MagicMock()
    fake_response.content = []
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with pytest.raises(ScriptGenerationError):
        generate_script("id", "name", "desc", client=fake_client)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generator'`

- [ ] **Step 4: Write minimal implementation**

```python
# scripts/generator.py
import os

import anthropic

from scripts.models import Chapter, Script
from scripts.prompts import SYSTEM_PROMPT, build_user_prompt

MODEL = "claude-sonnet-5"

OUTPUT_SCRIPT_TOOL = {
    "name": "output_script",
    "description": "Trả về truyện đã sáng tác dưới dạng tiêu đề và danh sách chương.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Tiêu đề truyện, dạng câu hook giật.",
            },
            "chapters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["heading", "text"],
                },
                "minItems": 6,
                "maxItems": 10,
            },
        },
        "required": ["title", "chapters"],
    },
}


class ScriptGenerationError(Exception):
    pass


def generate_script(
    trope_id: str,
    trope_name: str,
    trope_description: str,
    client: "anthropic.Anthropic | None" = None,
) -> Script:
    client = client or anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=[OUTPUT_SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "output_script"},
        messages=[
            {"role": "user", "content": build_user_prompt(trope_name, trope_description)}
        ],
    )

    tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
    if not tool_use_blocks:
        raise ScriptGenerationError("Claude không trả về tool_use block nào.")

    data = tool_use_blocks[0].input
    chapters = [
        Chapter(index=i + 1, heading=chapter["heading"], text=chapter["text"])
        for i, chapter in enumerate(data["chapters"])
    ]
    return Script(trope=trope_id, title=data["title"], chapters=chapters)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_generator.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/prompts.py scripts/generator.py tests/scripts/test_generator.py
git commit -m "feat: add Claude-based script generator"
```

---

### Task 6: Storage

**Files:**
- Create: `scripts/storage.py`
- Test: `tests/scripts/test_storage.py`

**Interfaces:**
- Consumes: `Script` from `scripts/models.py` (Task 2).
- Produces: `save_script(script: Script, output_dir: Path) -> Path`. Used by `cli.py` in Task 7.

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_storage.py
import json

from scripts.models import Chapter, Script
from scripts.storage import save_script


def test_save_script_writes_json_file(tmp_path):
    script = Script(
        trope="test_trope",
        title="Tiêu đề",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung")],
    )

    out_path = save_script(script, tmp_path)

    assert out_path.exists()
    assert out_path.parent == tmp_path
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề"
    assert data["trope"] == "test_trope"


def test_save_script_creates_output_dir_if_missing(tmp_path):
    script = Script(trope="t", title="T", chapters=[Chapter(1, "C1", "nội dung")])
    missing_dir = tmp_path / "nested" / "output"

    out_path = save_script(script, missing_dir)

    assert out_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/storage.py
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.models import Script


def save_script(script: Script, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = output_dir / f"{script.trope}-{timestamp}.json"
    out_path.write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_storage.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/storage.py tests/scripts/test_storage.py
git commit -m "feat: add script storage to disk"
```

---

### Task 7: CLI entrypoint

**Files:**
- Create: `scripts/cli.py`
- Test: `tests/scripts/test_cli.py`

**Interfaces:**
- Consumes: `get_trope` (Task 3), `generate_script` (Task 5), `validate_script` (Task 4), `save_script` (Task 6).
- Produces: `main() -> None`, module-level `CONFIG_PATH: Path` and `OUTPUT_DIR: Path` (both overridable via monkeypatch for testing). This is the last piece of sub-project 1; later plans (TTS module) will read the JSON files this CLI writes to `output/scripts/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_cli.py
import json

from scripts import cli
from scripts.models import Chapter, Script
from scripts.trope_bank import Trope


def test_main_generates_validates_and_saves_script(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "CONFIG_PATH", tmp_path / "tropes.yaml")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    fake_trope = Trope(id="demo", name="Demo", description="Mô tả demo")
    monkeypatch.setattr(cli, "get_trope", lambda path, trope_id: fake_trope)

    fake_script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung " * 10)],
    )
    monkeypatch.setattr(cli, "generate_script", lambda *args, **kwargs: fake_script)

    validated_scripts = []
    monkeypatch.setattr(cli, "validate_script", validated_scripts.append)

    monkeypatch.setattr("sys.argv", ["cli.py", "demo"])
    cli.main()

    assert validated_scripts == [fake_script]
    saved_files = list((tmp_path / "output").glob("*.json"))
    assert len(saved_files) == 1
    data = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"

    out = capsys.readouterr().out
    assert "Đã lưu kịch bản" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/cli.py
import argparse
from pathlib import Path

from dotenv import load_dotenv

from scripts.generator import generate_script
from scripts.qa import validate_script
from scripts.storage import save_script
from scripts.trope_bank import get_trope

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tropes.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "scripts"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh kịch bản truyện audio từ trope.")
    parser.add_argument("trope_id", help="ID trope trong config/tropes.yaml")
    args = parser.parse_args()

    trope = get_trope(CONFIG_PATH, args.trope_id)
    script = generate_script(trope.id, trope.name, trope.description)
    validate_script(script)
    out_path = save_script(script, OUTPUT_DIR)

    print(
        f"Đã lưu kịch bản: {out_path} "
        f"({script.word_count} từ, {len(script.chapters)} chương)"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_cli.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS (all tests across Task 2–7, no real API calls made)

- [ ] **Step 6: Commit**

```bash
git add scripts/cli.py tests/scripts/test_cli.py
git commit -m "feat: add script generation CLI entrypoint"
```

- [ ] **Step 7: Manual smoke test with the real Claude API (not automated — costs real API usage)**

1. Copy `.env.example` to `.env` and fill in a real `ANTHROPIC_API_KEY`.
2. Run: `uv run python -m scripts.cli trong_sinh_bao_thu`
3. Expected: prints `Đã lưu kịch bản: output/scripts/trong_sinh_bao_thu-<timestamp>.json (N từ, M chương)` with N in 5000–8000 and M in 6–10.
4. Open the saved JSON file and read at least one chapter to confirm the story is original (not a recognizable retelling of an existing novel) and reads naturally for audio narration.

---

## Self-Review Notes

- **Spec coverage**: This plan implements spec section 2 pipeline steps 1–2 (LLM script generation + automated QA) for the "Sinh kịch bản" stage only. Steps 3–9 (TTS, image gen, video assembly, metadata, upload) are explicitly out of scope — each needs its own plan per the Scope Check in the spec, since they are independent subsystems with different toolchains (OmniVoice, Flux, Remotion/Node, YouTube API).
- **Placeholder scan**: no TBD/TODO; every step has runnable code or an exact command with expected output.
- **Type consistency**: `Chapter(index, heading, text)` and `Script(trope, title, chapters)` from Task 2 are used with the same field names/order across Tasks 4–7. `generate_script(trope_id, trope_name, trope_description, client=None) -> Script` and `save_script(script, output_dir) -> Path` signatures match how `cli.py` calls them.
