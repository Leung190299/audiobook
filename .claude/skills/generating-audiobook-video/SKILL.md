---
name: generating-audiobook-video
description: Use when asked to produce, render, or generate a finished audiobook video (MP4) for this project from a trope/story idea — e.g. "tạo video truyện", "render video cho trope X", "chạy full pipeline", "làm 1 tập truyện audio", "chạy tập hôm nay", "làm truyện bắt trend", "up lên YouTube".
---

# Generating an Audiobook Video

## Overview

Chains this repo's pipeline modules — `trend` → `scripts` → `tts` → `images` → `video` → `thumbnail` → `metadata` → `shorts` — into a finished MP4 plus a thumbnail PNG, a vertical YouTube Shorts video, and copy-paste-ready SEO metadata. **The operator uploads to YouTube manually**; stage 8 (`upload/`) exists but is opt-in behind `--upload` and is off by default. Each module is a CLI that reads the previous module's JSON output and writes its own JSON + asset output.

**`./run_daily.sh` already chains all of them** (and notifies via Telegram when it finishes or fails) — prefer it over driving the stages by hand. Run the stages individually only when debugging one of them, or when the user explicitly asks for a partial run. When you do run them by hand, each stage's exact output path must be captured from stdout and passed to the next; nothing derives paths from a previous stage's timestamp.

## When to Use

- User names a trope (or asks to pick one) and wants a video produced end-to-end.
- User asks to "run the pipeline" / "render a video" without specifying which stage.

**Not for:** re-running a single stage in isolation (just run that module's CLI directly) or debugging a stage's internals (read that module's own code/tests instead).

## Prerequisites (check once per environment, not per run)

- `.env` exists with real `SECURE_1PSID`/`SECURE_1PSIDTS` (Gemini cookies) — required by `scripts` and `images`. **This is the one that actually breaks in practice.** Without it, stage 1 crashes with a raw `KeyError: 'SECURE_1PSID'` traceback (not a clean auth-error message — `scripts/generator.py` does `os.environ["SECURE_1PSID"]` with no try/except). Check `.env` exists (not just `.env.example`) before running anything. No API key is needed for stage 3 (images) — it runs `mflux-generate-flux2` locally, not a hosted API.
- `cd remotion && npm install` has been run at least once — needed by stage 4 only.
- Pick a `trope_id` from `config/tropes.yaml` (or ask the user which one) — **or** let stage 0 pick a trending topic instead, which is the default for `./run_daily.sh`.
- Stage 0 needs no credentials at all — it reads public RSS (Dân Trí / VnExpress tâm sự, đời sống, pháp luật; optionally YouTube channel feeds) configured in `config/trend.yaml`. Any source that fails is skipped; it only errors out if every source is dead.
- Stage 8 is only reachable via `./run_daily.sh --upload` and needs `config/youtube_token.json` from `uv run python -m upload.auth`. Do not run it unless the user explicitly asks to publish.
- `uv run python -m preflight.cli --deep` checks all of the above in ~10 seconds. Run it before a long unattended job instead of discovering a missing token at minute 50.

(`uv run` auto-syncs the Python venv itself on first use — no separate `uv sync` step needed.)

**Stage 3 (images) runs `mflux-generate-flux2` locally on-device** (FLUX.2 Klein 4B, quantized) — no `TOGETHER_API_KEY` or any API key required. First run on a machine downloads ~4.3GB of weights (`Runpod/FLUX.2-klein-4B-mflux-4bit`) from HuggingFace — no `HF_TOKEN` needed, this repo isn't gated. It now takes stage 2's TTS metadata JSON as a second argument and uses its per-sentence marks to cut each chapter into ~50s scenes, so **stage 3 depends on stage 2** and can't run for a script stage 2 hasn't processed yet. Every run (including after the weights are cached) reloads the model from scratch **per scene** (~64× for a 16-chapter script), so stage 3 now takes roughly **~50 minutes** — this is normal, not a hang. (Measured 2026-09-05: ~64 images at ~44s per image. An earlier measurement of ~40s/image, from before stage 3 split chapters into scenes, generated only one image per chapter.)

If `.env` is missing, stop and tell the user to create it from `.env.example` with real cookie values — don't guess credentials or silently skip the stage.

## The Stages

Run from the repo root. Each command prints the path(s) it wrote — capture those from stdout, don't guess filenames. Every stage's output filename embeds its own fresh UTC timestamp (`<trope>-<timestamp>.json`), independently per stage, so stage N's timestamp will NOT match stage N+1's.

| # | Command | Reads | Writes (path printed to stdout) |
|---|---------|-------|----------------------------------|
| 0 | `uv run python -m trend.cli` | `config/trend.yaml` (RSS báo + Google Trends, no keys) | `output/ideas/<slug>-<ts>.txt` (path after "Đã lưu ý tưởng:", slug after "Slug:") |
| 1 | `uv run python -m scripts.cli <trope_id>` *or* `--idea-file <txt> --label <slug>` | `config/tropes.yaml` or stage 0's `.txt` | `output/scripts/<trope>-<ts>.json` |
| 2 | `uv run python -m tts.cli <script_path>` | stage 1's JSON | `output/audio/<trope>-<ts>.wav` + `.json` (line 2 of stdout, after "Metadata:") |
| 3 | `uv run python -m images.cli <script_path> <tts_metadata_path>` | stage 1 + 2's JSON | `output/images/<trope>-<ts>.json` + ~64 `.png`, một ảnh cho mỗi cảnh ~50s (metadata path after "Metadata:") |
| 4 | `uv run python -m video.cli <script_path> <tts_metadata_path> <images_metadata_path>` | stage 1 + 2 + 3's JSON | `output/video/<trope>-<ts>.mp4` |
| 5 | `uv run python -m thumbnail.cli <script_path>` | stage 1's JSON only | `output/thumbnails/<trope>-<ts>.png` |
| 6 | `uv run python -m metadata.cli <script_path> <tts_metadata_path> <video_path>` | stage 1 + 2 + 4's output | `output/metadata/<trope>-<ts>.txt` + `.json`; also renames stage 4's `.mp4` in place to an SEO slug |
| 7 | `uv run python -m shorts.cli <tts_metadata_path> <images_metadata_path>` | stage 2 + 3's JSON | `output/shorts/<trope>-<ts>-part-NN.mp4` (path after "Đã render short:") + `.txt` (path after "Metadata short:"), one pair printed per part, ~30 parts, then a summary line `Đã render <N> short vào output/shorts` — cuts the whole episode into a numbered series using stage 2's per-sentence timestamps, no re-narration and no Gemini call; runtime not yet measured for the new version, budget noticeably more than the old single-short ~5 min since each part still needs its own Remotion render |
| 8 | *(opt-in)* `uv run python -m upload.cli <renamed_mp4> <metadata_json> --thumbnail <png>` | stage 5 + 6's output | Publishes to YouTube; prints `Đã upload: https://youtu.be/<id>` |

Stage 2 and 3 both take stage 1's script path directly — they don't depend on each other and could run in parallel, but running them sequentially is simpler to reason about and this repo has no orchestration for concurrent runs.

**Stage 2 runs entirely CPU-side** (VieNeu-TTS v3 Turbo via ONNX Runtime, `Vieneu(backend="onnx")`) — one `tts.cli` process loads the model once and synthesizes every chapter sequentially, no per-chapter mode or merge step needed. A single 865-word chapter synthesizes in ~30 seconds in isolation (RTF 0.136), but a real full end-to-end run of all 16 chapters (model load + sequential synthesis + loudness normalization + concatenation) measured **~14 minutes** on the operator's 16GB MacBook Air (2026-07-30, `trong_sinh_mat_the`, 3158s of output audio) — still far faster than OmniVoice, just not as fast as the single-chapter number alone suggests. (The previous OmniVoice engine needed ~12 min/chapter and a 2-process-parallel + merge workaround to stay under ~3.2 hours for 16 chapters; that workaround, including `tts/merge_cli.py`, is gone.)

**Voice is configured in `config/voice.yaml`**, two modes: a built-in preset (`voice: "<name>"`, e.g. `"Thục Đoan"` — pick from `vieneu.list_preset_voices()`, 14 available across Bắc/Trung/Nam) or voice cloning from a reference clip (`ref_audio_path: "config/voices/<file>.mp3"`, overrides `voice` when set). The TTS engine itself stays ONNX/CPU either way; cloning additionally needs `torch`/`torchaudio` (both project dependencies) purely for the reference-audio speaker-embedding feature extraction (CPU only, ~1-4s, no MPS/GPU involved) — not for the synthesis engine, which is unaffected by which mode is active.

## SEO metadata (stage 6)

Stage 6 automates the parts of YouTube SEO that can be derived from data already in the pipeline: title, description (with real chapter timestamps), tags, and hashtags — written to `output/metadata/<trope>-<ts>.txt` (copy-paste ready) and `.json`. It also renames the final `.mp4` to an SEO-friendly slug.

**Manual checklist — do these yourself in YouTube Studio at upload time, this pipeline does not automate them:**

- ~~Uploading the generated thumbnail~~ — **now automated** by stage 8 (`upload/uploader.py::set_thumbnail`). It fails soft: a channel without a verified phone number has no custom-thumbnail permission, in which case stage 8 prints `Thumbnail: chưa đặt` and you set it in Studio. The video itself still uploads.
- **Flipping the video to public**: stage 8 defaults to `private`, and an OAuth project that has not passed Google's API audit gets its uploads forced to `private` regardless of what you request — so this stays a manual step in Studio until that audit is done.
- **Cards & End Screens**: add in YouTube Studio after upload, pointing to related videos/playlists and a subscribe prompt.
- **Pinned comment**: pin a high-value comment or discussion question yourself after publishing.
- **Early engagement**: encourage likes/comments/shares in the first 24-48 hours — this is on you, not automatable.
- **Keyword research tools** (TubeBuddy/VidIQ/Semrush): stage 6's tags/hashtags come from Gemini reading the story content only, with no real search-volume/competition data. Cross-check with a real tool before publishing if ranking matters for that video.

## Thumbnail (stage 5)

Stage 5 generates one `output/thumbnails/<trope>-<ts>.png` (1280×720): mflux renders a dramatic close-up emotional portrait (different style from the background images in stage 3 — those explicitly forbid close-up faces, thumbnails want the opposite), then a short Vietnamese hook phrase (2-4 words, from Gemini) is drawn on top with Pillow using a bundled bold Vietnamese font (`assets/fonts/BeVietnamPro-Black.ttf`) — mflux is never trusted to render the text itself.

Stage 5 only needs the script JSON — it does not depend on stages 2-4's output, so it can run any time after stage 1, though the natural point in a full run is right after stage 4 (video render) finishes.

## Example

```bash
uv run python -m scripts.cli trong_sinh_bao_thu
# Đã lưu kịch bản: output/scripts/trong_sinh_bao_thu-20260722T090000Z.json (...)

uv run python -m tts.cli output/scripts/trong_sinh_bao_thu-20260722T090000Z.json
# Đã lưu audio: output/audio/trong_sinh_bao_thu-20260722T091500Z.wav (...)
# Metadata: output/audio/trong_sinh_bao_thu-20260722T091500Z.json

uv run python -m images.cli output/scripts/trong_sinh_bao_thu-20260722T090000Z.json output/audio/trong_sinh_bao_thu-20260722T091500Z.json
# Đã lưu 64 ảnh vào output/images
# Metadata: output/images/trong_sinh_bao_thu-20260722T093000Z.json

uv run python -m video.cli \
  output/scripts/trong_sinh_bao_thu-20260722T090000Z.json \
  output/audio/trong_sinh_bao_thu-20260722T091500Z.json \
  output/images/trong_sinh_bao_thu-20260722T093000Z.json
# Đã render video vào output/video/trong_sinh_bao_thu-20260722T094500Z.mp4

uv run python -m thumbnail.cli output/scripts/trong_sinh_bao_thu-20260722T090000Z.json
# Đã lưu thumbnail: output/thumbnails/trong_sinh_bao_thu-20260722T094600Z.png
```

If a printed path is missed, recover the newest file instead of re-running: `ls -t output/<stage_dir>/*.json | head -1`.

## Running the daily job

`./run_daily.sh` runs stage 0-7 in order (add `--upload` for stage 8), writes per-stage logs to `output/daily/<date>/0N-<stage>.log`, and notifies on success or failure via `notify/dispatch.py` (macOS notification by default, Telegram if configured). Flags: `--trope <id>` skips stage 0 and uses a fixed trope, `--upload` adds the YouTube publish step (`--no-upload` is accepted but is now the default).

Stage 7 (short) cuts the whole episode into a numbered series of ~30 Shorts (`Phần 1`…`Phần N`, 85-165s each), packing consecutive sentences from stage 2's per-sentence timestamps up to the per-part budget without ever crossing a chapter boundary — see `docs/superpowers/specs/2026-08-22-shorts-series-design.md` for the cutting rule. It's pure computation now, no Gemini call, so it still runs with expired Gemini cookies. **It depends on stage 2, not stage 1** — it needs the TTS metadata JSON's `sentences` array, which only episodes rendered after stage 2 started writing per-sentence marks have. **It cannot run for an episode built before that change**; its TTS metadata only has chapter-level marks, and the only fix is re-running stage 2 for that episode. For a current episode it can still be re-run by hand from just stage 2's and stage 3's JSON — see `output/daily/<date>/07-short.log` for the exact command if it failed. Unlike every other stage, stage 7 failing does **not** abort the run or send a failure notification: by the time it runs, the long video, thumbnail, and SEO metadata are already done, so a broken short (e.g. a Remotion render failure) must not make a successful episode report as a failed run. A failed stage 7 only logs a warning (`CẢNH BÁO: Stage 7: Short THẤT BẠI...`) with the command to retry it manually; the success notification and stage 8 (upload, if `--upload` was passed) still run normally either way.

It parses each stage's stdout with `sed -E`, so **changing a stage's printed output format silently breaks the chain** — the stage still succeeds, then the script fails with "không parse được output" (except stage 7, which only warns, per above). If you edit any CLI's `print()` strings, update the matching pattern in `run_daily.sh` (and in `n8n/audiobook-pipeline.workflow.json`, which parses the same strings).

`tests/test_run_daily.py` covers that chain: it runs the real `run_daily.sh` with `AUDIOBOOK_RUNNER` pointed at `tests/fake_stage.sh`, which prints each stage's exact stdout format without doing any work. **After changing any stage's `print()` output, update `fake_stage.sh` to match and run that test** — it takes ~2 seconds and catches a broken chain that would otherwise surface 50 minutes into a real run.

Scheduling is `launchd/com.lee.audiobook.daily.plist` (09:00 daily). The n8n workflow is an alternative path to the same thing — if both are active the pipeline runs twice a day.

## Common Mistakes

- **Assuming timestamps match across stages.** They don't — always read the printed path, never construct one from a previous stage's timestamp.
- **Passing the wrong JSON to `video.cli`.** It takes 3 paths in this order: script, TTS metadata, images metadata — not the `.wav`/`.png` files themselves.
- **Expecting this to be fast.** A full 16-chapter run now takes about an hour, dominated by stage 3 (images, ~50 min) and stage 4 (video render), not stage 2 (TTS with VieNeu-TTS measured at ~14 minutes for a full 16-chapter script, vs ~3.2 hours for the old OmniVoice engine). Image generation reloads the mflux model from scratch per scene (~50 min total for stage 3's ~64 images — one per ~50s scene, not one per chapter anymore — more on the very first run while weights download) — don't assume a hang is a failure. Stage 3 also **depends on stage 2** now, since it needs stage 2's per-sentence marks to cut each chapter into scenes.
- **`video.cli`/`shorts.cli` báo "chạy lại stage 3".** Metadata ảnh là định dạng cũ (một ảnh mỗi chương), phải chạy lại stage 3 với TTS JSON.
- **Running without a real `.env`.** `scripts`/`images` call Gemini via cookie auth; without real `SECURE_1PSID`/`SECURE_1PSIDTS` they crash with a raw `KeyError` traceback (not a clean error message) — check `.env` exists before starting, don't wait for the crash to notice.
- **Using the Agent/subagent tool to run a long image/video job in the background.** Subagents that start a `run_in_background: true` Bash command and then end their own turn cause that background job to vanish silently sometime later — no traceback, no exit code, no crash report. Launch these jobs directly from the main session's own `Bash` tool with `run_in_background: true` instead — that has run reliably for every long job in this project (image generation, video rendering).
- **Running stage 6 (metadata) before stage 4.** It needs the actual rendered `.mp4` path to rename, and the real TTS metadata for chapter timestamps — both only exist after stages 2 and 4 finish. Stage 5 (thumbnail) has no such ordering requirement — it only needs stage 1's script JSON.
