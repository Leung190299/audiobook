# Longer Script (16 Chapters) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Double story depth by raising the script target from 8 to 16 chapters (~10.4k–12.8k words, ~42–51 min video), and correct two badly stale timing numbers in the pipeline skill doc.

**Architecture:** Only two source files change. `scripts/prompts.py` gains two module-level constants (`TARGET_CHAPTERS`, `TOTAL_WORDS_RANGE`) interpolated into the three places that currently hardcode "8 chương" / "5.000–8.000 từ"; `scripts/qa.py` widens its four validation bounds. Every downstream module (`generator`, `images`, `tts`, `video`, `metadata`, `thumbnail`) already reads the chapter count dynamically from the script JSON, so none of them change.

**Tech Stack:** Python 3.11 + `uv` + `pytest` (all existing; no new dependencies).

## Global Constraints

- Spec: [docs/superpowers/specs/2026-07-23-longer-script-16-chapters-design.md](../specs/2026-07-23-longer-script-16-chapters-design.md)
- `TARGET_CHAPTERS = 16`, `TOTAL_WORDS_RANGE = "10.000–13.000"` — the dash in `TOTAL_WORDS_RANGE` is an **en dash (–, U+2013)**, matching the existing `5.000–8.000` string, not a hyphen.
- Per-chapter length stays **650–800 words** — unchanged. Depth comes from more chapters, not longer ones.
- QA bounds: `MIN_WORDS = 9000`, `MAX_WORDS = 14000`, `MIN_CHAPTERS = 14`, `MAX_CHAPTERS = 18` (target 16 ± 2, preserving the ±2 margin the previous design used around 8).
- `scripts/generator.py` and `build_chapter_prompt` **must not change** — both are already chapter-count-agnostic (`len(chapter_plans)`, `total_chapters` parameter).
- `tests/scripts/test_generator.py` **must stay at 8 chapters** — leaving it at a number other than the target is the evidence that the generator does not hardcode the target.
- Tests assert **literal** expected values (`"16 chương"`), never the constants themselves — asserting via the constant would stay green no matter what the value changed to, defeating the point.
- No real Gemini calls in automated tests (project-wide rule).
- Update living docs only (`SKILL.md`, channel design spec). Historical per-module specs mentioning "8 chương" stay untouched.

---

### Task 1: Parameterize the chapter count in `scripts/prompts.py`

**Files:**
- Modify: `scripts/prompts.py`
- Test: `tests/scripts/test_prompts.py`

**Interfaces:**
- Produces: module constants `scripts.prompts.TARGET_CHAPTERS: int = 16` and `scripts.prompts.TOTAL_WORDS_RANGE: str = "10.000–13.000"`. `build_outline_prompt(trope_name: str, trope_description: str) -> str` and `build_chapter_prompt(chapter_number: int, total_chapters: int, heading: str, summary: str) -> str` keep their existing signatures unchanged.

- [ ] **Step 1: Update the failing test**

In `tests/scripts/test_prompts.py`, replace the first test function with:

```python
def test_build_outline_prompt_includes_trope_details():
    prompt = build_outline_prompt("Trọng sinh báo thù", "Mô tả test.")

    assert "Trọng sinh báo thù" in prompt
    assert "Mô tả test." in prompt
    assert "16 chương" in prompt
    assert "10.000–13.000" in prompt
```

Leave `test_build_chapter_prompt_enforces_minimum_words` exactly as it is — it calls `build_chapter_prompt(3, 8, ...)` with arbitrary arguments and that function is not changing.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/scripts/test_prompts.py -v`

Expected: `test_build_outline_prompt_includes_trope_details` FAILS on `assert "16 chương" in prompt` (the prompt still says "8 chương"). `test_build_chapter_prompt_enforces_minimum_words` still PASSES.

- [ ] **Step 3: Write the implementation**

Replace the full contents of `scripts/prompts.py` with:

```python
# scripts/prompts.py
TARGET_CHAPTERS = 16
TOTAL_WORDS_RANGE = "10.000–13.000"

SYSTEM_PROMPT = f"""Bạn là biên kịch chuyên viết truyện audio tiếng Việt cho kênh YouTube.
Nhiệm vụ: sáng tác một truyện HOÀN TOÀN GỐC (nguyên tác của bạn), lấy cảm hứng từ
motif/trope được cung cấp — KHÔNG được chuyển thể, dịch, hay mô phỏng sát nội dung
của bất kỳ tiểu thuyết/tác phẩm có sẵn nào. Nhân vật, tên riêng, tình tiết cụ thể
phải do bạn tự sáng tạo.

Yêu cầu:
- Độ dài: {TOTAL_WORDS_RANGE} từ tiếng Việt.
- Chia thành đúng {TARGET_CHAPTERS} chương, mỗi chương có tiêu đề ngắn gọn.
- Văn phong ưu tiên thoại và diễn biến tâm lý nhân vật hơn là mô tả thị giác thuần
  tuý, vì người nghe không nhìn màn hình khi nghe.
- Có cao trào rõ ràng và kết thúc thoả mãn (không bỏ lửng trừ khi được yêu cầu).
- Không dùng tên nhân vật, địa danh, hoặc chi tiết cốt truyện trùng với tác phẩm nổi
  tiếng nào đang tồn tại.
"""


def build_outline_prompt(trope_name: str, trope_description: str) -> str:
    return f"""{SYSTEM_PROMPT}

Motif: {trope_name}
Mô tả motif: {trope_description}

Hãy LÊN DÀN Ý (outline) cho truyện gốc theo motif trên — CHƯA viết nội dung đầy đủ, chỉ
lên kế hoạch. Dàn ý gồm:
- Tiêu đề truyện (dạng câu hook giật).
- Đúng {TARGET_CHAPTERS} chương, mỗi chương có: tiêu đề ngắn gọn, và tóm tắt 2-3 câu về diễn biến
  chính, nhân vật xuất hiện, và cảm xúc/xung đột trung tâm của chương đó. Đảm bảo mạch
  truyện xuyên suốt có cao trào rõ ràng ở các chương cuối và kết thúc thoả mãn.

QUAN TRỌNG: Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm bất kỳ giải thích hay
văn bản nào khác ngoài JSON, đúng theo cấu trúc sau — "chapters" PHẢI là một mảng gồm
CHÍNH XÁC {TARGET_CHAPTERS} object phẳng (không được lồng mảng con, không được bọc thêm object cha
nào khác), mỗi object chỉ có đúng 2 field "heading" và "summary" dạng chuỗi văn bản:
{{
  "title": "<tiêu đề truyện>",
  "chapters": [
    {{"heading": "<tiêu đề chương 1>", "summary": "<tóm tắt chương 1>"}},
    {{"heading": "<tiêu đề chương 2>", "summary": "<tóm tắt chương 2>"}}
  ]
}}
"""


def build_chapter_prompt(
    chapter_number: int, total_chapters: int, heading: str, summary: str
) -> str:
    return f"""Bây giờ hãy viết ĐẦY ĐỦ nội dung Chương {chapter_number}/{total_chapters}: "{heading}".

Tóm tắt diễn biến chương này theo dàn ý đã thống nhất ở trên: {summary}

YÊU CẦU BẮT BUỘC:
- Viết đầy đủ cảnh, thoại giữa các nhân vật, diễn biến nội tâm chi tiết — KHÔNG tóm tắt.
- Độ dài BẮT BUỘC từ 650 đến 800 từ — TUYỆT ĐỐI không vượt quá 800 từ (các chương trước
  từng viết dài hơn yêu cầu, dẫn đến tổng truyện vượt giới hạn cho phép). Nếu thấy nội
  dung sắp hết trước khi đủ 650 từ, hãy mở rộng bằng thêm thoại, thêm miêu tả cảm
  xúc/suy nghĩ nhân vật, thêm chi tiết bối cảnh — nhưng dừng lại ngay khi chạm mốc 800 từ.
- Giữ nhất quán với các chương trước đó trong cuộc trò chuyện này (tên nhân vật, bối
  cảnh, mạch cảm xúc, mốc thời gian).
- CHỈ trả về nội dung văn xuôi của chương, KHÔNG kèm tiêu đề chương, KHÔNG kèm JSON,
  KHÔNG kèm giải thích hay bình luận nào khác ngoài nội dung truyện.
"""
```

Three things to note about this rewrite:
1. `SYSTEM_PROMPT` becomes an **f-string** (it now interpolates the two constants) — it previously was a plain string.
2. The JSON example braces inside `build_outline_prompt` stay doubled (`{{`/`}}`) — that function was already an f-string, so this is unchanged.
3. `build_chapter_prompt` is byte-for-byte unchanged from the current file.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/scripts/test_prompts.py -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/prompts.py tests/scripts/test_prompts.py
git commit -m "feat: raise script target from 8 to 16 chapters"
```

---

### Task 2: Widen the QA bounds in `scripts/qa.py`

**Files:**
- Modify: `scripts/qa.py`
- Test: `tests/scripts/test_qa.py`

**Interfaces:**
- Produces: `scripts.qa.MIN_WORDS = 9000`, `MAX_WORDS = 14000`, `MIN_CHAPTERS = 14`, `MAX_CHAPTERS = 18`. `validate_script(script: Script) -> None` keeps its signature and its behavior of raising `ScriptQAError` with all failures joined by `"; "`.

- [ ] **Step 1: Update the failing tests**

Replace the full contents of `tests/scripts/test_qa.py` with the following. Every word count below is arithmetic-checked against `_make_script`'s integer division (`word_count // num_chapters`, then that many words per chapter, so the real total is usually *less* than the requested `word_count` unless it divides evenly — the `extra_text` words make up the difference where an exact boundary is needed):

```python
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
    # 11200 // 16 = 700, 700 * 16 = 11200 (divides evenly, no rounding loss)
    script = _make_script(word_count=11200, num_chapters=16)
    assert script.word_count == 11200
    validate_script(script)  # không raise


def test_validate_script_raises_when_too_short():
    # 1600 // 16 = 100, 100 * 16 = 1600 (well below MIN_WORDS, chapter count valid)
    script = _make_script(word_count=1600, num_chapters=16)
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_many_chapters():
    # 11000 // 20 = 550, 550 * 20 = 11000 (words valid, but 20 > MAX_CHAPTERS)
    script = _make_script(word_count=11000, num_chapters=20)
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_when_banned_term_present():
    # Valid words and chapters; the 3 extra words keep it inside MAX_WORDS.
    script = _make_script(word_count=11200, num_chapters=16, extra_text="phù mỏ audio")
    with pytest.raises(ScriptQAError, match="từ khoá bị cấm"):
        validate_script(script)


def test_validate_script_passes_at_exact_minimum_boundaries():
    # 9000 // 14 = 642, 642 * 14 = 8988, so add 12 extra words to reach exactly 9000
    script = _make_script(
        word_count=9000,
        num_chapters=14,
        extra_text="từ từ từ từ từ từ từ từ từ từ từ từ",
    )
    assert script.word_count == 9000  # exactly MIN_WORDS
    assert len(script.chapters) == 14  # exactly MIN_CHAPTERS
    validate_script(script)  # không raise


def test_validate_script_passes_at_exact_maximum_boundaries():
    # 14000 // 18 = 777, 777 * 18 = 13986, so add 14 extra words to reach exactly 14000
    script = _make_script(
        word_count=14000,
        num_chapters=18,
        extra_text="từ từ từ từ từ từ từ từ từ từ từ từ từ từ",
    )
    assert script.word_count == 14000  # exactly MAX_WORDS
    assert len(script.chapters) == 18  # exactly MAX_CHAPTERS
    validate_script(script)  # không raise


def test_validate_script_raises_just_below_minimum_words():
    # 8999 // 16 = 562, 562 * 16 = 8992, so add 7 extra words to reach exactly 8999
    script = _make_script(word_count=8999, num_chapters=16, extra_text="từ từ từ từ từ từ từ")
    assert script.word_count == 8999  # one word below MIN_WORDS
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_words():
    # 14001 // 16 = 875, 875 * 16 = 14000, so add 1 extra word to reach exactly 14001
    script = _make_script(word_count=14001, num_chapters=16, extra_text="từ")
    assert script.word_count == 14001  # one word above MAX_WORDS
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_few_chapters():
    # 13000 // 13 = 1000, 1000 * 13 = 13000 (words valid, but 13 < MIN_CHAPTERS)
    script = _make_script(word_count=13000, num_chapters=13)
    assert script.word_count == 13000
    assert len(script.chapters) == 13
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_chapters():
    # 11400 // 19 = 600, 600 * 19 = 11400 (words valid, but 19 > MAX_CHAPTERS)
    script = _make_script(word_count=11400, num_chapters=19)
    assert script.word_count == 11400
    assert len(script.chapters) == 19
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_aggregates_multiple_failures_in_one_message():
    # 1000 // 20 = 50, 50 * 20 = 1000 (< MIN_WORDS AND > MAX_CHAPTERS)
    script = _make_script(word_count=1000, num_chapters=20)
    assert script.word_count == 1000  # below minimum
    assert len(script.chapters) == 20  # above maximum
    with pytest.raises(ScriptQAError) as exc_info:
        validate_script(script)
    message = str(exc_info.value)
    assert "Độ dài" in message
    assert "Số chương" in message
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/scripts/test_qa.py -v`

Expected: multiple FAILURES against the still-old bounds — notably `test_validate_script_passes_for_valid_script` fails because 11200 words exceeds the current `MAX_WORDS = 8000` and 16 chapters exceeds the current `MAX_CHAPTERS = 10`.

- [ ] **Step 3: Write the implementation**

In `scripts/qa.py`, replace the four constants at the top:

```python
MIN_WORDS = 5000
MAX_WORDS = 8000
MIN_CHAPTERS = 6
MAX_CHAPTERS = 10
```

with:

```python
MIN_WORDS = 9000
MAX_WORDS = 14000
MIN_CHAPTERS = 14
MAX_CHAPTERS = 18
```

Nothing else in the file changes — `validate_script` already reads these constants.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/scripts/test_qa.py -v`

Expected: 11 passed

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`

Expected: all tests pass. In particular `tests/scripts/test_generator.py` must still pass **unchanged at 8 chapters** — it exercises `generate_script` against a mocked Gemini client whose outline declares 8 chapters, proving the generator follows the outline rather than the new target.

- [ ] **Step 6: Commit**

```bash
git add scripts/qa.py tests/scripts/test_qa.py
git commit -m "feat: widen script QA bounds for 16-chapter target"
```

---

### Task 3: Update the living docs

**Files:**
- Modify: `.claude/skills/generating-audiobook-video/SKILL.md`
- Modify: `docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md`

**Interfaces:** none — documentation only, no code or tests.

- [ ] **Step 1: Fix the stage-3 chapter count and timing in SKILL.md**

Find this text (line 27):

```
Every run (including after the weights are cached) reloads the model from scratch **per chapter** (8×), so stage 3 alone takes roughly 20-25 minutes for a full 8-chapter script — this is normal, not a hang.
```

Replace with:

```
Every run (including after the weights are cached) reloads the model from scratch **per chapter** (16×), so stage 3 takes roughly 10 minutes for a full 16-chapter script — this is normal, not a hang. (Measured 2026-07-22: 8 images took ~5 minutes, so ~40s per image. An earlier version of this doc claimed 20-25 minutes for 8 images; that was an estimate, never a measurement, and it was wrong by ~4×.)
```

- [ ] **Step 2: Fix the per-chapter-mode line in SKILL.md**

Find this text (line 46):

```
**Stage 2 also has a per-chapter mode** for speeding up an 8-chapter run (see "Parallel TTS" below):
```

Replace with:

```
**Stage 2 also has a per-chapter mode** for speeding up a 16-chapter run (see "Parallel TTS" below):
```

- [ ] **Step 3: Fix the Parallel TTS intro line in SKILL.md**

Find this text (line 50):

```
Running all 8 chapters through `tts.cli --chapter N` lets you parallelize stage 2, which otherwise dominates total pipeline time (TTS is CPU-only on this machine). Real findings from doing this on the operator's 16GB MacBook Air (8 cores):
```

Replace with:

```
Running all 16 chapters through `tts.cli --chapter N` lets you parallelize stage 2, which otherwise dominates total pipeline time (TTS is CPU-only on this machine). Real findings from doing this on the operator's 16GB MacBook Air (8 cores):
```

- [ ] **Step 4: Replace the wrong parallel-TTS timing claim in SKILL.md**

Find this bullet (line 53):

```
- **2-way parallelism is a modest win, not ~2x.** CPU contention roughly doubles each individual chapter's wall time (solo ~20-31 min → ~44-54 min when paired), so a round of 2 chapters takes about as long as one chapter would solo-adjacent-plus-overhead — the net saving over fully sequential (8 × solo time) is real but only around 15-25%, not linear speedup.
```

Replace with:

```
- **Measured throughput: ~24 minutes per round of 2 chapters** (~12 min effective per chapter). Timed across all 4 rounds of a real 8-chapter run on 2026-07-22 — the rounds took 25, 24, 23, and 23 minutes, so 8 chapters took ~1.6 hours end to end; expect **~3.2 hours for 16 chapters** (8 rounds). An earlier version of this doc claimed pairing inflates each chapter to "~44-54 min" and yields only a 15-25% saving; the measurements above contradict that. Note there is no clean solo-chapter measurement from the same run, so the exact parallel-vs-sequential speedup ratio is unknown — only the paired throughput above is measured.
```

- [ ] **Step 5: Update the batching example in SKILL.md**

Find this bullet (line 55):

```
- **Practical batching that worked:** chapters `[1]` (or whichever's already done) reused as-is, then rounds of `[2,3]`, `[4,5]`, `[6,7]`, `[8]` (last one solo since 7 is odd) — each round launched as two separate direct (non-agent) `Bash` calls with `run_in_background: true` in the same turn, then wait for both completion notifications before starting the next round.
```

Replace with:

```
- **Practical batching that worked:** rounds of `[1,2]`, `[3,4]`, `[5,6]`, `[7,8]`, `[9,10]`, `[11,12]`, `[13,14]`, `[15,16]` — 8 rounds for a 16-chapter script. Each round is launched as two separate direct (non-agent) `Bash` calls with `run_in_background: true` in the same turn, then wait for both completion notifications before starting the next round. Any chapter already synthesized can be reused as-is and skipped.
```

- [ ] **Step 6: Fix the "Expecting this to be fast" mistake bullet in SKILL.md**

Find this bullet (line 105):

```
- **Expecting this to be fast.** TTS runs on CPU (no GPU/MPS on this project's dev machine); image generation reloads the mflux model from scratch for each of the 8 chapters (~20-25 min total for stage 3, more on the very first run while weights download) — don't assume a hang is a failure.
```

Replace with:

```
- **Expecting this to be fast.** A full 16-chapter run is a multi-hour job, dominated by TTS (~3.2 hours; CPU-only, no GPU/MPS on this project's dev machine). Image generation reloads the mflux model from scratch per chapter (~10 min total for stage 3's 16 images, more on the very first run while weights download) — don't assume a hang is a failure.
```

- [ ] **Step 7: Update the channel design spec's video-length and word-count figures**

In `docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md`:

Find (line 21):

```
- **Định dạng video**: audio full 1 tập/truyện, 25–45 phút, ảnh nền tĩnh hoặc pan nhẹ (Ken Burns), tiêu đề dạng "câu hook giật + #Full audio".
```

Replace with:

```
- **Định dạng video**: audio full 1 tập/truyện, 40–55 phút (cập nhật 2026-07-23 khi nâng kịch bản từ 8 lên 16 chương — xem [2026-07-23-longer-script-16-chapters-design.md](2026-07-23-longer-script-16-chapters-design.md)), ảnh nền tĩnh hoặc pan nhẹ (Ken Burns), tiêu đề dạng "câu hook giật + #Full audio".
```

Find (line 31), the tail of the background-image bullet:

```
đổi theo từng phân đoạn/chương để tránh nhàm chán khi nghe 25–45 phút. Sinh bằng **Flux**.
```

Replace with:

```
đổi theo từng phân đoạn/chương để tránh nhàm chán khi nghe 40–55 phút. Sinh bằng **Flux**.
```

Find (line 38):

```
   → 1. LLM sinh kịch bản: outline + full script (~5.000–8.000 từ/tập), chia theo chương/phân đoạn
```

Replace with:

```
   → 1. LLM sinh kịch bản: outline + full script (~10.000–13.000 từ/tập), chia theo chương/phân đoạn
```

- [ ] **Step 8: Verify no stale figures remain in the two living docs**

Run:

```bash
grep -n "25–45 phút\|5\.000–8\.000\|8 chapters\|8-chapter\|20-25 min" .claude/skills/generating-audiobook-video/SKILL.md docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md
```

Expected: **no output** (exit code 1). Every hit would be a missed replacement.

Note that a similar grep across `docs/superpowers/specs/` as a whole WILL still return hits in the older per-module specs (`flux-images`, `seo-metadata`, `thumbnail`, `images-mflux-migration`). Those are deliberately left alone — they are historical records of each module's design at the time, not current standards.

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/generating-audiobook-video/SKILL.md docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md
git commit -m "docs: update living docs for 16-chapter scripts and fix stale timings"
```

---

### Task 4: Manual smoke test (not automated)

**Files:** none (verification only, no code changes)

**Interfaces:** none — exercises `python -m scripts.cli <trope_id>`, built by Tasks 1-2.

This task is the only check on the plan's main risk: whether Gemini stays coherent across 16 sequential chapters (~11k words of accumulated chat context) instead of 8.

- [ ] **Step 1: Confirm credentials are present**

```bash
test -f .env && grep -c "SECURE_1PSID" .env
```

Expected: prints `2` (both `SECURE_1PSID` and `SECURE_1PSIDTS` present). If `.env` is missing or the cookies have expired, stop and tell the operator to refresh their Gemini cookies — do not attempt to obtain credentials.

- [ ] **Step 2: Generate a real script**

```bash
uv run python -m scripts.cli xuyen_khong_gia_toc
```

Expected: prints `Đã lưu kịch bản: output/scripts/xuyen_khong_gia_toc-<ts>.json (<N> từ, 16 chương)`. Takes roughly 3-4 minutes (17 sequential Gemini calls: 1 outline + 16 chapters).

If it fails QA, the error names which bound was violated — report the actual numbers rather than retrying blindly, since a systematic miss (e.g. Gemini reliably producing 12 chapters) means the prompt needs work, not a retry.

- [ ] **Step 3: Verify the structural numbers**

```bash
python3 -c "
import json, glob
p = sorted(glob.glob('output/scripts/xuyen_khong_gia_toc-*.json'))[-1]
d = json.load(open(p, encoding='utf-8'))
words = sum(len(c['text'].split()) for c in d['chapters'])
print('file:', p)
print('chapters:', len(d['chapters']))
print('total words:', words)
print('per-chapter words:', [len(c['text'].split()) for c in d['chapters']])
"
```

Expected: `chapters: 16`, `total words` between 9000 and 14000, and per-chapter counts clustered in the 650-800 range. A chapter far below 650 is a sign Gemini started running out of material — note it in the report.

- [ ] **Step 4: Read chapters 14, 15, and 16 for consistency drift**

```bash
python3 -c "
import json, glob
p = sorted(glob.glob('output/scripts/xuyen_khong_gia_toc-*.json'))[-1]
d = json.load(open(p, encoding='utf-8'))
for c in d['chapters']:
    if c['index'] in (1, 14, 15, 16):
        print('=' * 70)
        print('CHƯƠNG', c['index'], '—', c['heading'])
        print('=' * 70)
        print(c['text'])
        print()
"
```

Read chapter 1 and the last three, and check specifically:
- **Character names** in chapters 14-16 match those introduced in chapter 1 (no renamed or newly-invented protagonists).
- **Setting and timeline** remain coherent — no contradictions about where characters are or what has already happened.
- **The climax actually lands** and the ending resolves, rather than the story sagging or padding because it was stretched to double length.

- [ ] **Step 5: Report the outcome**

Report to the operator: the actual chapter count and word total, whether chapters 14-16 held consistency, and any drift found. If drift is real, the spec's out-of-scope section already names the follow-up options (periodically re-summarizing context into the prompt, or splitting across multiple chat sessions) — those are a separate iteration, not part of this plan.
