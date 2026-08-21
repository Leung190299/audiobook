# Kế hoạch triển khai module Shorts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi tập truyện dài sinh thêm một video dọc 1080×1920 dài 60-80 giây, trích chương gay cấn nhất, kết bằng card kêu gọi nghe trọn tập trên kênh.

**Architecture:** Một stage độc lập `shorts/` chỉ đọc output của stage 1 (kịch bản) và stage 3 (ảnh nền), nên chạy được cả cho tập cũ. Gemini chọn chương và trích đoạn; đoạn trích được tách thành câu và đọc từng câu một để lấy mốc thời gian thật cho phụ đề; Remotion render composition dọc mới.

**Tech Stack:** Python 3.14 + uv, `gemini-webapi`, VieNeu-TTS (ONNX, CPU), Remotion 4.0.495, pytest (`asyncio_mode = "auto"`).

**Spec:** [docs/superpowers/specs/2026-08-21-shorts-module-design.md](../specs/2026-08-21-shorts-module-design.md)

## Global Constraints

- Mọi thông báo lỗi và chuỗi in ra stdout đều bằng tiếng Việt, theo đúng giọng văn các module hiện có.
- Không viết code TTS mới — dùng lại `tts.synthesizer`, `tts.audio_postprocess`, `tts.voice_profile`.
- Đoạn trích hợp lệ: 120-250 từ (`MIN_EXCERPT_WORDS` / `MAX_EXCERPT_WORDS`).
- Khoảng nghỉ giữa các câu khi ghép audio: 0.15 giây — KHÔNG dùng `gap_seconds` trong `config/voice.yaml` (giá trị đó dành cho khoảng nghỉ giữa chương).
- Card CTA cuối video: 4.0 giây (`CTA_SECONDS`).
- Hook hiện ở 3 giây đầu (`HOOK_SECONDS` trong `ShortVideo.tsx`).
- Đường dẫn trong props là đường dẫn tương đối so với gốc repo; Remotion luôn được gọi kèm `--public-dir=<repo_root>`.
- Gemini trả lời theo nhãn dòng-đơn (`CHAPTER:`, `HOOK:`, ...), KHÔNG dùng JSON.
- Mọi file output nằm trong `output/shorts/`, dùng chung một `stem` dạng `<trope>-<YYYYMMDDTHHMMSSZ>`.

---

### Task 1: `shorts/excerpt.py` — Gemini chọn chương và trích đoạn

**Files:**
- Create: `shorts/__init__.py`
- Create: `shorts/excerpt.py`
- Create: `tests/shorts/__init__.py`
- Test: `tests/shorts/test_excerpt.py`

**Interfaces:**
- Consumes: `scripts.models.Script`, `scripts.models.Chapter`
- Produces:
  - `ShortExcerpt(chapter_index: int, hook_text: str, excerpt_text: str, short_title: str, short_description: str)`
  - `ShortExcerptError(Exception)`
  - `MIN_EXCERPT_WORDS = 120`, `MAX_EXCERPT_WORDS = 250`
  - `build_excerpt_prompt(script: Script) -> str`
  - `split_sentences(text: str) -> list[str]`
  - `async generate_short_excerpt(script: Script, client=None) -> ShortExcerpt`

- [ ] **Step 1: Tạo package rỗng**

```bash
cd /Users/lee/Project/Apps/audiobook
touch shorts/__init__.py tests/shorts/__init__.py
```

Lệnh trên giả định thư mục đã tồn tại; tạo trước nếu chưa:

```bash
mkdir -p shorts tests/shorts && touch shorts/__init__.py tests/shorts/__init__.py
```

- [ ] **Step 2: Viết test thất bại**

Tạo `tests/shorts/test_excerpt.py`:

```python
# tests/shorts/test_excerpt.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.models import Chapter, Script
from shorts.excerpt import (
    ShortExcerptError,
    build_excerpt_prompt,
    generate_short_excerpt,
    split_sentences,
)


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


def _sample_script() -> Script:
    return Script(
        trope="trong_sinh_bao_thu",
        title="Trọng Sinh Báo Thù",
        chapters=[
            Chapter(index=1, heading="Chương 1: Mở đầu", text="Câu chuyện bắt đầu."),
            Chapter(index=2, heading="Chương 2: Cao trào", text="Mọi thứ vỡ vụn."),
        ],
    )


def _excerpt_of(word_count: int) -> str:
    return " ".join(["từ"] * word_count)


def _response(chapter: str = "2", excerpt_words: int = 150) -> str:
    return (
        f"CHAPTER: {chapter}\n"
        "HOOK: CÔ ẤY BIẾT HẾT RỒI\n"
        f"EXCERPT: {_excerpt_of(excerpt_words)}\n"
        "TITLE: Trọng sinh báo thù - đoạn gay cấn nhất\n"
        "DESCRIPTION: Nghe full trên kênh nhé. #shorts"
    )


async def test_parse_day_du_nam_nhan():
    client = _make_fake_client(_response())

    excerpt = await generate_short_excerpt(_sample_script(), client=client)

    assert excerpt.chapter_index == 2
    assert excerpt.hook_text == "CÔ ẤY BIẾT HẾT RỒI"
    assert len(excerpt.excerpt_text.split()) == 150
    assert excerpt.short_title == "Trọng sinh báo thù - đoạn gay cấn nhất"
    assert excerpt.short_description == "Nghe full trên kênh nhé. #shorts"


async def test_thieu_nhan_thi_bao_loi():
    client = _make_fake_client("HOOK: CHỈ CÓ HOOK THÔI")

    with pytest.raises(ShortExcerptError, match="CHAPTER"):
        await generate_short_excerpt(_sample_script(), client=client)


async def test_chapter_ngoai_pham_vi_thi_bao_loi():
    client = _make_fake_client(_response(chapter="9"))

    with pytest.raises(ShortExcerptError, match="chương 9"):
        await generate_short_excerpt(_sample_script(), client=client)


async def test_chapter_khong_phai_so_thi_bao_loi():
    client = _make_fake_client(_response(chapter="chương hai"))

    with pytest.raises(ShortExcerptError, match="số chương"):
        await generate_short_excerpt(_sample_script(), client=client)


@pytest.mark.parametrize("word_count", [119, 251])
async def test_doan_trich_sai_do_dai_thi_bao_loi(word_count):
    client = _make_fake_client(_response(excerpt_words=word_count))

    with pytest.raises(ShortExcerptError, match="120-250"):
        await generate_short_excerpt(_sample_script(), client=client)


async def test_gemini_loi_thi_boc_thanh_loi_cua_module():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("hỏng"))

    with pytest.raises(ShortExcerptError, match="Gemini"):
        await generate_short_excerpt(_sample_script(), client=fake_client)


def test_prompt_chua_noi_dung_tung_chuong():
    prompt = build_excerpt_prompt(_sample_script())

    assert "Câu chuyện bắt đầu." in prompt
    assert "Mọi thứ vỡ vụn." in prompt
    assert "[Chương 2]" in prompt


def test_tach_cau_theo_dau_ket_cau():
    assert split_sentences("Cô ấy đến. Trời mưa! Anh biết chứ?") == [
        "Cô ấy đến.",
        "Trời mưa!",
        "Anh biết chứ?",
    ]


def test_cau_qua_ngan_duoc_gop_vao_cau_truoc():
    assert split_sentences("Cô ấy bước vào phòng khách. Im lặng.") == [
        "Cô ấy bước vào phòng khách. Im lặng."
    ]


def test_tach_cau_chuoi_rong():
    assert split_sentences("   ") == []
```

- [ ] **Step 3: Chạy test để chắc chắn nó fail**

Run: `uv run pytest tests/shorts/test_excerpt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shorts.excerpt'`

- [ ] **Step 4: Viết `shorts/excerpt.py`**

```python
# shorts/excerpt.py
"""Chọn chương gay cấn nhất và trích đoạn để dựng video ngắn.

Một lần gọi Gemini duy nhất trả về cả 5 thứ (chương, hook, đoạn trích, tiêu đề,
mô tả). Dùng nhãn dòng-đơn chứ không JSON — cùng lý do đã ghi ở
`metadata/seo_generator.py`: gemini-webapi trả JSON không đủ tin cậy.

`_parse_label` cố tình lặp lại logic của `metadata/seo_generator.py` thay vì dùng
chung: bộ nhãn khác nhau và loại exception khác nhau, gom lại sẽ phải truyền cả
hai thứ đó vào — đúng tiền lệ `thumbnail/prompt_generator.py` đã làm.
"""

import os
import re
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.models import Script


class ShortExcerptError(Exception):
    pass


@dataclass
class ShortExcerpt:
    chapter_index: int
    hook_text: str
    excerpt_text: str
    short_title: str
    short_description: str


MIN_EXCERPT_WORDS = 120
MAX_EXCERPT_WORDS = 250

# Câu ngắn hơn ngưỡng này bị gộp vào câu liền trước — phụ đề nhấp nháy khó đọc.
MIN_SENTENCE_CHARS = 15

_LABELS = ("CHAPTER", "HOOK", "EXCERPT", "TITLE", "DESCRIPTION")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def build_excerpt_prompt(script: Script) -> str:
    chapters_block = "\n\n".join(
        f"[Chương {c.index}] {c.heading}\n{c.text}" for c in script.chapters
    )
    return (
        "Bạn là biên tập viên video ngắn cho kênh truyện audio tiếng Việt. "
        "Nhiệm vụ: chọn đoạn kịch tính nhất trong truyện dưới đây để dựng một video "
        "Shorts dài khoảng 60-80 giây, mục đích kéo người xem về nghe trọn tập.\n\n"
        f"Tiêu đề truyện: {script.title}\n\n"
        f"Nội dung các chương:\n{chapters_block}\n\n"
        "Yêu cầu:\n"
        "- Chọn đúng MỘT chương có tình huống gay cấn nhất.\n"
        f"- Trích {MIN_EXCERPT_WORDS}-{MAX_EXCERPT_WORDS} từ liền mạch trong chương đó, "
        "giữ nguyên văn phong gốc.\n"
        "- Bắt đầu bằng một câu hoàn chỉnh, kết thúc ngay tại cao trào để người nghe "
        "tò mò. KHÔNG tiết lộ kết cục.\n\n"
        "Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, "
        "KHÔNG thêm giải thích nào khác:\n\n"
        "CHAPTER: <số thứ tự chương, chỉ ghi số>\n"
        "HOOK: <câu giật tít 4-10 từ, VIẾT HOA TOÀN BỘ>\n"
        "EXCERPT: <đoạn trích để đọc>\n"
        "TITLE: <tiêu đề đăng Shorts, tối đa 100 ký tự>\n"
        "DESCRIPTION: <mô tả 2-3 câu, có kêu gọi nghe full trên kênh, "
        "kết thúc bằng #shorts>"
    )


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_END.split(text.strip()) if p.strip()]

    merged: list[str] = []
    for part in parts:
        if merged and len(part) < MIN_SENTENCE_CHARS:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def _parse_label(text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise ShortExcerptError(f"Gemini không trả về nhãn '{label}:' khi chọn đoạn trích")
    start = match.end()

    next_positions = []
    for other in _LABELS:
        if other == label:
            continue
        other_match = re.compile(rf"^{re.escape(other)}:", re.MULTILINE).search(text, start)
        if other_match is not None:
            next_positions.append(other_match.start())

    end = min(next_positions) if next_positions else len(text)
    value = text[start:end].strip()
    if not value:
        raise ShortExcerptError(f"Gemini trả về nhãn '{label}:' rỗng")
    return value


def _parse_chapter_index(raw: str, script: Script) -> int:
    match = re.search(r"\d+", raw)
    if match is None:
        raise ShortExcerptError(f"Không đọc được số chương từ Gemini: {raw!r}")

    index = int(match.group())
    valid = {c.index for c in script.chapters}
    if index not in valid:
        raise ShortExcerptError(
            f"Gemini chọn chương {index} nhưng kịch bản chỉ có chương "
            f"{min(valid)}-{max(valid)}"
        )
    return index


async def generate_short_excerpt(
    script: Script, client: "GeminiClient | None" = None
) -> ShortExcerpt:
    if client is None:
        client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    try:
        response = await client.generate_content(build_excerpt_prompt(script))
    except (GeminiError, APIError, AuthError) as exc:
        raise ShortExcerptError(f"Gemini lỗi khi chọn đoạn trích: {exc}") from exc

    text = response.text.strip()

    chapter_index = _parse_chapter_index(_parse_label(text, "CHAPTER"), script)
    excerpt_text = _parse_label(text, "EXCERPT")

    word_count = len(excerpt_text.split())
    if not MIN_EXCERPT_WORDS <= word_count <= MAX_EXCERPT_WORDS:
        raise ShortExcerptError(
            f"Đoạn trích dài {word_count} từ, nằm ngoài khoảng "
            f"{MIN_EXCERPT_WORDS}-{MAX_EXCERPT_WORDS}"
        )

    return ShortExcerpt(
        chapter_index=chapter_index,
        hook_text=_parse_label(text, "HOOK"),
        excerpt_text=excerpt_text,
        short_title=_parse_label(text, "TITLE"),
        short_description=_parse_label(text, "DESCRIPTION"),
    )
```

- [ ] **Step 5: Chạy test để chắc chắn nó pass**

Run: `uv run pytest tests/shorts/test_excerpt.py -v`
Expected: PASS — 11 passed

- [ ] **Step 6: Commit**

```bash
git add shorts/__init__.py shorts/excerpt.py tests/shorts/__init__.py tests/shorts/test_excerpt.py
git commit -m "feat(shorts): chọn chương gay cấn và trích đoạn bằng Gemini"
```

---

### Task 2: `shorts/props_builder.py` — dựng props cho Remotion

**Files:**
- Create: `shorts/props_builder.py`
- Test: `tests/shorts/test_props_builder.py`

**Interfaces:**
- Consumes: `shorts.excerpt.ShortExcerpt`, `tts.audio_postprocess.ChapterTiming`, `scripts.models.Script`
- Produces:
  - `ShortPropsBuildError(Exception)`
  - `CTA_SECONDS = 4.0`
  - `build_short_props(script, excerpt, sentences, timings, images_metadata, audio_path, images_dir, repo_root, cta_seconds=CTA_SECONDS) -> dict`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/shorts/test_props_builder.py`:

```python
# tests/shorts/test_props_builder.py
from pathlib import Path

import pytest

from scripts.models import Chapter, Script
from shorts.excerpt import ShortExcerpt
from shorts.props_builder import ShortPropsBuildError, build_short_props
from tts.audio_postprocess import ChapterTiming


def _script() -> Script:
    return Script(
        trope="trong_sinh_bao_thu",
        title="Trọng Sinh Báo Thù",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="..."),
            Chapter(index=2, heading="Chương 2", text="..."),
        ],
    )


def _excerpt() -> ShortExcerpt:
    return ShortExcerpt(
        chapter_index=2,
        hook_text="CÔ ẤY BIẾT HẾT RỒI",
        excerpt_text="Cô ấy đến. Trời mưa.",
        short_title="Tiêu đề short",
        short_description="Mô tả short #shorts",
    )


def _images_metadata() -> dict:
    return {
        "trope": "trong_sinh_bao_thu",
        "title": "Trọng Sinh Báo Thù",
        "chapters": [
            {"index": 1, "filename": "anh-1.png", "scene_description": "..."},
            {"index": 2, "filename": "anh-2.png", "scene_description": "..."},
        ],
    }


def _timings() -> list[ChapterTiming]:
    return [
        ChapterTiming(index=1, heading="Câu 1", start_seconds=0.0, end_seconds=2.5),
        ChapterTiming(index=2, heading="Câu 2", start_seconds=2.65, end_seconds=5.0),
    ]


def _setup_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path
    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-1.png").write_bytes(b"x")
    (images_dir / "anh-2.png").write_bytes(b"x")

    audio_dir = repo_root / "output" / "shorts"
    audio_dir.mkdir(parents=True)
    audio_path = audio_dir / "trong_sinh_bao_thu-20260822T010000Z.wav"
    audio_path.write_bytes(b"x")

    return repo_root, images_dir, audio_path


def test_props_dung_anh_cua_chuong_duoc_chon(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    props = build_short_props(
        script=_script(),
        excerpt=_excerpt(),
        sentences=["Cô ấy đến.", "Trời mưa."],
        timings=_timings(),
        images_metadata=_images_metadata(),
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=repo_root,
    )

    assert props["imagePath"] == "output/images/anh-2.png"
    assert props["audioPath"] == "output/shorts/trong_sinh_bao_thu-20260822T010000Z.wav"
    assert props["hookText"] == "CÔ ẤY BIẾT HẾT RỒI"
    assert props["title"] == "Trọng Sinh Báo Thù"
    assert props["trope"] == "trong_sinh_bao_thu"


def test_moi_cau_giu_dung_moc_thoi_gian_that(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    props = build_short_props(
        script=_script(),
        excerpt=_excerpt(),
        sentences=["Cô ấy đến.", "Trời mưa."],
        timings=_timings(),
        images_metadata=_images_metadata(),
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=repo_root,
    )

    assert props["captions"] == [
        {"text": "Cô ấy đến.", "startSeconds": 0.0, "endSeconds": 2.5},
        {"text": "Trời mưa.", "startSeconds": 2.65, "endSeconds": 5.0},
    ]
    assert props["audioDurationSeconds"] == 5.0
    assert props["ctaSeconds"] == 4.0


def test_lech_so_cau_va_so_moc_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    with pytest.raises(ShortPropsBuildError, match="không khớp"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=["Chỉ một câu."],
            timings=_timings(),
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_khong_co_anh_cho_chuong_do_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    images_metadata = _images_metadata()
    images_metadata["chapters"] = [images_metadata["chapters"][0]]

    with pytest.raises(ShortPropsBuildError, match="chương 2"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=["Cô ấy đến.", "Trời mưa."],
            timings=_timings(),
            images_metadata=images_metadata,
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_file_anh_khong_ton_tai_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    (images_dir / "anh-2.png").unlink()

    with pytest.raises(ShortPropsBuildError, match="Không tìm thấy file ảnh"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=["Cô ấy đến.", "Trời mưa."],
            timings=_timings(),
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )


def test_khong_co_cau_nao_thi_bao_loi(tmp_path: Path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)

    with pytest.raises(ShortPropsBuildError, match="Không có câu nào"):
        build_short_props(
            script=_script(),
            excerpt=_excerpt(),
            sentences=[],
            timings=[],
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `uv run pytest tests/shorts/test_props_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shorts.props_builder'`

- [ ] **Step 3: Viết `shorts/props_builder.py`**

```python
# shorts/props_builder.py
from pathlib import Path

from scripts.models import Script
from shorts.excerpt import ShortExcerpt
from tts.audio_postprocess import ChapterTiming


class ShortPropsBuildError(Exception):
    pass


CTA_SECONDS = 4.0


def build_short_props(
    script: Script,
    excerpt: ShortExcerpt,
    sentences: list[str],
    timings: list[ChapterTiming],
    images_metadata: dict,
    audio_path: Path,
    images_dir: Path,
    repo_root: Path,
    cta_seconds: float = CTA_SECONDS,
) -> dict:
    if not sentences or not timings:
        raise ShortPropsBuildError("Không có câu nào để dựng short")

    if len(sentences) != len(timings):
        raise ShortPropsBuildError(
            f"Số câu ({len(sentences)}) không khớp số mốc thời gian ({len(timings)})"
        )

    images_by_index = {c["index"]: c for c in images_metadata["chapters"]}
    image_chapter = images_by_index.get(excerpt.chapter_index)
    if image_chapter is None:
        raise ShortPropsBuildError(
            f"Metadata ảnh không có chương {excerpt.chapter_index}"
        )

    image_path = images_dir / image_chapter["filename"]
    if not image_path.exists():
        raise ShortPropsBuildError(f"Không tìm thấy file ảnh: {image_path}")

    captions = [
        {
            "text": sentence,
            "startSeconds": timing.start_seconds,
            "endSeconds": timing.end_seconds,
        }
        for sentence, timing in zip(sentences, timings)
    ]

    return {
        "trope": script.trope,
        "title": script.title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "imagePath": str(image_path.relative_to(repo_root)),
        "hookText": excerpt.hook_text,
        "captions": captions,
        "audioDurationSeconds": timings[-1].end_seconds,
        "ctaSeconds": cta_seconds,
    }
```

- [ ] **Step 4: Chạy test để chắc chắn nó pass**

Run: `uv run pytest tests/shorts/test_props_builder.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add shorts/props_builder.py tests/shorts/test_props_builder.py
git commit -m "feat(shorts): dựng props Remotion từ đoạn trích và mốc thời gian"
```

---

### Task 3: `shorts/storage.py` — lưu audio, props, metadata

**Files:**
- Create: `shorts/storage.py`
- Test: `tests/shorts/test_storage.py`

**Interfaces:**
- Consumes: `shorts.excerpt.ShortExcerpt`
- Produces:
  - `make_stem(trope: str) -> str`
  - `save_short_audio(stem: str, audio: np.ndarray, sample_rate: int, output_dir: Path) -> Path`
  - `save_short_props(stem: str, props: dict, output_dir: Path) -> Path`
  - `short_video_path(stem: str, output_dir: Path) -> Path`
  - `save_short_metadata(stem: str, excerpt: ShortExcerpt, episode_title: str, video_filename: str, output_dir: Path) -> Path`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/shorts/test_storage.py`:

```python
# tests/shorts/test_storage.py
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from shorts.excerpt import ShortExcerpt
from shorts.storage import (
    make_stem,
    save_short_audio,
    save_short_metadata,
    save_short_props,
    short_video_path,
)


def _excerpt() -> ShortExcerpt:
    return ShortExcerpt(
        chapter_index=2,
        hook_text="CÔ ẤY BIẾT HẾT RỒI",
        excerpt_text="Cô ấy đến.",
        short_title="Trọng sinh báo thù - đoạn gay cấn nhất",
        short_description="Nghe full trên kênh nhé. #shorts",
    )


def test_stem_gom_trope_va_timestamp_utc():
    stem = make_stem("trong_sinh_bao_thu")

    assert re.fullmatch(r"trong_sinh_bao_thu-\d{8}T\d{6}Z", stem)


def test_moi_file_dung_chung_mot_stem(tmp_path: Path):
    stem = "trong_sinh_bao_thu-20260822T010000Z"
    audio = np.zeros(2400, dtype=np.float32)

    audio_path = save_short_audio(stem, audio, 24000, tmp_path)
    props_path = save_short_props(stem, {"trope": "x"}, tmp_path)
    video_path = short_video_path(stem, tmp_path)

    assert audio_path.name == f"{stem}.wav"
    assert props_path.name == f"{stem}-props.json"
    assert video_path.name == f"{stem}.mp4"


def test_luu_audio_doc_lai_duoc(tmp_path: Path):
    audio = np.zeros(2400, dtype=np.float32)

    path = save_short_audio("abc-20260822T010000Z", audio, 24000, tmp_path)

    data, sample_rate = sf.read(path)
    assert sample_rate == 24000
    assert len(data) == 2400


def test_luu_props_giu_nguyen_tieng_viet(tmp_path: Path):
    props = {"hookText": "CÔ ẤY BIẾT HẾT RỒI"}

    path = save_short_props("abc-20260822T010000Z", props, tmp_path)

    assert json.loads(path.read_text(encoding="utf-8")) == props
    assert "CÔ ẤY BIẾT HẾT RỒI" in path.read_text(encoding="utf-8")


def test_file_metadata_du_bon_muc(tmp_path: Path):
    path = save_short_metadata(
        "abc-20260822T010000Z",
        _excerpt(),
        episode_title="Trọng Sinh Báo Thù",
        video_filename="abc-20260822T010000Z.mp4",
        output_dir=tmp_path,
    )

    content = path.read_text(encoding="utf-8")
    assert path.name == "abc-20260822T010000Z.txt"
    assert "TIÊU ĐỀ:\nTrọng sinh báo thù - đoạn gay cấn nhất" in content
    assert "MÔ TẢ:\nNghe full trên kênh nhé. #shorts" in content
    assert "TẬP ĐẦY ĐỦ:\nTrọng Sinh Báo Thù" in content
    assert "TÊN FILE VIDEO:\nabc-20260822T010000Z.mp4" in content


def test_tu_tao_thu_muc_neu_chua_co(tmp_path: Path):
    output_dir = tmp_path / "chua" / "ton" / "tai"

    path = save_short_props("abc-20260822T010000Z", {}, output_dir)

    assert path.exists()
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `uv run pytest tests/shorts/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shorts.storage'`

- [ ] **Step 3: Viết `shorts/storage.py`**

```python
# shorts/storage.py
"""Lưu output của stage short.

Khác `tts/storage.py` và `video/storage.py` ở chỗ: timestamp được sinh MỘT LẦN qua
`make_stem()` rồi truyền vào từng hàm lưu, để cả .wav/.mp4/-props.json/.txt của cùng
một lượt chạy dùng chung một tên gốc. Nếu mỗi hàm tự sinh timestamp thì bốn file sẽ
lệch nhau vài giây và rất khó ghép lại khi cần lần vết.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from shorts.excerpt import ShortExcerpt


def make_stem(trope: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{trope}-{timestamp}"


def save_short_audio(
    stem: str, audio: np.ndarray, sample_rate: int, output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}.wav"
    sf.write(path, audio, sample_rate)
    return path


def save_short_props(stem: str, props: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}-props.json"
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def short_video_path(stem: str, output_dir: Path) -> Path:
    return output_dir / f"{stem}.mp4"


def save_short_metadata(
    stem: str,
    excerpt: ShortExcerpt,
    episode_title: str,
    video_filename: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}.txt"
    path.write_text(
        f"TIÊU ĐỀ:\n{excerpt.short_title}\n\n"
        f"MÔ TẢ:\n{excerpt.short_description}\n\n"
        f"TẬP ĐẦY ĐỦ:\n{episode_title}\n\n"
        f"TÊN FILE VIDEO:\n{video_filename}\n",
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Chạy test để chắc chắn nó pass**

Run: `uv run pytest tests/shorts/test_storage.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add shorts/storage.py tests/shorts/test_storage.py
git commit -m "feat(shorts): lưu audio, props và metadata theo chung một stem"
```

---

### Task 4: Composition dọc `ShortVideo` trong Remotion

**Files:**
- Create: `remotion/src/ShortVideo.tsx`
- Modify: `remotion/src/types.ts` (thêm `ShortProps`, `ShortCaption`)
- Modify: `remotion/src/Root.tsx` (đăng ký composition thứ hai)

**Interfaces:**
- Consumes: props JSON do `shorts/props_builder.build_short_props` sinh ra
- Produces: composition id `ShortVideo`, 1080×1920, 30fps — `shorts/cli.py` gọi bằng đúng id này

- [ ] **Step 1: Thêm kiểu vào `remotion/src/types.ts`**

Nối vào cuối file (giữ nguyên `ChapterProps` và `VideoProps` đang có):

```ts
export interface ShortCaption {
  text: string;
  startSeconds: number;
  endSeconds: number;
}

export interface ShortProps {
  trope: string;
  title: string;
  audioPath: string;
  imagePath: string;
  hookText: string;
  captions: ShortCaption[];
  audioDurationSeconds: number;
  ctaSeconds: number;
}
```

- [ ] **Step 2: Tạo `remotion/src/ShortVideo.tsx`**

```tsx
import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { ShortProps } from "./types";

// Hook chỉ hiện ở đầu video — sau đó nhường chỗ cho phụ đề.
const HOOK_SECONDS = 3;
const FONT_FAMILY = "BeVietnamPro, sans-serif";

// Font đóng gói trong repo, nạp qua FontFace API. Phải chặn render bằng
// delayRender cho tới khi font sẵn sàng, nếu không khung hình đầu sẽ render
// bằng font dự phòng rồi mới đổi giữa chừng.
const useBeVietnamPro = () => {
  const [handle] = useState(() => delayRender("Đang nạp font Be Vietnam Pro"));

  useEffect(() => {
    const font = new FontFace(
      "BeVietnamPro",
      `url(${staticFile("assets/fonts/BeVietnamPro-Black.ttf")}) format("truetype")`
    );
    font
      .load()
      .then((loaded) => {
        document.fonts.add(loaded);
        continueRender(handle);
      })
      .catch(() => {
        // Thiếu font thì vẫn render bằng sans-serif, không làm hỏng cả lượt chạy.
        continueRender(handle);
      });
  }, [handle]);
};

export const ShortVideo: React.FC<ShortProps> = ({
  title,
  audioPath,
  imagePath,
  hookText,
  captions,
  audioDurationSeconds,
}) => {
  useBeVietnamPro();

  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const seconds = frame / fps;

  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.08], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const inCta = seconds >= audioDurationSeconds;
  const activeCaption = captions.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={staticFile(imagePath)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${zoom})`,
          }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.15) 30%, rgba(0,0,0,0.25) 60%, rgba(0,0,0,0.9) 100%)",
        }}
      />

      {!inCta && seconds < HOOK_SECONDS ? (
        <div
          style={{
            position: "absolute",
            top: 160,
            left: 60,
            right: 60,
            textAlign: "center",
            color: "#FFD84D",
            fontFamily: FONT_FAMILY,
            fontSize: 84,
            lineHeight: 1.15,
            textShadow: "0 6px 18px rgba(0,0,0,0.85)",
          }}
        >
          {hookText}
        </div>
      ) : null}

      {!inCta && activeCaption ? (
        <div
          style={{
            position: "absolute",
            bottom: 320,
            left: 60,
            right: 60,
            textAlign: "center",
            color: "#fff",
            fontFamily: FONT_FAMILY,
            fontSize: 62,
            lineHeight: 1.25,
            padding: "24px 28px",
            backgroundColor: "rgba(0,0,0,0.55)",
            borderRadius: 24,
          }}
        >
          {activeCaption.text}
        </div>
      ) : null}

      {inCta ? (
        <AbsoluteFill
          style={{
            backgroundColor: "rgba(0,0,0,0.88)",
            justifyContent: "center",
            alignItems: "center",
            padding: 80,
            gap: 48,
          }}
        >
          <div
            style={{
              color: "#fff",
              fontFamily: FONT_FAMILY,
              fontSize: 72,
              lineHeight: 1.2,
              textAlign: "center",
            }}
          >
            {title}
          </div>
          <div
            style={{
              color: "#FFD84D",
              fontFamily: FONT_FAMILY,
              fontSize: 64,
              textAlign: "center",
            }}
          >
            Nghe full trên kênh
          </div>
        </AbsoluteFill>
      ) : null}

      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Đăng ký composition trong `remotion/src/Root.tsx`**

Thay toàn bộ nội dung file bằng:

```tsx
import React from "react";
import { Composition } from "remotion";
import type { AnyZodObject } from "remotion";
import { MainVideo } from "./MainVideo";
import { ShortVideo } from "./ShortVideo";
import type { ShortProps, VideoProps } from "./types";

// Composition's generic constraint requires an indexable Props type; VideoProps
// itself has no index signature, so widen it just for the generic argument.
type CompositionVideoProps = VideoProps & Record<string, unknown>;
type CompositionShortProps = ShortProps & Record<string, unknown>;

const FPS = 30;
const WIDTH = 1024;
const HEIGHT = 576;

const SHORT_WIDTH = 1080;
const SHORT_HEIGHT = 1920;

const calculateMetadata = async ({ props }: { props: VideoProps }) => {
  const lastChapter = props.chapters[props.chapters.length - 1];
  const durationInSeconds = lastChapter ? lastChapter.endSeconds : 0;
  return {
    durationInFrames: Math.max(1, Math.round(durationInSeconds * FPS)),
  };
};

const calculateShortMetadata = async ({ props }: { props: ShortProps }) => {
  const durationInSeconds = props.audioDurationSeconds + props.ctaSeconds;
  return {
    durationInFrames: Math.max(1, Math.round(durationInSeconds * FPS)),
  };
};

const defaultProps: CompositionVideoProps = {
  trope: "",
  title: "",
  audioPath: "",
  sampleRate: 24000,
  chapters: [],
};

const defaultShortProps: CompositionShortProps = {
  trope: "",
  title: "",
  audioPath: "",
  imagePath: "",
  hookText: "",
  captions: [],
  audioDurationSeconds: 0,
  ctaSeconds: 4,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition<AnyZodObject, CompositionVideoProps>
        id="MainVideo"
        component={MainVideo}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        durationInFrames={1}
        calculateMetadata={calculateMetadata}
        defaultProps={defaultProps}
      />
      <Composition<AnyZodObject, CompositionShortProps>
        id="ShortVideo"
        component={ShortVideo}
        fps={FPS}
        width={SHORT_WIDTH}
        height={SHORT_HEIGHT}
        durationInFrames={1}
        calculateMetadata={calculateShortMetadata}
        defaultProps={defaultShortProps}
      />
    </>
  );
};
```

- [ ] **Step 4: Kiểm tra typecheck**

```bash
cd /Users/lee/Project/Apps/audiobook/remotion && npm run typecheck
```

Expected: không in ra lỗi nào, exit code 0.

- [ ] **Step 5: Kiểm tra composition đã được đăng ký**

```bash
cd /Users/lee/Project/Apps/audiobook/remotion && npx remotion compositions src/index.ts
```

Expected: danh sách có cả `MainVideo` và `ShortVideo` (1080x1920).

- [ ] **Step 6: Commit**

```bash
cd /Users/lee/Project/Apps/audiobook
git add remotion/src/ShortVideo.tsx remotion/src/Root.tsx remotion/src/types.ts
git commit -m "feat(remotion): thêm composition ShortVideo dọc 1080x1920"
```

---

### Task 5: `shorts/cli.py` — nối toàn bộ stage

**Files:**
- Create: `shorts/cli.py`
- Test: `tests/shorts/test_cli.py`

**Interfaces:**
- Consumes: `shorts.excerpt`, `shorts.props_builder`, `shorts.storage`, `tts.synthesizer.synthesize_chapter`, `tts.audio_postprocess.{normalize_loudness, concatenate_chapters}`, `tts.voice_profile.load_voice_profile`
- Produces: CLI `uv run python -m shorts.cli <script_json> <images_metadata_json>`, in ra hai dòng `Đã render short: <path>` và `Metadata short: <path>` — `run_daily.sh` ở Task 6 parse đúng hai chuỗi này.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/shorts/test_cli.py`:

```python
# tests/shorts/test_cli.py
import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from shorts import cli as shorts_cli
from shorts.excerpt import ShortExcerpt


def _excerpt() -> ShortExcerpt:
    return ShortExcerpt(
        chapter_index=2,
        hook_text="CÔ ẤY BIẾT HẾT RỒI",
        excerpt_text="Cô ấy bước vào phòng khách. Trời đổ mưa rất to.",
        short_title="Tiêu đề short",
        short_description="Nghe full trên kênh. #shorts",
    )


class _FakeModel:
    """Trả về 0.5 giây âm thanh cho mỗi câu, đủ để tính mốc thời gian."""

    def infer(self, **kwargs):
        return np.zeros(12000, dtype=np.float32)


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch):
    repo_root = tmp_path
    (repo_root / "config").mkdir()
    (repo_root / "config" / "voice.yaml").write_text(
        "voice: 'Thục Đoan'\nstyle: 'normal'\ntarget_lufs: -16.0\n"
        "sample_rate: 24000\ngap_seconds: 0.5\n",
        encoding="utf-8",
    )

    scripts_dir = repo_root / "output" / "scripts"
    scripts_dir.mkdir(parents=True)
    script_path = scripts_dir / "trong_sinh_bao_thu-20260822T000000Z.json"
    script_path.write_text(
        json.dumps(
            {
                "trope": "trong_sinh_bao_thu",
                "title": "Trọng Sinh Báo Thù",
                "chapters": [
                    {"index": 1, "heading": "Chương 1", "text": "..."},
                    {"index": 2, "heading": "Chương 2", "text": "..."},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    images_dir = repo_root / "output" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "anh-2.png").write_bytes(b"x")
    images_path = images_dir / "trong_sinh_bao_thu-20260822T000500Z.json"
    images_path.write_text(
        json.dumps(
            {
                "trope": "trong_sinh_bao_thu",
                "title": "Trọng Sinh Báo Thù",
                "chapters": [
                    {"index": 1, "filename": "anh-1.png", "scene_description": "..."},
                    {"index": 2, "filename": "anh-2.png", "scene_description": "..."},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_dir = repo_root / "output" / "shorts"

    monkeypatch.setattr(shorts_cli, "REPO_ROOT", repo_root)
    monkeypatch.setattr(shorts_cli, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(shorts_cli, "VOICE_CONFIG_PATH", repo_root / "config" / "voice.yaml")
    monkeypatch.setattr(
        shorts_cli.excerpt_module, "generate_short_excerpt", AsyncMock(return_value=_excerpt())
    )

    return script_path, images_path, output_dir


def _fake_render_ok():
    def _run(cmd, **kwargs):
        mp4 = [c for c in cmd if str(c).endswith(".mp4")][0]
        Path(mp4).write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return _run


async def test_chay_tron_ven_sinh_du_bon_file(sandbox, monkeypatch, capsys):
    script_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fake_render_ok())

    await shorts_cli._run(script_path, images_path, model=_FakeModel())

    suffixes = sorted(p.suffix for p in output_dir.iterdir())
    assert suffixes == [".json", ".mp4", ".txt", ".wav"]

    out = capsys.readouterr().out
    assert "Đã render short: " in out
    assert "Metadata short: " in out


async def test_goi_remotion_dung_composition_shortvideo(sandbox, monkeypatch):
    script_path, images_path, output_dir = sandbox
    seen = {}

    def _capture(cmd, **kwargs):
        seen["cmd"] = cmd
        mp4 = [c for c in cmd if str(c).endswith(".mp4")][0]
        Path(mp4).write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)

    await shorts_cli._run(script_path, images_path, model=_FakeModel())

    assert "ShortVideo" in seen["cmd"]
    assert any(str(c).startswith("--public-dir=") for c in seen["cmd"])


async def test_remotion_loi_thi_bao_loi(sandbox, monkeypatch):
    script_path, images_path, _ = sandbox

    def _fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="remotion hỏng")

    monkeypatch.setattr(subprocess, "run", _fail)

    with pytest.raises(shorts_cli.ShortRenderError, match="remotion hỏng"):
        await shorts_cli._run(script_path, images_path, model=_FakeModel())


async def test_remotion_bao_thanh_cong_nhung_khong_co_file(sandbox, monkeypatch):
    script_path, images_path, _ = sandbox

    def _lie(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _lie)

    with pytest.raises(shorts_cli.ShortRenderError, match="không có file"):
        await shorts_cli._run(script_path, images_path, model=_FakeModel())


async def test_moi_cau_duoc_doc_rieng(sandbox, monkeypatch):
    script_path, images_path, output_dir = sandbox
    monkeypatch.setattr(subprocess, "run", _fake_render_ok())

    calls = []

    class _CountingModel(_FakeModel):
        def infer(self, **kwargs):
            calls.append(kwargs.get("text"))
            return super().infer(**kwargs)

    await shorts_cli._run(script_path, images_path, model=_CountingModel())

    # Đoạn trích có đúng 2 câu -> 2 lần gọi TTS, không phải 1 lần cho cả đoạn.
    assert calls == ["Cô ấy bước vào phòng khách.", "Trời đổ mưa rất to."]
```

- [ ] **Step 2: Chạy test để chắc chắn nó fail**

Run: `uv run pytest tests/shorts/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shorts.cli'`

- [ ] **Step 3: Viết `shorts/cli.py`**

```python
# shorts/cli.py
"""Stage 7: dựng video ngắn (Shorts) từ chương gay cấn nhất của tập.

    uv run python -m shorts.cli <script_json> <images_metadata_json>
    # Đã render short: output/shorts/<trope>-<ts>.mp4
    # Metadata short: output/shorts/<trope>-<ts>.txt

Chỉ đọc output của stage 1 và stage 3, nên chạy được cho cả tập đã dựng xong từ trước.
"""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from scripts.models import Chapter, Script
from shorts import excerpt as excerpt_module
from shorts.props_builder import build_short_props
from shorts.storage import (
    make_stem,
    save_short_audio,
    save_short_metadata,
    save_short_props,
    short_video_path,
)
from tts.audio_postprocess import concatenate_chapters, normalize_loudness
from tts.synthesizer import synthesize_chapter
from tts.voice_profile import load_voice_profile

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "shorts"
VOICE_CONFIG_PATH = REPO_ROOT / "config" / "voice.yaml"

# Khoảng nghỉ giữa hai câu. KHÔNG dùng gap_seconds trong voice.yaml — giá trị đó
# (~0.5s) dành cho khoảng nghỉ giữa các chương, áp vào giữa câu nghe rời rạc.
SENTENCE_GAP_SECONDS = 0.15


class ShortRenderError(Exception):
    pass


def _load_model():
    from vieneu import Vieneu

    return Vieneu(backend="onnx")


async def _run(
    script_path: Path,
    images_metadata_path: Path,
    gemini_client=None,
    model=None,
) -> None:
    # Resolve trước khi lấy .parent: build_short_props tính đường dẫn bằng
    # .relative_to(REPO_ROOT), cần cả hai vế đều là đường dẫn tuyệt đối.
    images_metadata_path = images_metadata_path.resolve()

    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    images_metadata = json.loads(images_metadata_path.read_text(encoding="utf-8"))

    excerpt = await excerpt_module.generate_short_excerpt(script, gemini_client)
    sentences = excerpt_module.split_sentences(excerpt.excerpt_text)

    voice_profile = load_voice_profile(VOICE_CONFIG_PATH)
    if model is None:
        model = _load_model()

    # Đọc từng câu một để lấy mốc thời gian thật cho phụ đề. Chapter ở đây chỉ là
    # vỏ bọc cho synthesize_chapter — index/heading chỉ dùng trong thông báo lỗi.
    pieces = []
    for i, sentence in enumerate(sentences, start=1):
        audio = synthesize_chapter(
            Chapter(index=i, heading=f"Câu {i}", text=sentence), model, voice_profile
        )
        pieces.append(
            (
                i,
                sentence,
                normalize_loudness(
                    audio, voice_profile.sample_rate, voice_profile.target_lufs
                ),
            )
        )

    full_audio, timings = concatenate_chapters(
        pieces,
        sample_rate=voice_profile.sample_rate,
        gap_seconds=SENTENCE_GAP_SECONDS,
    )

    stem = make_stem(script.trope)
    audio_path = save_short_audio(stem, full_audio, voice_profile.sample_rate, OUTPUT_DIR)

    props = build_short_props(
        script=script,
        excerpt=excerpt,
        sentences=sentences,
        timings=timings,
        images_metadata=images_metadata,
        audio_path=audio_path,
        images_dir=images_metadata_path.parent,
        repo_root=REPO_ROOT,
    )
    props_path = save_short_props(stem, props, OUTPUT_DIR)

    output_path = short_video_path(stem, OUTPUT_DIR)
    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        "ShortVideo",
        str(output_path),
        f"--props={props_path}",
        f"--public-dir={REPO_ROOT}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REMOTION_DIR)

    if result.returncode != 0:
        raise ShortRenderError(
            f"Lỗi khi render short bằng Remotion: {result.stderr or result.stdout}"
        )
    if not output_path.exists():
        raise ShortRenderError(
            f"Remotion trả về mã thành công nhưng không có file short tại {output_path}"
        )

    metadata_path = save_short_metadata(
        stem, excerpt, script.title, output_path.name, OUTPUT_DIR
    )

    print(f"Đã render short: {output_path}")
    print(f"Metadata short: {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dựng video ngắn (Shorts) từ chương gay cấn nhất của tập."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("images_metadata_path", help="Đường dẫn file JSON metadata ảnh")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path), Path(args.images_metadata_path)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy test để chắc chắn nó pass**

Run: `uv run pytest tests/shorts/ -v`
Expected: PASS — toàn bộ 28 test qua

- [ ] **Step 5: Chạy thật trên một tập đã có sẵn**

```bash
cd /Users/lee/Project/Apps/audiobook
uv run python -m shorts.cli \
  output/scripts/xet_nghiem_adn_tra_manh-20260821T013449Z.json \
  output/images/xet_nghiem_adn_tra_manh-20260821T015406Z.json
```

Nếu hai đường dẫn trên không còn, lấy cặp mới nhất:

```bash
ls -t output/scripts/*.json | head -1; ls -t output/images/*.json | head -1
```

Expected: in ra `Đã render short: ...` và `Metadata short: ...`; file `.mp4` mở lên phải là khung dọc, có hook 3 giây đầu, phụ đề khớp tiếng, và 4 giây cuối là card CTA.

- [ ] **Step 6: Commit**

```bash
git add shorts/cli.py tests/shorts/test_cli.py
git commit -m "feat(shorts): CLI stage 7 dựng video ngắn từ chương gay cấn nhất"
```

---

### Task 6: Ghép stage 7 vào `run_daily.sh`

**Files:**
- Modify: `run_daily.sh` (chèn stage 7 trước nhánh thoát sớm; đổi upload thành stage 8)
- Modify: `tests/fake_stage.sh` (thêm nhánh `shorts.cli`)
- Modify: `tests/test_run_daily.py`
- Modify: `.claude/skills/generating-audiobook-video/SKILL.md`

**Interfaces:**
- Consumes: stdout của `shorts.cli` từ Task 5 — hai chuỗi `Đã render short: <path>.mp4` và `Metadata short: <path>.txt`
- Produces: biến shell `SHORT_PATH`, log riêng `07-short.log`, upload chuyển sang `08-upload.log`

- [ ] **Step 1: Thêm nhánh `shorts.cli` vào `tests/fake_stage.sh`**

Chèn ngay sau khối `metadata.cli)`:

```bash
  shorts.cli)
    echo "Đã render short: output/shorts/me_chong_giau_cua-20260813T015300Z.mp4"
    echo "Metadata short: output/shorts/me_chong_giau_cua-20260813T015300Z.txt"
    ;;
```

- [ ] **Step 2: Cập nhật `tests/test_run_daily.py`**

Thêm hằng số cạnh các hằng số `EXPECTED_*` đang có:

```python
EXPECTED_SHORT = "output/shorts/me_chong_giau_cua-20260813T015300Z.mp4"
```

Thêm `"shorts.cli"` vào danh sách module trong `test_mac_dinh_dung_video_khong_dang_youtube`:

```python
    for module in [
        "trend.cli", "scripts.cli", "tts.cli", "images.cli",
        "video.cli", "thumbnail.cli", "metadata.cli", "shorts.cli",
    ]:
```

Thêm test mới ngay sau `test_stage_6_nhan_video_goc_chu_khong_phai_ten_da_doi`:

```python
def test_stage_7_short_nhan_script_va_images_json(tmp_path: Path):
    # Short chỉ cần output stage 1 và stage 3 — không cần audio hay video.
    run = _run(tmp_path)
    assert run.call_for("shorts.cli") == (
        f"shorts.cli {EXPECTED_SCRIPT} {EXPECTED_IMAGES_JSON}"
    )


def test_short_van_chay_khi_khong_dang_youtube(tmp_path: Path):
    # Nhánh thoát sớm của --no-upload không được nhảy qua stage short.
    run = _run(tmp_path)
    assert run.exit_code == 0
    assert run.called("shorts.cli")
```

Sửa `test_stage_7_upload_ten_video_da_doi_chu_khong_phai_ten_goc` đổi tên thành stage 8:

```python
def test_stage_8_upload_ten_video_da_doi_chu_khong_phai_ten_goc(tmp_path: Path):
```

Trong `test_stage_hong_thi_dung_ngay_va_bao_ngay`, đổi tham số của `upload.cli` từ `"Stage 7"` thành `"Stage 8"`, thêm một dòng cho short, và bổ sung `shorts.cli` vào `order`:

```python
@pytest.mark.parametrize(
    "module,stage_name",
    [
        ("trend.cli", "Stage 0"),
        ("scripts.cli", "Stage 1"),
        ("tts.cli", "Stage 2"),
        ("video.cli", "Stage 4"),
        ("shorts.cli", "Stage 7"),
        ("upload.cli", "Stage 8"),
    ],
)
```

```python
    order = ["trend.cli", "scripts.cli", "tts.cli", "images.cli",
             "video.cli", "thumbnail.cli", "metadata.cli", "shorts.cli", "upload.cli"]
```

Trong `test_moi_stage_ghi_log_rieng_de_lan_lai_khi_hong`, cập nhật danh sách file log:

```python
    assert files == [
        "00-trend.log", "01-script.log", "02-tts.log", "03-images.log",
        "04-video.log", "05-thumbnail.log", "06-metadata.log", "07-short.log",
        "run.log",
    ]
```

- [ ] **Step 3: Chạy test để chắc chắn nó fail**

Run: `uv run pytest tests/test_run_daily.py -v`
Expected: FAIL — `chưa gọi shorts.cli` (run_daily.sh chưa có stage 7)

- [ ] **Step 4: Chèn stage 7 vào `run_daily.sh`**

Chèn khối sau vào **ngay trước** dòng `if [[ "$DO_UPLOAD" -eq 0 ]]; then` (vị trí này quan trọng: đặt sau nhánh đó thì short sẽ không bao giờ chạy ở chế độ mặc định):

```bash
# --- Stage 7: video ngắn ------------------------------------------------------
# Chỉ cần output stage 1 và stage 3, nhưng đặt ở cuối để một lượt chạy hỏng giữa
# chừng không tốn thêm thời gian dựng short cho tập không bao giờ hoàn thành.
SHORT_LOG="$LOG_DIR/07-short.log"
run_stage "Stage 7: Short" "$SHORT_LOG" $RUNNER shorts.cli "$SCRIPT_PATH" "$IMAGES_JSON"
SHORT_PATH="$(extract 'Đã render short: ([^[:space:]]+\.mp4)' "$SHORT_LOG")"
require "$SHORT_PATH" "Stage 7: Short" "$SHORT_LOG"
```

Trong nhánh `if [[ "$DO_UPLOAD" -eq 0 ]]`, thêm một dòng log ngay sau dòng `log "✔ Đã dựng xong..."`:

```bash
  log "  Short: $SHORT_PATH"
```

Đổi khối upload từ stage 7 thành stage 8 — sửa cả tên log, tên stage trong `run_stage` và trong hai lời gọi `require`:

```bash
# --- Stage 8: upload YouTube (chỉ khi có --upload) ---------------------------
UPLOAD_LOG="$LOG_DIR/08-upload.log"
run_stage "Stage 8: Upload YouTube" "$UPLOAD_LOG" \
  $RUNNER upload.cli "$FINAL_VIDEO" "$METADATA_JSON" --thumbnail "$THUMBNAIL_PATH"
VIDEO_URL="$(extract 'Đã upload: ([^[:space:]]+)' "$UPLOAD_LOG")"
require "$VIDEO_URL" "Stage 8: Upload YouTube" "$UPLOAD_LOG"
```

Cập nhật phần chú thích đầu file, thêm dòng mô tả stage short vào block comment:

```bash
#   ./run_daily.sh                              # chủ đề bắt trend (mặc định)
#   ./run_daily.sh --trope trong_sinh_bao_thu   # bỏ qua trend, dùng trope có sẵn
#   ./run_daily.sh --upload                     # dựng xong đăng luôn lên YouTube
#
# Mỗi lượt dựng 1 video dài + 1 thumbnail + 1 video ngắn (Shorts) + metadata SEO.
```

- [ ] **Step 5: Chạy test để chắc chắn nó pass**

Run: `uv run pytest tests/test_run_daily.py -v`
Expected: PASS — toàn bộ test qua, kể cả hai test mới

- [ ] **Step 6: Cập nhật SKILL.md**

Trong `.claude/skills/generating-audiobook-video/SKILL.md`, thêm dòng vào bảng stage ngay sau dòng stage 6:

```markdown
| 7 | `uv run python -m shorts.cli <script_path> <images_metadata_path>` | stage 1 + 3's JSON | `output/shorts/<trope>-<ts>.mp4` (path after "Đã render short:") + `.wav`, `-props.json`, `.txt` |
```

Đổi dòng stage 7 (upload) hiện có thành stage 8, và sửa mọi chỗ nhắc "stage 7 (`upload/`)" thành stage 8 — có ở phần Overview, Prerequisites, mục SEO metadata và Common Mistakes.

Thêm vào mục "Running the daily job": stage 7 chỉ đọc output stage 1 và stage 3 nên chạy lại độc lập được cho tập cũ.

- [ ] **Step 7: Chạy toàn bộ test**

Run: `uv run pytest tests/ -v`
Expected: PASS — không có test nào hỏng

- [ ] **Step 8: Commit**

```bash
git add run_daily.sh tests/fake_stage.sh tests/test_run_daily.py .claude/skills/generating-audiobook-video/SKILL.md
git commit -m "feat(pipeline): chèn stage 7 dựng short, upload chuyển thành stage 8"
```

---

### Task 7: Cập nhật workflow n8n

**Files:**
- Modify: `n8n/audiobook-pipeline.workflow.json`

**Interfaces:**
- Consumes: cùng hai chuỗi stdout như Task 6
- Produces: node `Stage 7: Short` + `Parse Stage 7`, upload đổi tên thành `Stage 8`

Task này độc lập với các task trước — nếu bạn không dùng n8n thì bỏ qua được mà không ảnh hưởng gì đến `run_daily.sh`.

- [ ] **Step 1: Đổi tên hai node upload thành stage 8**

Trong file JSON, đổi:
- `"name": "Stage 7: Upload YouTube"` → `"name": "Stage 8: Upload YouTube"`
- `"name": "Parse Stage 7 (kết quả cuối)"` → `"name": "Parse Stage 8 (kết quả cuối)"`

Đổi luôn mọi tham chiếu tới hai tên này trong khối `"connections"` ở cuối file.

- [ ] **Step 2: Thêm node `Stage 7: Short`**

Thêm vào mảng `"nodes"`, ngay sau node `Parse Stage 6`:

```json
{
  "parameters": {
    "command": "=cd /Users/lee/Project/Apps/audiobook && uv run python -m shorts.cli {{ $json.script_path }} {{ $json.images_json }}"
  },
  "type": "n8n-nodes-base.executeCommand",
  "typeVersion": 1,
  "name": "Stage 7: Short",
  "notes": "Dựng video ngắn từ chương gay cấn nhất. Chỉ cần output stage 1 và stage 3."
}
```

- [ ] **Step 3: Thêm node `Parse Stage 7`**

```json
{
  "parameters": {
    "jsCode": "const stdout = $input.item.json.stdout || '';\nconst mp4 = stdout.match(/Đã render short: (\\S+\\.mp4)/);\nconst txt = stdout.match(/Metadata short: (\\S+\\.txt)/);\nif (!mp4 || !txt) {\n  throw new Error('Không parse được output short:\\n' + stdout + '\\n' + ($input.item.json.stderr || ''));\n}\nreturn [{\n  json: {\n    ...$('Parse Stage 6').item.json,\n    short_path: mp4[1],\n    short_metadata_txt: txt[1],\n  }\n}];"
  },
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "name": "Parse Stage 7"
}
```

- [ ] **Step 4: Nối lại dây trong `connections`**

`Parse Stage 6` phải trỏ sang `Stage 7: Short` thay vì thẳng tới upload; `Stage 7: Short` → `Parse Stage 7` → `Stage 8: Upload YouTube`. Trong khối `"connections"`, sửa mục `"Parse Stage 6"` và thêm hai mục mới:

```json
"Parse Stage 6": {
  "main": [[{ "node": "Stage 7: Short", "type": "main", "index": 0 }]]
},
"Stage 7: Short": {
  "main": [[{ "node": "Parse Stage 7", "type": "main", "index": 0 }]]
},
"Parse Stage 7": {
  "main": [[{ "node": "Stage 8: Upload YouTube", "type": "main", "index": 0 }]]
},
```

- [ ] **Step 5: Kiểm tra JSON còn hợp lệ**

```bash
cd /Users/lee/Project/Apps/audiobook
uv run python -c "import json; d=json.load(open('n8n/audiobook-pipeline.workflow.json')); print(len(d['nodes']), 'node'); print([n['name'] for n in d['nodes']])"
```

Expected: in ra danh sách node có cả `Stage 7: Short` và `Parse Stage 7`, upload mang tên `Stage 8: Upload YouTube`.

- [ ] **Step 6: Commit**

```bash
git add n8n/audiobook-pipeline.workflow.json
git commit -m "feat(n8n): thêm node stage 7 dựng short vào workflow"
```
