# Nhiều cảnh mỗi chương + chuyển động Ken Burns — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Video dài đổi cảnh mỗi ~50 giây thay vì mỗi ~3,5 phút, và mỗi cảnh có pan/zoom nhìn thấy được, không tốn thêm dịch vụ trả phí nào.

**Architecture:** Stage 3 nhận thêm metadata TTS, chia mỗi chương thành các cảnh ~50s tại ranh giới câu (`images/scene_planner.py`, thuần tính toán), tả và vẽ một ảnh cho mỗi cảnh. Metadata ảnh đổi từ một `filename` mỗi chương sang mảng `scenes` có mốc thời gian. Stage 4 dựng mỗi cảnh thành một lớp `SceneBackground` có pan + zoom + crossfade, thêm vignette tĩnh. Stage 7 (short) chọn cảnh đang chiếu tại thời điểm phần bắt đầu.

**Tech Stack:** Python 3.14 + pytest (asyncio mode auto), mflux (FLUX.2-klein, chạy tại máy), gemini-webapi, Remotion 4.0.495 (TypeScript), bash + BSD sed trong `run_daily.sh`.

## Bối cảnh đã đo (tập `chong_hien_mau_con`, 04/09)

- 16 chương, **mỗi ảnh đứng yên trung bình 202 giây** (183–245). Chuyển động duy nhất: scale 1,0→1,15 trải đều cả chương = 0,07%/giây, mắt không thấy.
- mflux: **44 giây/ảnh** (gồm nạp lại model mỗi lần). Gemini tả cảnh: 3–4 giây. Với ~64 cảnh, stage 3 sẽ mất **~50 phút** thay vì 11 — người dùng đã chấp nhận.
- Prompt tả cảnh đã sửa ở `d136b47`: một địa điểm, cảnh trống, ≤30 từ. Việc chia cảnh ngắn càng hợp với quy tắc "một địa điểm".

## Global Constraints

- Mọi thông báo, docstring, bình luận bằng tiếng Việt, đúng giọng văn các module hiện có.
- **Không viết nhánh dự phòng** cho metadata ảnh định dạng cũ. Tập cũ không có `scenes` thì báo lỗi nêu rõ "chạy lại stage 3" — cùng cách đã làm với `sentences` của stage 2.
- Hai dòng stdout contract của `images.cli` giữ nguyên chữ: `Đã lưu <N> ảnh vào <dir>` và `Metadata: <path>`. `run_daily.sh` và n8n parse dòng `Metadata:`.
- `run_daily.sh` dùng BSD `sed -E` — chỉ POSIX ERE, không `\S`, không `\d`.
- Test không được gọi Gemini, mflux hay Remotion thật. Kiểm tra Remotion bằng `npm run typecheck` trong `remotion/`.
- Không đụng `tts/`, `metadata/`, `thumbnails/`, `upload/`, `scripts/`, `shorts/planner.py`, `remotion/src/ShortVideo.tsx`, `remotion/src/ShortThumbnail.tsx`.
- Ảnh cảnh đặt tên `<trope>-<ts>-chapter-<c>-scene-<n>.png`, `n` 1-based trong chương.
- Kiểm chứng mỗi task: `uv run pytest tests/ -q` xanh sạch; task có TypeScript thêm `cd remotion && npm run typecheck`.

## Cấu trúc file

| File | Trách nhiệm |
|---|---|
| `images/scene_planner.py` (mới) | Chia chương thành cảnh theo mốc câu. Thuần. |
| `images/scene_prompt.py` | Tả cảnh bằng Gemini — nhận `(chapter_index, scene_number, text)` thay vì `Chapter`. |
| `images/storage.py` | Ghi ảnh + metadata theo cấu trúc `chapters[].scenes[]`. |
| `images/cli.py` | Stage 3: nhận script + TTS JSON, lặp qua cảnh, in tiến độ. |
| `video/props_builder.py` | Props chương có `scenes[]` với `imagePath` + mốc. |
| `remotion/src/types.ts` | `SceneProps`; `ChapterProps.scenes`. |
| `remotion/src/SceneBackground.tsx` (mới, thay `ChapterBackground.tsx`) | Một lớp ảnh: pan + zoom + crossfade. |
| `remotion/src/MainVideo.tsx` | Trải cảnh thành lớp, thêm vignette. |
| `shorts/props_builder.py` | Chọn cảnh theo thời điểm phần bắt đầu. |
| `run_daily.sh`, `tests/fake_stage.sh`, `tests/test_run_daily.py`, `n8n/audiobook-pipeline.workflow.json` | Stage 3 nhận thêm `$AUDIO_JSON`. |
| `.claude/skills/generating-audiobook-video/SKILL.md`, `docs/DAILY_AUTOMATION.md`, `config/voice.yaml` | Tài liệu và chú thích. |

---

### Task 1: `images/scene_planner.py` — chia chương thành cảnh

**Files:**
- Create: `images/scene_planner.py`
- Test: `tests/images/test_scene_planner.py`

**Interfaces:**
- Consumes: metadata TTS của stage 2 — `{"chapters": [{"index", "start_seconds", "end_seconds"}], "sentences": [{"chapter_index", "index", "text", "start_seconds", "end_seconds"}]}`.
- Produces:
  ```python
  TARGET_SCENE_SECONDS = 50.0
  class ScenePlanError(Exception)
  @dataclass(frozen=True)
  class ScenePlan:
      chapter_index: int
      number: int            # 1-based trong chương
      start_seconds: float   # trục thời gian toàn tập
      end_seconds: float
      text: str              # các câu trong cảnh ghép bằng khoảng trắng
  def plan_scenes(tts_metadata: dict, target_seconds: float = TARGET_SCENE_SECONDS) -> list[ScenePlan]
  ```
  Bất biến mà Task 3, 5, 7 dựa vào: các cảnh của một chương **phủ kín** chương — cảnh 1 bắt đầu đúng `start_seconds` của chương, cảnh cuối kết thúc đúng `end_seconds`, cảnh k+1 bắt đầu đúng lúc cảnh k kết thúc. Thứ tự trả về: theo chương rồi theo `number`.

- [ ] **Step 1: Viết test đỏ**

```python
# tests/images/test_scene_planner.py
import pytest

from images.scene_planner import ScenePlan, ScenePlanError, plan_scenes


def _sentence(chapter_index, index, start, end, text=None):
    return {
        "chapter_index": chapter_index,
        "index": index,
        "text": text or f"Câu {chapter_index}.{index}.",
        "start_seconds": start,
        "end_seconds": end,
    }


def _metadata(chapters, sentences):
    return {"trope": "t", "title": "T", "sample_rate": 24000,
            "chapters": chapters, "sentences": sentences}


def test_chuong_200s_chia_thanh_4_canh_phu_kin_chuong():
    # 20 câu, mỗi câu 10s (có 0.15s nghỉ giữa câu như thật) -> mục tiêu 50s -> 4 cảnh.
    sentences = [_sentence(1, i + 1, i * 10.0, i * 10.0 + 9.85) for i in range(20)]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 200.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert [s.number for s in scenes] == [1, 2, 3, 4]
    assert scenes[0].start_seconds == 0.0
    assert scenes[-1].end_seconds == 200.0
    for prev, nxt in zip(scenes, scenes[1:]):
        assert nxt.start_seconds == prev.end_seconds  # không hở, không chồng
    # Mỗi cảnh xấp xỉ 50s: cắt tại ranh giới câu nên lệch tối đa một câu.
    for s in scenes:
        assert 40.0 <= s.end_seconds - s.start_seconds <= 60.0


def test_cat_dung_ranh_gioi_cau_va_ghep_text():
    sentences = [
        _sentence(1, 1, 0.0, 30.0, "Một."),
        _sentence(1, 2, 30.0, 60.0, "Hai."),
        _sentence(1, 3, 60.0, 90.0, "Ba."),
        _sentence(1, 4, 90.0, 120.0, "Bốn."),
    ]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 120.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=60.0)

    assert len(scenes) == 2
    assert scenes[0].text == "Một. Hai."
    assert scenes[1].text == "Ba. Bốn."
    assert scenes[1].start_seconds == 60.0


def test_chuong_ngan_hon_muc_tieu_thanh_mot_canh():
    sentences = [_sentence(1, 1, 0.0, 10.0), _sentence(1, 2, 10.0, 30.0)]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 30.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert scenes == [ScenePlan(1, 1, 0.0, 30.0, "Câu 1.1. Câu 1.2.")]


def test_it_cau_hon_so_canh_mong_muon_thi_moi_canh_mot_cau():
    # 3 câu rất dài trong chương 200s: muốn 4 cảnh nhưng chỉ có 3 câu.
    sentences = [_sentence(1, 1, 0.0, 70.0), _sentence(1, 2, 70.0, 140.0), _sentence(1, 3, 140.0, 200.0)]
    meta = _metadata([{"index": 1, "start_seconds": 0.0, "end_seconds": 200.0}], sentences)

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert [s.number for s in scenes] == [1, 2, 3]
    assert [s.start_seconds for s in scenes] == [0.0, 70.0, 140.0]


def test_nhieu_chuong_giu_thu_tu_va_danh_so_lai_tu_1():
    sentences = [
        _sentence(1, 1, 0.0, 50.0), _sentence(1, 2, 50.0, 100.0),
        _sentence(2, 1, 100.5, 150.0), _sentence(2, 2, 150.0, 200.5),
    ]
    meta = _metadata(
        [{"index": 1, "start_seconds": 0.0, "end_seconds": 100.0},
         {"index": 2, "start_seconds": 100.5, "end_seconds": 200.5}],
        sentences,
    )

    scenes = plan_scenes(meta, target_seconds=50.0)

    assert [(s.chapter_index, s.number) for s in scenes] == [(1, 1), (1, 2), (2, 1), (2, 2)]
    assert scenes[2].start_seconds == 100.5  # cảnh đầu chương 2 bám start của chương, không phải end chương 1


def test_thieu_mang_sentences_thi_bao_chay_lai_stage_2():
    meta = {"trope": "t", "title": "T", "sample_rate": 24000,
            "chapters": [{"index": 1, "start_seconds": 0.0, "end_seconds": 10.0}]}

    with pytest.raises(ScenePlanError, match="chạy lại stage 2"):
        plan_scenes(meta)


def test_chuong_khong_co_cau_nao_thi_bao_ro_chuong():
    meta = _metadata(
        [{"index": 1, "start_seconds": 0.0, "end_seconds": 10.0},
         {"index": 2, "start_seconds": 10.0, "end_seconds": 20.0}],
        [_sentence(1, 1, 0.0, 10.0)],
    )

    with pytest.raises(ScenePlanError, match="Chương 2"):
        plan_scenes(meta)
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/images/test_scene_planner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'images.scene_planner'`

- [ ] **Step 3: Viết `images/scene_planner.py`**

```python
# images/scene_planner.py
"""Chia mỗi chương thành các cảnh ~50 giây theo mốc câu của stage 2.

Một ảnh gánh cả chương 3-4 phút là lý do video nhìn "đứng": đo tập 04/09, mỗi
ảnh đứng yên trung bình 202 giây. Cắt tại ranh giới câu để cảnh không đổi giữa
chừng một câu. Thuần tính toán -- không gọi Gemini hay mflux, nên test chạy
không cần cookie hay model.
"""

from dataclasses import dataclass

# Mục tiêu độ dài một cảnh. 50s là khoảng mắt còn thấy "mới đổi cảnh" mà stage 3
# chưa quá chậm: 16 chương ~200s -> ~64 ảnh -> ~50 phút với 44s/ảnh.
TARGET_SCENE_SECONDS = 50.0


class ScenePlanError(Exception):
    pass


@dataclass(frozen=True)
class ScenePlan:
    chapter_index: int
    number: int  # 1-based trong chương
    # Trục thời gian toàn tập. Các cảnh của một chương phủ kín chương: cảnh 1 bắt
    # đầu đúng start của chương, cảnh cuối kết thúc đúng end, cảnh sau bắt đầu
    # đúng lúc cảnh trước kết thúc. Stage 4 và 7 dựa vào bất biến này.
    start_seconds: float
    end_seconds: float
    text: str  # các câu trong cảnh ghép lại, để Gemini tả bối cảnh


def plan_scenes(
    tts_metadata: dict, target_seconds: float = TARGET_SCENE_SECONDS
) -> list[ScenePlan]:
    sentences = tts_metadata.get("sentences")
    if not sentences:
        raise ScenePlanError(
            "Metadata TTS không có mốc câu (mảng 'sentences' thiếu hoặc rỗng). "
            "Tập này dựng trước khi stage 2 biết ghi mốc câu -- muốn chia cảnh, "
            "hãy chạy lại stage 2."
        )

    by_chapter: dict[int, list[dict]] = {}
    for sentence in sentences:
        by_chapter.setdefault(sentence["chapter_index"], []).append(sentence)

    plans: list[ScenePlan] = []
    for chapter in tts_metadata["chapters"]:
        index = chapter["index"]
        chapter_sentences = by_chapter.get(index)
        if not chapter_sentences:
            raise ScenePlanError(
                f"Chương {index} không có câu nào trong metadata TTS."
            )
        plans.extend(
            _split_chapter(
                index,
                chapter["start_seconds"],
                chapter["end_seconds"],
                chapter_sentences,
                target_seconds,
            )
        )
    return plans


def _split_chapter(
    index: int,
    chapter_start: float,
    chapter_end: float,
    sentences: list[dict],
    target_seconds: float,
) -> list[ScenePlan]:
    duration = chapter_end - chapter_start
    wanted = max(1, round(duration / target_seconds))
    wanted = min(wanted, len(sentences))  # mỗi cảnh ít nhất một câu

    # Duyệt một lượt, đóng cảnh khi câu vừa thêm chạm mốc chia đều kế tiếp.
    # Hai ràng buộc: không đóng cảnh cuối (nó ôm phần còn lại), và phải đóng
    # ngay khi số câu còn lại chỉ vừa đủ cho số cảnh còn lại.
    groups: list[list[dict]] = []
    current: list[dict] = []
    for position, sentence in enumerate(sentences):
        current.append(sentence)
        scenes_left = wanted - len(groups)  # kể cả cảnh đang mở
        sentences_left = len(sentences) - position - 1
        ideal_end = chapter_start + duration * (len(groups) + 1) / wanted
        must_close = sentences_left == scenes_left - 1
        if scenes_left > 1 and (sentence["end_seconds"] >= ideal_end or must_close):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    plans = []
    for number, group in enumerate(groups, start=1):
        is_first = number == 1
        is_last = number == len(groups)
        start = chapter_start if is_first else group[0]["start_seconds"]
        end = chapter_end if is_last else groups[number][0]["start_seconds"]
        plans.append(
            ScenePlan(
                chapter_index=index,
                number=number,
                start_seconds=start,
                end_seconds=end,
                text=" ".join(s["text"] for s in group),
            )
        )
    return plans
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `uv run pytest tests/images/test_scene_planner.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add images/scene_planner.py tests/images/test_scene_planner.py
git commit -m "feat(images): chia chương thành cảnh ~50s theo mốc câu"
```

---

### Task 2: `images/scene_prompt.py` — tả cảnh theo đoạn, không theo chương

**Files:**
- Modify: `images/scene_prompt.py` (hàm `generate_scene_description`)
- Test: `tests/images/test_scene_prompt.py`

**Interfaces:**
- Produces:
  ```python
  async def generate_scene_description(
      chapter_index: int, scene_number: int, text: str,
      client: "GeminiClient | None" = None,
  ) -> str
  ```
  Thông báo lỗi nêu `chương {chapter_index} cảnh {scene_number}`. `build_scene_prompt_request(text)` giữ nguyên.

- [ ] **Step 1: Sửa test sang chữ ký mới**

Trong `tests/images/test_scene_prompt.py`, thay ba test đang có bằng:

```python
async def test_generate_scene_description_returns_cleaned_text():
    fake_client = _make_fake_client('"cozy living room at dusk"')

    description = await generate_scene_description(
        1, 1, "Nội dung cảnh một.", client=fake_client
    )

    assert description == "cozy living room at dusk"
    fake_client.generate_content.assert_called_once()
    request = fake_client.generate_content.call_args.args[0]
    assert "Nội dung cảnh một." in request


async def test_generate_scene_description_raises_on_empty_response():
    fake_client = _make_fake_client("   ")

    with pytest.raises(ScenePromptError, match="chương 2 cảnh 3"):
        await generate_scene_description(2, 3, "Nội dung.", client=fake_client)


async def test_generate_scene_description_wraps_api_error():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("boom"))

    with pytest.raises(ScenePromptError, match="chương 3 cảnh 1"):
        await generate_scene_description(3, 1, "Nội dung.", client=fake_client)
```

Bỏ `from scripts.models import Chapter` nếu không còn dùng. Giữ `test_build_scene_prompt_request_ep_mot_dia_diem_va_canh_trong`.

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/images/test_scene_prompt.py -q`
Expected: FAIL — `TypeError` vì hàm vẫn nhận `Chapter`.

- [ ] **Step 3: Sửa `generate_scene_description`**

Thay toàn bộ hàm (giữ `build_scene_prompt_request` nguyên):

```python
async def generate_scene_description(
    chapter_index: int,
    scene_number: int,
    text: str,
    client: "GeminiClient | None" = None,
) -> str:
    # Nhận đoạn văn của MỘT cảnh chứ không phải cả chương: chương 3-4 phút có
    # nhiều bối cảnh, còn một cảnh ~50s thường chỉ có một -- hợp với quy tắc
    # "đúng một địa điểm" trong prompt.
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    where = f"chương {chapter_index} cảnh {scene_number}"
    try:
        response = await client.generate_content(build_scene_prompt_request(text))
    except (GeminiError, APIError, AuthError) as exc:
        raise ScenePromptError(f"Gemini lỗi khi tạo mô tả cảnh cho {where}: {exc}") from exc

    description = response.text.strip().strip('"').strip()
    if not description:
        raise ScenePromptError(f"Gemini trả về mô tả cảnh rỗng cho {where}")

    return description
```

Xoá `from scripts.models import Chapter` ở đầu file.

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `uv run pytest tests/images/test_scene_prompt.py -q`
Expected: `4 passed`. (`tests/images/test_cli.py` sẽ đỏ tạm — Task 4 sửa.)

- [ ] **Step 5: Commit**

```bash
git add images/scene_prompt.py tests/images/test_scene_prompt.py
git commit -m "refactor(images): tả cảnh theo đoạn văn của cảnh, không theo cả chương"
```

---

### Task 3: `images/storage.py` — metadata `chapters[].scenes[]`

**Files:**
- Modify: `images/storage.py`
- Test: `tests/images/test_storage.py`

**Interfaces:**
- Consumes: `ScenePlan` (Task 1).
- Produces:
  ```python
  def save_scene_images(
      trope: str, title: str,
      images: list[tuple[ScenePlan, str, bytes]],   # (cảnh, mô tả, png)
      output_dir: Path,
  ) -> tuple[list[Path], Path]
  ```
  Metadata ghi ra — Task 5 và 7 đọc đúng khoá này:
  ```json
  {
    "trope": "...", "title": "...",
    "chapters": [
      {"index": 1, "scenes": [
        {"number": 1, "start_seconds": 0.0, "end_seconds": 48.3,
         "filename": "<trope>-<ts>-chapter-1-scene-1.png",
         "scene_description": "..."}
      ]}
    ]
  }
  ```
  `save_chapter_images` bị xoá — không giữ hai đường ghi.

- [ ] **Step 1: Viết lại test**

Thay toàn bộ `tests/images/test_storage.py`:

```python
import json

from images.scene_planner import ScenePlan
from images.storage import save_scene_images


def _scene(chapter, number, start, end):
    return ScenePlan(chapter, number, start, end, f"text {chapter}.{number}")


def test_save_scene_images_ghi_png_va_metadata_theo_chuong_va_canh(tmp_path):
    images = [
        (_scene(1, 1, 0.0, 50.0), "cozy living room at dusk", b"png 1.1"),
        (_scene(1, 2, 50.0, 100.0), "empty kitchen at night", b"png 1.2"),
        (_scene(2, 1, 100.0, 140.0), "misty valley at dawn", b"png 2.1"),
    ]

    image_paths, metadata_path = save_scene_images(
        trope="test_trope", title="Tiêu đề", images=images, output_dir=tmp_path
    )

    assert [p.name.split("-", 2)[2] for p in image_paths] == [
        "chapter-1-scene-1.png", "chapter-1-scene-2.png", "chapter-2-scene-1.png",
    ]
    assert image_paths[1].read_bytes() == b"png 1.2"

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["trope"] == "test_trope"
    assert data["title"] == "Tiêu đề"
    assert [c["index"] for c in data["chapters"]] == [1, 2]
    assert data["chapters"][0]["scenes"] == [
        {"number": 1, "start_seconds": 0.0, "end_seconds": 50.0,
         "filename": image_paths[0].name, "scene_description": "cozy living room at dusk"},
        {"number": 2, "start_seconds": 50.0, "end_seconds": 100.0,
         "filename": image_paths[1].name, "scene_description": "empty kitchen at night"},
    ]
    assert data["chapters"][1]["scenes"][0]["filename"] == image_paths[2].name


def test_save_scene_images_tao_thu_muc_neu_chua_co(tmp_path):
    missing_dir = tmp_path / "nested" / "output"

    image_paths, _ = save_scene_images(
        trope="t", title="T",
        images=[(_scene(1, 1, 0.0, 10.0), "a scene", b"bytes")],
        output_dir=missing_dir,
    )

    assert image_paths[0].exists()
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/images/test_storage.py -q`
Expected: FAIL — `ImportError: cannot import name 'save_scene_images'`

- [ ] **Step 3: Viết lại `images/storage.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from images.scene_planner import ScenePlan


def save_scene_images(
    trope: str,
    title: str,
    images: list[tuple[ScenePlan, str, bytes]],
    output_dir: Path,
) -> tuple[list[Path], Path]:
    """Ghi mỗi cảnh một PNG và một metadata JSON gom cảnh theo chương.

    Mốc start/end của cảnh đi kèm trong metadata để stage 4 biết chiếu ảnh nào
    lúc nào và stage 7 biết phần short bắt đầu ở cảnh nào -- không ai phải
    tính lại từ mốc câu.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    image_paths: list[Path] = []
    chapters: dict[int, list[dict]] = {}
    for scene, scene_description, image_bytes in images:
        image_path = (
            output_dir
            / f"{trope}-{timestamp}-chapter-{scene.chapter_index}-scene-{scene.number}.png"
        )
        image_path.write_bytes(image_bytes)
        image_paths.append(image_path)
        chapters.setdefault(scene.chapter_index, []).append(
            {
                "number": scene.number,
                "start_seconds": scene.start_seconds,
                "end_seconds": scene.end_seconds,
                "filename": image_path.name,
                "scene_description": scene_description,
            }
        )

    metadata_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {
        "trope": trope,
        "title": title,
        "chapters": [
            {"index": index, "scenes": scenes} for index, scenes in chapters.items()
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return image_paths, metadata_path
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `uv run pytest tests/images/test_storage.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add images/storage.py tests/images/test_storage.py
git commit -m "feat(images): metadata ảnh gom cảnh theo chương, kèm mốc thời gian"
```

---

### Task 4: `images/cli.py` — stage 3 nhận script + TTS JSON

**Files:**
- Modify: `images/cli.py`
- Test: `tests/images/test_cli.py`

**Interfaces:**
- Consumes: `plan_scenes` (Task 1), `generate_scene_description(chapter_index, scene_number, text, client)` (Task 2), `save_scene_images` (Task 3), `generate_background_image(description)` (không đổi).
- Produces: lệnh `uv run python -m images.cli <script_path> <tts_metadata_path>`. Stdout: mỗi cảnh một dòng tiến độ `Cảnh <i>/<N>: chương <c> cảnh <n> (<mm:ss>–<mm:ss>)`, cuối cùng hai dòng contract `Đã lưu <N> ảnh vào <dir>` và `Metadata: <path>`. `_run(script_path, tts_metadata_path, gemini_client=None)`.

- [ ] **Step 1: Viết lại test**

Thay toàn bộ `tests/images/test_cli.py`:

```python
import json
from pathlib import Path

import pytest

from images import cli
from scripts.models import Chapter, Script


def _write_inputs(tmp_path):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Một. Hai."),
            Chapter(index=2, heading="Chương 2", text="Ba."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    tts_metadata = {
        "trope": "demo", "title": "Tiêu đề demo", "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": 100.0},
            {"index": 2, "heading": "Chương 2", "start_seconds": 100.5, "end_seconds": 130.5},
        ],
        "sentences": [
            {"chapter_index": 1, "index": 1, "text": "Một.", "start_seconds": 0.0, "end_seconds": 50.0},
            {"chapter_index": 1, "index": 2, "text": "Hai.", "start_seconds": 50.0, "end_seconds": 100.0},
            {"chapter_index": 2, "index": 1, "text": "Ba.", "start_seconds": 100.5, "end_seconds": 130.5},
        ],
    }
    tts_path = tmp_path / "audio.json"
    tts_path.write_text(json.dumps(tts_metadata, ensure_ascii=False), encoding="utf-8")
    return script_path, tts_path


async def test_run_chia_canh_ta_canh_ve_anh_va_luu(tmp_path, monkeypatch, capsys):
    script_path, tts_path = _write_inputs(tmp_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    fake_gemini_client = object()
    described = []

    async def fake_generate_scene_description(chapter_index, scene_number, text, client):
        assert client is fake_gemini_client
        described.append((chapter_index, scene_number, text))
        return f"scene {chapter_index}.{scene_number}"

    def fake_generate_background_image(scene_description):
        return f"png for {scene_description}".encode("utf-8")

    monkeypatch.setattr(cli, "generate_scene_description", fake_generate_scene_description)
    monkeypatch.setattr(cli, "generate_background_image", fake_generate_background_image)

    await cli._run(script_path, tts_path, gemini_client=fake_gemini_client)

    # Chương 1 dài 100s -> 2 cảnh; chương 2 dài 30s -> 1 cảnh. Mô tả nhận đúng
    # đoạn văn của cảnh, không phải cả chương.
    assert described == [(1, 1, "Một."), (1, 2, "Hai."), (2, 1, "Ba.")]

    saved_images = sorted((tmp_path / "output").glob("*.png"))
    assert [p.name.split("-", 2)[2] for p in saved_images] == [
        "chapter-1-scene-1.png", "chapter-1-scene-2.png", "chapter-2-scene-1.png",
    ]
    data = json.loads(next((tmp_path / "output").glob("*.json")).read_text(encoding="utf-8"))
    assert data["chapters"][0]["scenes"][1]["scene_description"] == "scene 1.2"

    out = capsys.readouterr().out
    assert "Cảnh 1/3: chương 1 cảnh 1 (00:00–00:50)" in out
    assert "Đã lưu 3 ảnh vào" in out
    assert "Metadata: " in out


async def test_run_tu_choi_khi_tts_khong_khop_script(tmp_path, monkeypatch):
    script_path, tts_path = _write_inputs(tmp_path)
    tts = json.loads(tts_path.read_text(encoding="utf-8"))
    tts["title"] = "Tập khác"
    tts_path.write_text(json.dumps(tts, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    with pytest.raises(cli.ImagesInputError, match="trope/title"):
        await cli._run(script_path, tts_path, gemini_client=object())


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    async def fake_run(script_path, tts_metadata_path, gemini_client=None):
        calls.append((script_path, tts_metadata_path))

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json", "some/audio.json"])

    cli.main()

    assert calls == [(Path("some/script.json"), Path("some/audio.json"))]
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/images/test_cli.py -q`
Expected: FAIL — `_run()` nhận sai số tham số / thiếu `ImagesInputError`.

- [ ] **Step 3: Viết lại `images/cli.py`**

Đọc file hiện tại để giữ nguyên `_load_gemini_client`, `OUTPUT_DIR` và các import đang có. Thay phần còn lại:

```python
import argparse
import asyncio
import json
from pathlib import Path

from images.generator import generate_background_image
from images.scene_planner import plan_scenes
from images.scene_prompt import generate_scene_description
from images.storage import save_scene_images
from scripts.models import Script

# ... giữ OUTPUT_DIR và _load_gemini_client như cũ ...


class ImagesInputError(Exception):
    pass


def _mmss(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60:02d}:{whole % 60:02d}"


async def _run(
    script_path: Path, tts_metadata_path: Path, gemini_client=None
) -> None:
    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))

    if tts_metadata["trope"] != script.trope or tts_metadata["title"] != script.title:
        raise ImagesInputError(
            "trope/title của metadata TTS không khớp với script "
            f"(script: {script.trope!r}/{script.title!r}, "
            f"tts: {tts_metadata['trope']!r}/{tts_metadata['title']!r})"
        )

    # Stage 3 nay cần mốc câu của stage 2 để chia cảnh -- nên nhận TTS JSON chứ
    # không chỉ script. Tập dựng trước khi stage 2 ghi mốc câu sẽ bị plan_scenes
    # từ chối với thông báo bảo chạy lại stage 2.
    scenes = plan_scenes(tts_metadata)

    if gemini_client is None:
        gemini_client = await _load_gemini_client()

    images = []
    for position, scene in enumerate(scenes, start=1):
        # In trước khi vẽ: stage này chạy ~50 phút, người theo dõi log cần biết
        # nó đang ở đâu chứ không phải nó có treo không.
        print(
            f"Cảnh {position}/{len(scenes)}: chương {scene.chapter_index} "
            f"cảnh {scene.number} ({_mmss(scene.start_seconds)}–{_mmss(scene.end_seconds)})",
            flush=True,
        )
        description = await generate_scene_description(
            scene.chapter_index, scene.number, scene.text, gemini_client
        )
        image_bytes = generate_background_image(description)
        images.append((scene, description, image_bytes))

    image_paths, metadata_path = save_scene_images(
        script.trope, script.title, images, OUTPUT_DIR
    )

    print(
        f"Đã lưu {len(image_paths)} ảnh vào {OUTPUT_DIR}\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sinh ảnh nền cho từng cảnh ~50s của kịch bản bằng Flux."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản (stage 1)")
    parser.add_argument(
        "tts_metadata_path",
        help="Đường dẫn file JSON metadata TTS (stage 2) -- cần mốc câu để chia cảnh",
    )
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path), Path(args.tts_metadata_path)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy toàn bộ test images, xác nhận xanh**

Run: `uv run pytest tests/images/ -q`
Expected: tất cả pass.

- [ ] **Step 5: Commit**

```bash
git add images/cli.py tests/images/test_cli.py
git commit -m "feat(images): stage 3 nhận TTS JSON, vẽ một ảnh cho mỗi cảnh ~50s"
```

---

### Task 5: `video/props_builder.py` — props chương có `scenes[]`

**Files:**
- Modify: `video/props_builder.py`
- Test: `tests/video/test_props_builder.py`, `tests/video/test_cli.py` (fixture dòng ~56)

**Interfaces:**
- Consumes: metadata ảnh Task 3.
- Produces: mỗi phần tử `chapters[]` trong props **bỏ** `imagePath`, **thêm**:
  ```python
  "scenes": [{"number": 1, "startSeconds": 0.0, "endSeconds": 48.3, "imagePath": "output/images/..png"}]
  ```
  Task 6 (TypeScript) đọc đúng bốn khoá này.

- [ ] **Step 1: Sửa test**

Trong `tests/video/test_props_builder.py`, thêm helper và đổi mọi fixture `images_metadata`:

```python
def _image_chapter(index, *scenes):
    # scenes: (number, start, end, filename)
    return {
        "index": index,
        "scenes": [
            {"number": n, "start_seconds": s, "end_seconds": e,
             "filename": f, "scene_description": "..."}
            for n, s, e, f in scenes
        ],
    }
```

Trong `test_build_video_props_joins_all_sources` đổi `images_metadata` thành:

```python
    images_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "chapters": [
            _image_chapter(1, (1, 0.0, 1.0, "demo-c1-s1.png"), (2, 1.0, 2.0, "demo-c1-s2.png")),
            _image_chapter(2, (1, 2.5, 4.5, "demo-c2-s1.png")),
        ],
    }
```

và khẳng định chương 1 thành:

```python
    assert props["chapters"][0] == {
        "index": 1,
        "heading": "Chuong 1",
        "startSeconds": 0.0,
        "endSeconds": 2.0,
        "scenes": [
            {"number": 1, "startSeconds": 0.0, "endSeconds": 1.0,
             "imagePath": str(Path("output/images/demo-c1-s1.png"))},
            {"number": 2, "startSeconds": 1.0, "endSeconds": 2.0,
             "imagePath": str(Path("output/images/demo-c1-s2.png"))},
        ],
        "sentences": [
            {"text": "Cau mot.", "startSeconds": 0.0, "endSeconds": 1.0},
            {"text": "Cau hai.", "startSeconds": 1.0, "endSeconds": 2.0},
        ],
    }
    assert props["chapters"][1]["scenes"][0]["imagePath"] == str(Path("output/images/demo-c2-s1.png"))
```

Các test còn lại: thay mỗi `{"index": N, "filename": "x.png", "scene_description": "a"}` bằng `_image_chapter(N, (1, <start chương>, <end chương>, "x.png"))`.

Thêm test mới:

```python
def test_build_video_props_raises_on_images_without_scenes():
    script = _make_script()
    tts_metadata = {
        "trope": "demo", "title": "Tieu de demo", "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0},
            {"index": 2, "heading": "Chuong 2", "start_seconds": 2.5, "end_seconds": 4.5},
        ],
        "sentences": [_sentence(1, 1, "Cau mot.", 0.0, 2.0), _sentence(2, 1, "Cau ba.", 2.5, 4.5)],
    }
    # Định dạng cũ: một filename mỗi chương, không có scenes.
    images_metadata = {
        "trope": "demo", "title": "Tieu de demo",
        "chapters": [
            {"index": 1, "filename": "a.png", "scene_description": "a"},
            {"index": 2, "filename": "b.png", "scene_description": "b"},
        ],
    }

    with pytest.raises(PropsBuildError, match="chạy lại stage 3"):
        build_video_props(
            script, tts_metadata, images_metadata,
            audio_path=Path("/repo/a.wav"), images_dir=Path("/repo/images"), repo_root=Path("/repo"),
        )
```

Trong `tests/video/test_cli.py`, dòng ~56 đổi fixture thành `{"index": 1, "scenes": [{"number": 1, "start_seconds": 0.0, "end_seconds": 2.0, "filename": "demo-chapter-1.png", "scene_description": "a"}]}` (đọc fixture để khớp mốc chương đang dùng).

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/video/ -q`
Expected: FAIL — props vẫn có `imagePath` ở chương, thiếu `scenes`.

- [ ] **Step 3: Sửa `build_video_props`**

Thay đoạn dựng `chapters.append({...})`:

```python
    chapters = []
    for chapter in script.chapters:
        tts_chapter = tts_by_index[chapter.index]
        image_chapter = images_by_index[chapter.index]
        chapter_sentences = sentences_by_chapter.get(chapter.index)
        if not chapter_sentences:
            raise PropsBuildError(
                f"Chương {chapter.index} không có câu nào trong metadata TTS — tập này "
                "dựng trước khi stage 2 biết ghi mốc câu. Muốn render lại, hãy chạy lại stage 2."
            )
        image_scenes = image_chapter.get("scenes")
        if not image_scenes:
            raise PropsBuildError(
                f"Metadata ảnh của chương {chapter.index} không có mảng 'scenes' — tập này "
                "dựng trước khi stage 3 biết chia cảnh. Muốn render lại, hãy chạy lại stage 3."
            )
        chapters.append(
            {
                "index": chapter.index,
                "heading": chapter.heading,
                "startSeconds": tts_chapter["start_seconds"],
                "endSeconds": tts_chapter["end_seconds"],
                # Mốc cảnh giữ trục toàn tập, cùng lý do với mốc câu bên dưới.
                "scenes": [
                    {
                        "number": scene["number"],
                        "startSeconds": scene["start_seconds"],
                        "endSeconds": scene["end_seconds"],
                        "imagePath": str(
                            (images_dir / scene["filename"]).relative_to(repo_root)
                        ),
                    }
                    for scene in image_scenes
                ],
                "sentences": [
                    {
                        "text": s["text"],
                        "startSeconds": s["start_seconds"],
                        "endSeconds": s["end_seconds"],
                    }
                    for s in chapter_sentences
                ],
            }
        )
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `uv run pytest tests/video/ -q`
Expected: tất cả pass.

- [ ] **Step 5: Commit**

```bash
git add video/props_builder.py tests/video/
git commit -m "feat(video): props chương mang mảng cảnh có mốc và đường dẫn ảnh"
```

---

### Task 6: Remotion — `SceneBackground` pan/zoom/crossfade + vignette

**Files:**
- Modify: `remotion/src/types.ts`
- Create: `remotion/src/SceneBackground.tsx`
- Delete: `remotion/src/ChapterBackground.tsx`
- Modify: `remotion/src/MainVideo.tsx`

**Interfaces:**
- Consumes: props Task 5 (`chapters[].scenes[]` với `number`, `startSeconds`, `endSeconds`, `imagePath`).
- Produces: composition `MainVideo` render từ props mới. Không đổi `Root.tsx` (defaultProps `chapters: []` vẫn hợp lệ).

Số liệu chuyển động, chọn để **thấy được trong 50s mà không lộ mép đen**: scale 1,06→1,16 (hoặc ngược), pan ngang ±2,5% (ở scale 1,06 còn dư 3% mỗi bên nên không hở), 4 kiểu luân phiên theo thứ tự cảnh toàn tập, crossfade 1,0s.

- [ ] **Step 1: Sửa `types.ts`**

```ts
export interface SceneProps {
  number: number;
  // Trục thời gian toàn tập, giống mốc câu.
  startSeconds: number;
  endSeconds: number;
  imagePath: string;
}

export interface ChapterProps {
  index: number;
  heading: string;
  startSeconds: number;
  endSeconds: number;
  // Mỗi chương nhiều cảnh ~50s, phủ kín chương (stage 3 đảm bảo).
  scenes: SceneProps[];
  // Mốc câu giữ nguyên trục thời gian toàn tập (không quy về gốc chương) --
  // xem Caption.tsx, nơi so trực tiếp với `seconds` toàn cục.
  sentences: { text: string; startSeconds: number; endSeconds: number }[];
}
```

(Giữ nguyên `VideoProps`, `ShortCaption`, `ShortProps`.)

- [ ] **Step 2: Viết `SceneBackground.tsx`**

```tsx
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import type { SceneProps } from "./types";

// Bốn kiểu chuyển động luân phiên theo thứ tự cảnh trên toàn tập, để hai cảnh
// liền nhau không bao giờ lặp cùng một hướng.
const MOTIONS = [
  { scale: [1.06, 1.16], panX: [-2.5, 2.5] },
  { scale: [1.16, 1.06], panX: [2.5, -2.5] },
  { scale: [1.06, 1.16], panX: [2.5, -2.5] },
  { scale: [1.16, 1.06], panX: [-2.5, 2.5] },
] as const;

interface SceneBackgroundProps {
  scene: SceneProps;
  startFrame: number;
  endFrame: number;
  crossfadeFrames: number;
  motionIndex: number; // thứ tự cảnh toàn tập, chọn kiểu trong MOTIONS
}

export const SceneBackground: React.FC<SceneBackgroundProps> = ({
  scene,
  startFrame,
  endFrame,
  crossfadeFrames,
  motionIndex,
}) => {
  const frame = useCurrentFrame();
  const motion = MOTIONS[motionIndex % MOTIONS.length];

  // Hiện dần TRƯỚC startFrame và mờ dần SAU endFrame: cảnh sau nằm trên cảnh
  // trước (thứ tự map trong MainVideo) nên đoạn hiện dần chính là dissolve.
  const opacity = interpolate(
    frame,
    [startFrame - crossfadeFrames, startFrame, endFrame, endFrame + crossfadeFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Scale tối thiểu 1,06 để pan ±2,5% không bao giờ lộ mép đen.
  const scale = interpolate(frame, [startFrame, endFrame], [...motion.scale], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const panX = interpolate(frame, [startFrame, endFrame], [...motion.panX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      <Img
        src={staticFile(scene.imagePath)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translateX(${panX}%) scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Viết lại `MainVideo.tsx`**

```tsx
import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { SceneBackground } from "./SceneBackground";
import { Waveform } from "./Waveform";
import { Caption } from "./Caption";

// Dissolve giữa hai cảnh. Dài hơn khoảng nghỉ 0,5s giữa chương (gap_seconds ở
// config/voice.yaml) là cố ý: ảnh tan dần qua ranh giới chương nhìn mềm hơn
// là cắt đúng lúc tiếng ngắt.
const CROSSFADE_SECONDS = 1.0;

export const MainVideo: React.FC<VideoProps> = ({ audioPath, chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);
  const seconds = frame / fps;

  const currentChapter = chapters.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );

  // Trải mọi cảnh của mọi chương thành một dãy, đánh số liên tục để chọn kiểu
  // chuyển động luân phiên trên toàn tập chứ không reset mỗi chương.
  const scenes = chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({ chapterIndex: chapter.index, scene }))
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {scenes.map(({ chapterIndex, scene }, i) => (
        <SceneBackground
          key={`${chapterIndex}-${scene.number}`}
          scene={scene}
          startFrame={Math.round(scene.startSeconds * fps)}
          endFrame={Math.round(scene.endSeconds * fps)}
          crossfadeFrames={crossfadeFrames}
          motionIndex={i}
        />
      ))}
      {/* Vignette tĩnh: tối nhẹ bốn góc để ảnh có chiều sâu và chữ dễ đọc hơn. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)",
          pointerEvents: "none",
        }}
      />
      <Avatar />
      {audioPath ? <Waveform audioPath={audioPath} /> : null}
      {currentChapter ? (
        <div
          style={{
            position: "absolute",
            top: 190,
            left: 24,
            color: "#fff",
            fontStyle: "italic",
            fontSize: 20,
          }}
        >
          {currentChapter.heading}
        </div>
      ) : null}
      <Caption chapters={chapters} />
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 4: Xoá `ChapterBackground.tsx`, sửa chú thích `config/voice.yaml`**

```bash
git rm remotion/src/ChapterBackground.tsx
```

Trong `config/voice.yaml` dòng 6, đổi chú thích thành:

```yaml
gap_seconds: 0.5  # Khoảng nghỉ giữa chương. Crossfade ảnh (MainVideo.tsx) cố ý dài hơn, 1,0s.
```

- [ ] **Step 5: Typecheck**

Run: `cd remotion && npm run typecheck`
Expected: không lỗi. Nếu báo `ChapterBackground` còn được import ở đâu: `grep -rn ChapterBackground remotion/src` và xoá.

- [ ] **Step 6: Commit**

```bash
git add remotion/src/types.ts remotion/src/SceneBackground.tsx remotion/src/MainVideo.tsx config/voice.yaml
git commit -m "feat(remotion): mỗi cảnh một lớp pan/zoom, crossfade 1s, vignette"
```

---

### Task 7: `shorts/props_builder.py` — chọn cảnh theo thời điểm phần bắt đầu

**Files:**
- Modify: `shorts/props_builder.py`
- Test: `tests/shorts/test_props_builder.py`, `tests/shorts/test_cli.py` (fixture dòng ~88–100)

**Interfaces:**
- Consumes: metadata ảnh Task 3; `ShortPart.source_start_seconds`.
- Produces: `imagePath` của short = ảnh của cảnh **cuối cùng có `start_seconds <= part.source_start_seconds`** trong chương của phần; không có cảnh nào thoả thì cảnh 1.

- [ ] **Step 1: Sửa fixture và thêm test**

Trong `tests/shorts/test_props_builder.py`, `_images_metadata()` đổi thành:

```python
def _images_metadata() -> dict:
    return {
        "trope": TROPE,
        "title": TITLE,
        "chapters": [
            {"index": 1, "scenes": [
                {"number": 1, "start_seconds": 0.0, "end_seconds": 50.0,
                 "filename": "anh-1-1.png", "scene_description": "..."},
                {"number": 2, "start_seconds": 50.0, "end_seconds": 100.0,
                 "filename": "anh-1-2.png", "scene_description": "..."},
            ]},
            {"index": 2, "scenes": [
                {"number": 1, "start_seconds": 100.0, "end_seconds": 150.0,
                 "filename": "anh-2-1.png", "scene_description": "..."},
            ]},
        ],
    }
```

Trong `_setup_repo`, thay hai dòng tạo `anh-1.png`/`anh-2.png` bằng ba file `anh-1-1.png`, `anh-1-2.png`, `anh-2-1.png`. Test sẵn có `test_props_dung_anh_cua_chuong_chua_phan` đổi khẳng định thành `"output/images/anh-2-1.png"` (phần mặc định bắt đầu ở giây 90, chương 2 chỉ có một cảnh).

Mở rộng helper `_part` sẵn có để chọn được mốc bắt đầu — thay chữ ký và hai dòng mốc:

```python
def _part(
    number: int = 2,
    chapter_index: int = 2,
    source_start_seconds: float = 90.0,
    source_end_seconds: float = 95.5,
) -> ShortPart:
    return ShortPart(
        number=number,
        chapter_index=chapter_index,
        heading="Chương 2: Cao trào",
        source_start_seconds=source_start_seconds,
        source_end_seconds=source_end_seconds,
        captions=[
            PartCaption(text="Cô ấy đến.", start_seconds=0.0, end_seconds=2.5),
            PartCaption(text="Trời mưa.", start_seconds=2.65, end_seconds=5.5),
        ],
    )
```

Thêm hai test:

```python
def test_phan_bat_dau_giua_chuong_lay_canh_dang_chieu(tmp_path):
    # Phần bắt đầu ở giây 70 của chương 1 -> cảnh 2 (50s-100s), không phải cảnh 1.
    props = _build(
        tmp_path,
        part=_part(chapter_index=1, source_start_seconds=70.0, source_end_seconds=95.0),
    )

    assert props["imagePath"] == "output/images/anh-1-2.png"


def test_metadata_anh_khong_co_scenes_thi_bao_chay_lai_stage_3(tmp_path):
    images_metadata = _images_metadata()
    images_metadata["chapters"][0] = {"index": 1, "filename": "anh-1.png", "scene_description": "..."}

    with pytest.raises(ShortPropsBuildError, match="chạy lại stage 3"):
        _build(tmp_path, images_metadata=images_metadata)
```

Nếu file chưa có helper `_part(...)`, thêm một helper dựng `ShortPart(number=1, chapter_index=..., heading="Chương", source_start_seconds=start, source_end_seconds=end, captions=[])`.

Trong `tests/shorts/test_cli.py` (dòng ~88–100) đổi fixture sang cùng cấu trúc `scenes` và tạo file `anh-1-1.png`, `anh-2-1.png` (mỗi chương một cảnh phủ kín chương là đủ cho test CLI).

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/shorts/ -q`
Expected: FAIL — `KeyError: 'filename'` hoặc test mới đỏ.

- [ ] **Step 3: Sửa `build_short_props`**

Thay đoạn từ `image_chapter = images_by_index.get(...)` đến `image_path = images_dir / image_chapter["filename"]`:

```python
    images_by_index = {c["index"]: c for c in images_metadata["chapters"]}
    image_chapter = images_by_index.get(part.chapter_index)
    if image_chapter is None:
        raise ShortPropsBuildError(
            f"Metadata ảnh không có chương {part.chapter_index}"
        )
    scenes = image_chapter.get("scenes")
    if not scenes:
        raise ShortPropsBuildError(
            f"Metadata ảnh của chương {part.chapter_index} không có mảng 'scenes' -- "
            "tập này dựng trước khi stage 3 biết chia cảnh. Hãy chạy lại stage 3."
        )

    # Lấy cảnh đang chiếu lúc phần bắt đầu: cảnh cuối cùng có start <= mốc đầu
    # phần. Cùng cách chọn "mốc gần nhất đã qua" như phụ đề, và cùng lý do:
    # không cần so cả hai đầu, chỉ cần biết đã đi qua ranh giới nào.
    scene = scenes[0]
    for candidate in scenes:
        if candidate["start_seconds"] <= part.source_start_seconds:
            scene = candidate

    image_path = images_dir / scene["filename"]
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `uv run pytest tests/shorts/ -q`
Expected: tất cả pass.

- [ ] **Step 5: Commit**

```bash
git add shorts/props_builder.py tests/shorts/
git commit -m "feat(shorts): short lấy ảnh của cảnh đang chiếu lúc phần bắt đầu"
```

---

### Task 8: Nối dây chuyền, n8n, tài liệu

**Files:**
- Modify: `run_daily.sh:146`
- Modify: `tests/fake_stage.sh:39-42`
- Modify: `tests/test_run_daily.py` (test stage 3, dòng ~142)
- Modify: `n8n/audiobook-pipeline.workflow.json` (node `Stage 3: Ảnh nền`)
- Modify: `.claude/skills/generating-audiobook-video/SKILL.md`, `docs/DAILY_AUTOMATION.md`

- [ ] **Step 1: Sửa test run_daily**

Trong `tests/test_run_daily.py`, tìm test khẳng định `run.call_for("images.cli") == f"images.cli {EXPECTED_SCRIPT}"` (dòng ~142) và đổi thành:

```python
    assert run.call_for("images.cli") == f"images.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON}"
```

Nếu chưa có hằng `EXPECTED_AUDIO_JSON`, thêm cạnh `EXPECTED_IMAGES_JSON` với giá trị đúng dòng `Metadata:` mà nhánh `tts.cli` của `tests/fake_stage.sh` in ra (đọc file để lấy).

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/test_run_daily.py -q -k images`
Expected: FAIL — lệnh thật chưa có `$AUDIO_JSON`.

- [ ] **Step 3: Sửa `run_daily.sh` và `fake_stage.sh`**

`run_daily.sh` dòng 146:

```bash
# Stage 3 cần mốc câu của stage 2 để chia mỗi chương thành cảnh ~50s.
run_stage "Stage 3: Ảnh nền" "$IMAGES_LOG" $RUNNER images.cli "$SCRIPT_PATH" "$AUDIO_JSON"
```

`tests/fake_stage.sh` nhánh `images.cli`:

```bash
  images.cli)
    echo "Đã lưu 64 ảnh vào output/images"
    echo "Metadata: output/images/me_chong_giau_cua-20260813T013500Z.json"
    ;;
```

- [ ] **Step 4: Sửa n8n**

Trong `n8n/audiobook-pipeline.workflow.json`, node `Stage 3: Ảnh nền`, `parameters.command` đổi thành:

```
=cd /Users/lee/Project/Apps/audiobook && uv run python -m images.cli {{ $json.script_path }} {{ $json.audio_json }}
```

(`audio_json` là trường mà node `Parse Stage 2` đã đặt.) Node `Parse Stage 3` giữ nguyên.

Kiểm tra JSON còn hợp lệ và không có connection treo:

```bash
uv run python -c "
import json; w=json.load(open('n8n/audiobook-pipeline.workflow.json'))
names={n['name'] for n in w['nodes']}
for src,outs in w['connections'].items():
    assert src in names, src
    for branch in outs['main']:
        for c in branch: assert c['node'] in names, c['node']
print('n8n ok', len(names), 'node')"
```

- [ ] **Step 5: Sửa tài liệu**

`.claude/skills/generating-audiobook-video/SKILL.md`:
- Bảng stage, dòng stage 3: lệnh `uv run python -m images.cli <script_path> <tts_metadata_path>`; đầu vào "stage 1 + 2's JSON"; đầu ra "`output/images/<trope>-<ts>.json` + ~64 `.png`, một ảnh cho mỗi cảnh ~50s".
- Đoạn mô tả stage 3 (dòng ~32) và mục "Expecting this to be fast" (dòng ~119): stage 3 nay **~50 phút** cho 16 chương (~64 ảnh × 44s, đo 05/09), và **phụ thuộc stage 2** — không chạy được cho tập dựng trước khi stage 2 ghi mốc câu.
- Thêm vào mục lỗi hay gặp: "`video.cli`/`shorts.cli` báo *chạy lại stage 3*: metadata ảnh là định dạng cũ (một ảnh mỗi chương), phải chạy lại stage 3 với TTS JSON."

`docs/DAILY_AUTOMATION.md`: dòng 59 `Stage 3  images.cli  ~50m → output/images/<slug>-<ts>.json + ~64 png`; dòng 191 sửa lý do "Bình thường: ~64 ảnh, mflux nạp lại model cho từng ảnh".

- [ ] **Step 6: Chạy toàn bộ test**

Run: `uv run pytest tests/ -q`
Expected: tất cả pass, output sạch.

- [ ] **Step 7: Commit**

```bash
git add run_daily.sh tests/fake_stage.sh tests/test_run_daily.py n8n/audiobook-pipeline.workflow.json .claude/skills/generating-audiobook-video/SKILL.md docs/DAILY_AUTOMATION.md
git commit -m "feat(daily): stage 3 nhận TTS JSON; cập nhật n8n và tài liệu cho nhiều cảnh mỗi chương"
```

---

### Task 9: Kiểm chứng trên tập thật

Task này chạy pipeline thật (~50 phút stage 3 + ~25 phút stage 4), **không giao cho subagent** — phiên chính chạy nền và theo dõi.

- [ ] **Step 1: Chạy lại stage 3 cho tập 04/09**

```bash
uv run python -m images.cli \
  output/scripts/chong_hien_mau_con-20260904T014918Z.json \
  output/audio/chong_hien_mau_con-20260904T015621Z.json
```

Expected: ~64 dòng `Cảnh i/N: ...`, rồi `Đã lưu 6x ảnh vào ...` và `Metadata: output/images/chong_hien_mau_con-<ts mới>.json`.

- [ ] **Step 2: Kiểm metadata**

```bash
uv run python -c "
import json,glob; p=sorted(glob.glob('output/images/chong_hien_mau_con-*.json'))[-1]; d=json.load(open(p))
sc=[s for c in d['chapters'] for s in c['scenes']]; durs=[s['end_seconds']-s['start_seconds'] for s in sc]
print(p, len(sc), 'cảnh; dài TB %.0fs, ngắn nhất %.0fs, dài nhất %.0fs'%(sum(durs)/len(durs),min(durs),max(durs)))"
```

Expected: ~64 cảnh, trung bình ~50s, không cảnh nào < 25s hay > 80s.

- [ ] **Step 3: Render stage 4 với metadata mới**

```bash
uv run python -m video.cli \
  output/scripts/chong_hien_mau_con-20260904T014918Z.json \
  output/audio/chong_hien_mau_con-20260904T015621Z.json \
  output/images/chong_hien_mau_con-<ts mới>.json
```

- [ ] **Step 4: Cắt một đoạn 2 phút quanh một ranh giới cảnh và gửi người dùng xem**

```bash
ffmpeg -y -ss 00:00:40 -t 120 -i output/video/<file mới>.mp4 -c copy /tmp/preview-2phut.mp4
```

Xem: có đổi cảnh ở ~giây 50 và ~100 không, pan/zoom có thấy không, có lộ mép đen ở góc không, phụ đề và tiêu đề chương còn đúng vị trí không.

- [ ] **Step 5: Ghi số đo vào commit cuối**

Thêm vào SKILL.md thời gian thật của stage 3 và 4 vừa đo (thay con số ước tính "~50 phút" bằng số đo), commit:

```bash
git commit -am "docs: số đo thật stage 3/4 sau khi chia cảnh"
```

---

## Ngoài phạm vi (ghi lại, không làm trong kế hoạch này)

- **Short tĩnh**: `ShortVideo.tsx` vẫn zoom 1→1,08 trên ~100s. Áp cùng `SceneBackground` cho short là việc riêng, sau khi thấy kết quả video dài.
- **mflux nạp lại model mỗi ảnh** (~phần lớn của 44s). Giữ tiến trình sống qua 64 ảnh có thể rút stage 3 từ ~50 phút xuống ~15. Đáng làm nếu 50 phút thành phiền.
- **Parallax theo chiều sâu** (tách lớp bằng mô hình ước lượng độ sâu) — chỉ cân nhắc sau khi (1)+(2) chạy ổn vài tập.
