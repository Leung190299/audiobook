---
name: generating-audiobook-video
description: Use when asked to produce, render, or generate a finished audiobook video (MP4) for this project from a trope/story idea — e.g. "tạo video truyện", "render video cho trope X", "chạy full pipeline", "làm 1 tập truyện audio".
---

# Generating an Audiobook Video

## Overview

Chains this repo's four pipeline modules — `scripts` → `tts` → `images` → `video` — into one finished MP4. Each module is a CLI that reads the previous module's JSON output and writes its own JSON + asset output; there is no single orchestrator command, so each stage's exact output path must be captured and passed to the next.

## When to Use

- User names a trope (or asks to pick one) and wants a video produced end-to-end.
- User asks to "run the pipeline" / "render a video" without specifying which stage.

**Not for:** re-running a single stage in isolation (just run that module's CLI directly) or debugging a stage's internals (read that module's own code/tests instead).

## Prerequisites (check once per environment, not per run)

- `.env` exists with real `SECURE_1PSID`/`SECURE_1PSIDTS` (Gemini cookies) — required by `scripts` and `images`. **This is the one that actually breaks in practice.** Without it, stage 1 crashes with a raw `KeyError: 'SECURE_1PSID'` traceback (not a clean auth-error message — `scripts/generator.py` does `os.environ["SECURE_1PSID"]` with no try/except). Check `.env` exists (not just `.env.example`) before running anything. No API key is needed for stage 3 (images) — it runs `mflux-generate-flux2` locally, not a hosted API.
- `cd remotion && npm install` has been run at least once — needed by stage 4 only.
- Pick a `trope_id` from `config/tropes.yaml` (or ask the user which one).

(`uv run` auto-syncs the Python venv itself on first use — no separate `uv sync` step needed.)

**Stage 3 (images) runs `mflux-generate-flux2` locally on-device** (FLUX.2 Klein 4B, quantized) — no `TOGETHER_API_KEY` or any API key required. First run on a machine downloads ~4.3GB of weights (`Runpod/FLUX.2-klein-4B-mflux-4bit`) from HuggingFace — no `HF_TOKEN` needed, this repo isn't gated. Every run (including after the weights are cached) reloads the model from scratch **per chapter** (8×), so stage 3 alone takes roughly 20-25 minutes for a full 8-chapter script — this is normal, not a hang.

If `.env` is missing, stop and tell the user to create it from `.env.example` with real cookie values — don't guess credentials or silently skip the stage.

## The Four Stages

Run from the repo root. Each command prints the path(s) it wrote — capture those from stdout, don't guess filenames. Every stage's output filename embeds its own fresh UTC timestamp (`<trope>-<timestamp>.json`), independently per stage, so stage N's timestamp will NOT match stage N+1's.

| # | Command | Reads | Writes (path printed to stdout) |
|---|---------|-------|----------------------------------|
| 1 | `uv run python -m scripts.cli <trope_id>` | `config/tropes.yaml` | `output/scripts/<trope>-<ts>.json` |
| 2 | `uv run python -m tts.cli <script_path>` | stage 1's JSON | `output/audio/<trope>-<ts>.wav` + `.json` (line 2 of stdout, after "Metadata:") |
| 3 | `uv run python -m images.cli <script_path>` | stage 1's JSON | `output/images/<trope>-<ts>.json` + 8 `.png` (metadata path after "Metadata:") |
| 4 | `uv run python -m video.cli <script_path> <tts_metadata_path> <images_metadata_path>` | stage 1 + 2 + 3's JSON | `output/video/<trope>-<ts>.mp4` |

Stage 2 and 3 both take stage 1's script path directly — they don't depend on each other and could run in parallel, but running them sequentially is simpler to reason about and this repo has no orchestration for concurrent runs.

**Stage 2 also has a per-chapter mode** for speeding up an 8-chapter run (see "Parallel TTS" below): `uv run python -m tts.cli <script_path> --chapter N` synthesizes only chapter N, writing to `output/audio/chapters/` instead of `output/audio/`. A separate merge step, `uv run python -m tts.merge_cli <script_path> <chapter_audio_dir>`, combines all per-chapter files back into one full-story `output/audio/<trope>-<ts>.wav` + `.json` in the exact same format stage 4 expects — so stage 4 is unaffected either way.

### Parallel TTS (stage 2), real findings

Running all 8 chapters through `tts.cli --chapter N` lets you parallelize stage 2, which otherwise dominates total pipeline time (TTS is CPU-only on this machine). Real findings from doing this on the operator's 16GB MacBook Air (8 cores):

- **Run at most 2 chapters concurrently.** Each `tts.cli` process loads OmniVoice (~2.5GB RSS) plus, on first use, a Whisper ASR model for auto-transcribing the voice-clone reference. 2 concurrent processes work reliably; going higher risks OOM on this machine (only ~3.5GB free RAM was observed even with nothing else running).
- **2-way parallelism is a modest win, not ~2x.** CPU contention roughly doubles each individual chapter's wall time (solo ~20-31 min → ~44-54 min when paired), so a round of 2 chapters takes about as long as one chapter would solo-adjacent-plus-overhead — the net saving over fully sequential (8 × solo time) is real but only around 15-25%, not linear speedup.
- **Do NOT dispatch these long-running (20+ min) background jobs through the Agent/subagent tool.** In practice, subagents that start a `run_in_background: true` Bash command and then end their own turn cause that background job to vanish silently sometime later — no Python traceback, no exit code, no crash report, no OS-level jetsam/OOM log entry matching it. It just disappears. Launch these jobs directly from the main session's own Bash tool with `run_in_background: true` instead — that has run reliably for every long job in this project (TTS, image generation, video rendering all take many minutes to tens of minutes).
- **Practical batching that worked:** chapters `[1]` (or whichever's already done) reused as-is, then rounds of `[2,3]`, `[4,5]`, `[6,7]`, `[8]` (last one solo since 7 is odd) — each round launched as two separate direct (non-agent) `Bash` calls with `run_in_background: true` in the same turn, then wait for both completion notifications before starting the next round.

## Example

```bash
uv run python -m scripts.cli trong_sinh_bao_thu
# Đã lưu kịch bản: output/scripts/trong_sinh_bao_thu-20260722T090000Z.json (...)

uv run python -m tts.cli output/scripts/trong_sinh_bao_thu-20260722T090000Z.json
# Đã lưu audio: output/audio/trong_sinh_bao_thu-20260722T091500Z.wav (...)
# Metadata: output/audio/trong_sinh_bao_thu-20260722T091500Z.json

uv run python -m images.cli output/scripts/trong_sinh_bao_thu-20260722T090000Z.json
# Đã lưu 8 ảnh vào output/images
# Metadata: output/images/trong_sinh_bao_thu-20260722T093000Z.json

uv run python -m video.cli \
  output/scripts/trong_sinh_bao_thu-20260722T090000Z.json \
  output/audio/trong_sinh_bao_thu-20260722T091500Z.json \
  output/images/trong_sinh_bao_thu-20260722T093000Z.json
# Đã render video vào output/video/trong_sinh_bao_thu-20260722T094500Z.mp4
```

If a printed path is missed, recover the newest file instead of re-running: `ls -t output/<stage_dir>/*.json | head -1`.

## Common Mistakes

- **Assuming timestamps match across stages.** They don't — always read the printed path, never construct one from a previous stage's timestamp.
- **Passing the wrong JSON to `video.cli`.** It takes 3 paths in this order: script, TTS metadata, images metadata — not the `.wav`/`.png` files themselves.
- **Expecting this to be fast.** TTS runs on CPU (no GPU/MPS on this project's dev machine); image generation reloads the mflux model from scratch for each of the 8 chapters (~20-25 min total for stage 3, more on the very first run while weights download) — don't assume a hang is a failure.
- **Running without a real `.env`.** `scripts`/`images` call Gemini via cookie auth; without real `SECURE_1PSID`/`SECURE_1PSIDTS` they crash with a raw `KeyError` traceback (not a clean error message) — check `.env` exists before starting, don't wait for the crash to notice.
- **Using the Agent/subagent tool to run a long TTS/image/video job in the background.** See "Parallel TTS" above — this has caused jobs to silently vanish. Use the main session's own `Bash` tool with `run_in_background: true` instead.
- **Merging per-chapter TTS audio out of order.** `tts.merge_cli` orders chapters by the *original script's* chapter index, not by filename or discovery order — it's safe to run chapters in any order/any batching, but always pass the same original multi-chapter script JSON as its first argument.
