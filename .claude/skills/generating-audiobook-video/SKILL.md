---
name: generating-audiobook-video
description: Use when asked to produce, render, upload, or schedule a finished audiobook video (MP4) or its Shorts for this project — e.g. "tạo video truyện", "làm video hôm nay", "chạy truyện #42", "dựng lại video", "đăng short", "up lên YouTube", "chạy full pipeline", "đổi video nền", "làm lại avatar/linh vật". Covers the daily story-bank run, the branded on-screen layout, background videos, the frog mascot, uploads and the nightly Shorts job.
---

# Generating an Audiobook Video

## What the channel ships (since 2026-10-05)

One **35–50 min long video per day** + **3 Shorts**, Vietnamese family-drama stories read by TTS. The look copies the *layout* of top audiobook channels (reference: Dứa Audio, 2.38M views on a 38-min video) — **never their branding**:

```
┌───────────── 1024 x 576 ─────────────┐
│ 🐸 vẫy tay │                │ 🐸 đọc truyện│
│            │  VIDEO "THỦ    │  Audio       │
│ Đăng ký    │  CÔNG" GIỮA    │  Truyện      │
│ kênh, 20h  │  (lặp suốt     │ Truyện hư cấu│
│ mỗi tối    │   cả tập)      │ ...do AI tạo │
│ 🐸 kính râm│                │ 🐸 kính râm  │
└──────────────────────────────────────┘
```

- **Static frame start to end.** No burned-in captions, chapter titles, avatar, waveform, hook text or end card. Viewers who want captions turn on YouTube's auto-captions. The cold open still *plays* (it is an audio edit); only its text overlay is gone.
- **Centre = a background video**, picked at random per episode from `assets/backgrounds/`. The centre box follows the clip's aspect ratio: vertical clips (most Douyin clips) show uncropped and the side panels widen; landscape clips are capped at 66% of the width and cropped at the sides.
- **Side panels = channel brand**: cream background from the logo palette, the **frog mascot** top and bottom, "subscribe, new story 20h every night" on the left, channel name + the fixed AI disclosure on the right.
- **One mascot everywhere**: a chubby green frog wearing a Vietnamese conical hat (*nón lá*). It is on the avatar, every thumbnail and both side panels. It was designed (spec 24/09) to differ from competitors' white duck / capybara — do not swap it for a competitor-looking character.

Layout code: `remotion/src/MainVideo.tsx` → `BrandedLayout.tsx` (centre box width) → `BrandPanel.tsx` (panels, colours, AI text) + `BackgroundVideo.tsx` (looped centre clip). Shorts (`ShortVideo.tsx`) keep their own older layout with captions.

## Run it

```bash
./run_daily.sh                 # next story from the bank, build only (no upload)
./run_daily.sh --story 42      # a specific story id from data/story_bank.json
./run_daily.sh --dry-run-pick  # print the next 7 days' picks, build nothing
./run_daily.sh --upload        # build, then upload long video + Shorts
```

`launchd/com.lee.audiobook.daily.plist` runs `./run_daily.sh` at **09:00 daily, build only**. Uploading stays a human step on purpose: it is the one checkpoint before content goes public, and it has caught real problems.

**Prefer `run_daily.sh` over driving stages by hand.** Each stage prints the path the next one needs; `run_daily.sh` parses those lines with BSD `sed -E`. **Changing any stage's `print()` silently breaks the chain** — update the pattern in `run_daily.sh` and `tests/fake_stage.sh`, then run `uv run pytest tests/test_run_daily.py` (~5 s).

## Stages (measured 03–05/10 on an M4 / 16 GB)

| # | Module | ~Time | Notes |
|---|--------|-------|-------|
| 1 | `scripts.cli --story <id>` | 2 min | Title, hook, comment question, thumb keywords come **from the bank**, not Gemini. Approved outline → chapter N follows line N, but **chapter headings come from Gemini** (outline lines are internal notes like "Miếng hài: …"). |
| 2 | `tts.cli` | 5.5 min | VieNeu-TTS, ONNX on CPU. |
| 3 | `images.cli` | 31 min | FLUX.2-klein via mflux. Not shown in the long video any more (background video replaces it) but **Shorts still use these images**, so it stays. |
| 4 | `episodes.cli` | 16–23 min | Remotion render. 23 min with a background video (video decode) vs 16 with images. Picks the background here. |
| 5 | `thumbnail.cli` | 2 min | Frog sticker left + almost-full title right in Anton, keywords coloured. Already matches the reference style. |
| 6 | `metadata.cli` | 5 s | Minimal description (below). Renames the mp4 to the title slug. |
| 7 | `shorts.cli --script` | 1–2 min | 3 Shorts from `short_beats`. **Failure only warns**, never fails the run. |
| 8 | `upload.episodes_cli` | — | Only with `--upload`. |

After stage 7, `run_daily.sh` records `shorts_prefix` into the metadata index and marks the story `built` in the bank (see Gotchas).

## Background videos

Drop `.mp4` files into `assets/backgrounds/` — that's all. Each episode picks one at random (seeded by the episode stem, so a re-render keeps the same clip). New files are picked up automatically.

Each source is prepared **once** by ffmpeg into `assets/backgrounds/.prepared/<name>-h576.mp4`: scaled to 576 px tall keeping its aspect, **audio stripped** (Douyin music would fight the narration), 30 fps. A source that fails ffmpeg is skipped and the episode falls back to the stage-3 images — one bad clip never kills an hour-long run. `assets/backgrounds/` is gitignored (hundreds of MB).

## Mascot, avatar, brand assets

`uv run python -m scripts.make_brand_mascots` draws the panel poses into `remotion/public/mascot-{wave,read,cool}.png` and the avatar into `assets/brand/avatar-frog.png` (800×800). It reuses the thumbnail's exact prompt, model and seed (`thumbnail/sticker.py`: `MASCOT_CHARACTER`, `MASCOT_SEED`), so the frog matches the thumbnails. Background removal is the existing flood-fill `thumbnail.sticker.cut_out_background` — the thick dark outline stops the fill, no extra model needed. Existing files are skipped; `--force` redraws **all four** (~4 min). The avatar's cut-out is cached as `avatar-frog-raw.png`, so re-composing the avatar does not need FLUX: delete only `avatar-frog.png` and run again.

The avatar must be uploaded **by hand in YouTube Studio** — the API cannot change a channel's profile picture.

## Metadata & disclosure

- **Title**: `[Truyện Audio] <story title> | <CHANNEL_NAME>`.
- **Description** (`metadata.full.build_minimal_description`): title → `⚠️ Truyện hư cấu. Kịch bản, giọng đọc và hình ảnh do AI tạo ra.` → `Hashtags:` (topic tags first, ≤15 — over 15 and YouTube ignores all) → `Keywords:`. No chapters, summary, playlist link or question, matching the reference. The side-picking question lives in the pinned comment.
- **AI disclosure** appears in three places: description line 2, fixed on the right side panel, and YouTube's own flag `status.containsSyntheticMedia = true` set at upload. **That flag only takes effect on `videos.insert`, and `videos.list` never returns it** — reading it back always gives `None` even when it is on. Verify in Studio, never by read-back.

## Uploading

`upload.episodes_cli <metadata-index>` uploads the long video as `private` with `publishAt` = the story's `publish_date` at 20:00 (+07:00). **A date already in the past rolls forward** to the next 20:00 with a warning, instead of producing a past `publishAt`. Without a `publish_date`, `--first-air 2026-10-07T20:00` sets it — check it does not collide with an already-scheduled video. It adds the video to its topic playlist (`YOUTUBE_PLAYLIST_*` in `.env`, link or bare `PL…` id — a playlist *name* is rejected) and marks the story `published` with its `video_id`.

**Shorts go out by themselves.** `launchd/com.lee.audiobook.shorts.plist` runs `scripts.post_shorts` at **20:05 every night**: it finds the story whose `published_at` is today (its long video went public five minutes earlier), uploads its 3 Shorts as public and retitles them `<story title> — Trích đoạn N/3` (the default title is a truncated first sentence). It **refuses** if the long video is not public yet — a Short pointing at a private video is a dead link exactly when Shorts get most views. To front-load quota, upload Shorts early as `--privacy private`; the 20:05 job then only flips them public (50 units instead of 1,600).

## Gotchas that have actually bitten

- **Quota is 10,000 units/day and resets at midnight Pacific (~14:00 Vietnam), not local midnight.** `videos.insert` = 1,600 regardless of size. One long video + 3 Shorts ≈ 6,600. Plan multi-video days around this.
- **OAuth token dies every 7 days** (project in Testing mode). Symptom: `invalid_grant` in `output/daily/shorts.err.log` or the upload log. Fix: `uv run python -m upload.auth` — the browser consent is the operator's to click, never Claude's.
- **Only 16 GB RAM.** Never run a second FLUX job (mascots, `mac-image-ai`) while stage 3 or 5 is running, or while a Remotion render is going — swap thrash slows everything and can kill a stage. Check `memory_pressure` first.
- **Don't edit Remotion or stage-4 Python while stage 4 is starting.** Remotion bundles the source once at render start; once `chrome-headless-shell` processes exist, editing is safe for that render.
- **Built-but-unuploaded stories must be marked**, or `--story auto` rebuilds them the next day. Since 02/10 `run_daily.sh` marks `built` after stage 7. A run that dies before stage 7 leaves the story unmarked — check `output/story_bank_state.json` after any failed run.
- **Renaming no longer crashes on a name clash**: a stale earlier build with the same slug makes stage 6 write `<slug>-2.mp4`. Clean old files up by hand; nothing deletes them.
- **Tests must not touch real data.** `tests/conftest.py` blocks YouTube calls and points `assets/backgrounds/` at an empty dir. Resolve path defaults at call time (`x = x or DEFAULT`), not in the signature — a default bound at import makes `monkeypatch` silently miss, and twice that let a test reach real files or the real API.
- **Long jobs from Claude**: background Bash jobs are killed after ~10 min. For a 20-min+ render, launch with `nohup caffeinate -i <script> > log 2>&1 < /dev/null & disown` and watch the log with `Monitor`.
- **Gemini cookies** (`SECURE_1PSID`/`SECURE_1PSIDTS` in `.env`) expire; stages 1, 3 and 6 need them. `AuthError: Failed to refresh cookies` in the log is the early warning.
- Before a long unattended run: `uv run python -m preflight.cli --deep` (~10 s).

## Re-rendering a story in the current style

Stages 1–3 are the slow, reusable part. To rebuild only the visuals:

```bash
uv run python -m episodes.cli <script.json> <audio.json> <images.json>   # prints Manifest:
uv run python -m metadata.cli <script.json> --episodes <manifest.json>   # prints Danh sách:
uv run python -m shorts.cli <audio.json> <images.json> --script <script.json>
uv run python -m scripts.post_shorts --record <metadata-index.json> <shorts-prefix>
uv run python -m scripts.story_bank --mark-used <id>
```

The three input paths are in `output/daily/<date>/01-*.log`, `02-*.log`, `03-*.log` (`Đã lưu kịch bản:` / `Metadata:`).
