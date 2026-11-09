---
name: generating-audiobook-video
description: Use when asked to produce, render, upload, or schedule a finished audiobook video (MP4) or its Shorts for this project — e.g. "tạo video truyện", "làm video hôm nay", "chạy truyện #42", "dựng lại video", "đăng short", "up lên YouTube", "chạy full pipeline", "đổi video nền", "làm lại avatar/linh vật". Covers the daily story-bank run, the branded on-screen layout, background videos, the frog mascot, uploads and the nightly Shorts job.
---

# Generating an Audiobook Video

## What the channel ships (since 2026-10-05)

One **35–50 min long video per day** + **3 Shorts**, Vietnamese family-drama stories read by TTS. The look copies the *layout* of top audiobook channels (reference: Dứa Audio, 2.38M views on a 38-min video) — **never their branding**:

```
┌──────────── 1920 x 1080 ─────────────┐
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
- **Side panels = channel brand**: cream background, two **frog stickers** per panel. Left: "Đừng quên Đăng ký nhé!" sign, card "Truyện mới 20h mỗi tối", "Like nhé!". Right: the "AUDIO TRUYỆN" logo sticker (it carries the channel name — no name text any more), the fixed AI disclosure card, the headphones-reading frog.
- **One mascot everywhere**: a chubby green frog wearing a Vietnamese conical hat (*nón lá*). It is on the avatar, every thumbnail and both side panels. Since 07/10 panels and thumbnails use the channel's own 4×4 sticker sheet (`assets/brand/sticker-sheet.webp`), not FLUX drawings. It was designed (spec 24/09) to differ from competitors' white duck / capybara — do not swap it for a competitor-looking character.

**Output quality**: long video renders at **1920×1080** (was 1024×576 until 05/10 — SD, and it threw away over half the vertical detail of the 1024–1280 px Douyin sources). Remotion's intermediate frames are JPEG 95 (`backgrounds.RENDER_JPEG_QUALITY`; default 80 smeared text edges). 1080p renders ~33% slower than 576p. `BrandPanel` scales all its size clamps by `height / 576`, so changing the frame size keeps the layout.

Layout code: `remotion/src/MainVideo.tsx` → `BrandedLayout.tsx` (centre box width) → `BrandPanel.tsx` (panels, colours, AI text) + `BackgroundVideo.tsx` (looped centre clip). Shorts (`ShortVideo.tsx`) keep their own older layout: 3-second hook text + CTA card. **Since 08/11 Shorts burn no captions either** (channel request); `props.captions` is still sent by stage 7 but not drawn.

## Run it

```bash
./run_daily.sh                 # next story from the bank, build only (no upload)
./run_daily.sh --story 42      # a specific story id from data/story_bank.json
./run_daily.sh --dry-run-pick  # print the next 7 days' picks, build nothing
./run_daily.sh --upload        # build, then upload long video + Shorts
./run_daily.sh --no-keywords   # skip stage 0 keyword research, pick straight from the bank
```

`launchd/com.lee.audiobook.daily.plist` runs `./run_daily.sh --upload` at **09:00 daily: build, then upload** (since 26/10, at the channel's request — before that uploading was a deliberate human checkpoint). Remove the `--upload` line from the plist to go back to build-only. Upload needs a live OAuth token; in Testing mode it dies every 7 days.

**Prefer `run_daily.sh` over driving stages by hand.** Each stage prints the path the next one needs; `run_daily.sh` parses those lines with BSD `sed -E`. **Changing any stage's `print()` silently breaks the chain** — update the pattern in `run_daily.sh` and `tests/fake_stage.sh`, then run `uv run pytest tests/test_run_daily.py` (~5 s).

## Stages (measured 03–05/10 on an M4 / 16 GB)

| # | Module | ~Time | Notes |
|---|--------|-------|-------|
| 0 | `keywords.cli` | ~1–2 min (+ model) | **Since 10/11, on by default for `--story auto`.** Collects YouTube VN search suggestions around the channel's seeds (free) and the 50 latest videos of ~16 competitor channels (Data API, cached 7 days in `output/keywords/`), scores each phrase 0–3 on Cầu / View / Giọng / Mới (`config/keywords.yaml`), and takes the best phrase not used in 30 days. If a bank story's **title** already carries the phrase, that story is picked; otherwise the model writes a new bank record (title must contain the phrase, ≤60 chars, no "Tôi"/"Trọng Sinh" start; hook, premise, twist, question, thumb keyword) into `data/story_bank.auto.json` (gitignored, ids from 1000) and stage 1 runs on it like any bank story. Exit 3 (no phrase above `min_score`) or any failure → warning, then the old `--pick` path. `--no-keywords` / `AUDIOBOOK_KEYWORDS=0` skips it. `uv run python -m keywords.cli --dry-run` prints the scoreboard without writing anything. |
| 1 | `scripts.cli --story <id>` | ~15 min (Claude) / 2 min (Gemini) | Writer chosen by `STORY_LLM` (`claude` / `gemini`, `--llm` overrides; unset → Claude when `ANTHROPIC_API_KEY` is in `.env`) — `scripts/llm.py`. Claude = `claude-opus-5-5`, effort `high`, one multi-turn conversation with prompt caching, server-side refusal fallback. Title, hook, comment question, thumb keywords come **from the bank**, not the model. Approved outline → chapter N follows line N, but **chapter headings come from the model** (outline lines are internal notes like "Miếng hài: …"). |
| 2 | `tts.cli` | 5.5 min | VieNeu-TTS, ONNX on CPU. |
| 3 | `images.cli` | 31 min | **Skipped whenever `assets/backgrounds/` has a video** — long video and Shorts both run on background video. Only runs (FLUX via mflux) as the fallback when that folder is empty. |
| 4 | `episodes.cli` | 27–41 min | Remotion render; picks the background here. Images arg is optional — omitted when stage 3 is skipped. |
| 5 | `thumbnail.cli` | seconds | Frog sticker left + almost-full title right in Anton, keywords coloured. Stickers come from the topic's `thumb_stickers` (A, B) in `scripts/topics.py` — no FLUX. |
| 6 | `metadata.cli` | 5 s | Minimal description (below). Renames the mp4 to the title slug. |
| 7 | `shorts.cli --script` | 1–2 min | 3 Shorts from `short_beats`, each on its own background video (vertical clips preferred). **Failure only warns**, never fails the run. |
| 8 | `upload.episodes_cli` | — | Only with `--upload`. |

After stage 7, `run_daily.sh` records `shorts_prefix` into the metadata index and marks the story `built` in the bank (see Gotchas).

## Background videos

Drop `.mp4` files into `assets/backgrounds/` — that's all. Each episode picks one at random (seeded by the episode stem, so a re-render keeps the same clip). New files are picked up automatically.

Each source is prepared **once** by ffmpeg into `assets/backgrounds/.prepared/`: `<name>-h1080.mp4` for the long video and, for vertical sources only, `<name>-h1920.mp4` for Shorts (Short frame is 1080×1920). Aspect kept, **audio stripped** (Douyin music would fight the narration), 30 fps. Shorts prefer vertical clips; a landscape clip squeezed into a vertical frame keeps only the middle ~32%.

With videos present `run_daily.sh` **skips stage 3 entirely** and calls stages 4 and 7 without an images file — a run drops from ~70 to ~40 min. Empty folder → stage 3 runs and everything uses images as before. A source that fails ffmpeg is skipped and the episode falls back to the stage-3 images — one bad clip never kills an hour-long run. `assets/backgrounds/` is gitignored (hundreds of MB).

## Background music (experiment, 09/11)

Off by default. `AUDIOBOOK_BGM=1 ./run_daily.sh --story <id>` mixes a soft looping pad under the narration of the **long video only** (`episodes/music.py` → `MainVideo` `<Audio loop volume=… />`); `AUDIOBOOK_BGM=<path>` picks a file, `AUDIOBOOK_BGM_VOLUME` (default 0.15) sets the level. The pad is generated locally with `uv run python -m scripts.make_bgm` into `assets/music/` (gitignored) — no downloaded music, so no Content ID risk. The TTS wav is untouched, so Shorts timing is unaffected. One episode was built with it for an A/B on retention; do not turn it on for the daily run until that comparison is in.

## Mascot, avatar, brand assets

`uv run python -m scripts.cut_sticker_sheet` cuts `assets/brand/sticker-sheet.webp` into 16 transparent stickers in `assets/brand/stickers/<name>.png` (logo, nghe-truyen, hay-qua, thu-gian, dang-ky, ngu, cung-nghe, cam-on, hum, truyen-hay, like, chill, moi-luc, co-len, kien-thuc, hen-gap) and copies the four the panels use to `remotion/public/sticker-*.png`. The sheet's white background equals the stickers' white rim, so the rim is removed with the background and redrawn by `thumbnail.sticker.sticker()`. A new sheet with the same 4×4 layout: replace the file and rerun; a different layout: edit `NAMES`. To change which stickers appear: `MASCOT` in `remotion/src/BrandPanel.tsx`, `thumb_stickers` in `scripts/topics.py` (prefer stickers with short speech text — long text fights the title).

`uv run python -m scripts.make_brand_mascots` now only draws the FLUX avatar `assets/brand/avatar-frog.png` (800×800); its cut-out is cached as `avatar-frog-raw.png`.

The avatar must be uploaded **by hand in YouTube Studio** — the API cannot change a channel's profile picture.

## Metadata & disclosure

- **Title**: `[Truyện Audio] <story title> | <CHANNEL_NAME>`.
- **Description** (`metadata.full.build_minimal_description`): title → `⚠️ Truyện hư cấu. Kịch bản, giọng đọc và hình ảnh do AI tạo ra.` → `Hashtags:` (topic tags first, ≤15 — over 15 and YouTube ignores all) → `Keywords:`. No chapters, summary, playlist link or question, matching the reference. The side-picking question lives in the pinned comment.
- **AI disclosure** appears in three places: description line 2, fixed on the right side panel, and YouTube's own flag `status.containsSyntheticMedia = true` set at upload. **That flag only takes effect on `videos.insert`, and `videos.list` never returns it** — reading it back always gives `None` even when it is on. Verify in Studio, never by read-back.

## Uploading

`upload.episodes_cli <metadata-index>` uploads the long video as `private` with `publishAt` = the story's `publish_date` at 20:00 (+07:00). **A date already in the past rolls forward** to the next 20:00 with a warning, instead of producing a past `publishAt`. Without a `publish_date`, `--first-air 2026-10-07T20:00` sets it — check it does not collide with an already-scheduled video. It adds the video to its topic playlist (`YOUTUBE_PLAYLIST_*` in `.env`, link or bare `PL…` id — a playlist *name* is rejected) and marks the story `published` with its `video_id`.

**Shorts are uploaded and scheduled together with the long video.** Pass `--shorts-prefix <prefix>` (stored as `shorts_prefix` in the metadata index; `run_daily.sh --upload` does it) and the 3 Shorts go up immediately as `private` with `publishAt` = the long video's publish time **+ 5 min**, titled `<story title> — Trích đoạn N/3` from the start. YouTube flips them public by itself — nothing has to be awake or authenticated on air night. The publish time is read from the long video's **saved upload state**, never recomputed (a hand-picked `--first-air` date would otherwise drift). If that time has already passed, Shorts go up public immediately (YouTube rejects a past `publishAt`). Re-running for a long video already uploaded skips it and only uploads the Shorts.

`launchd/com.lee.audiobook.shorts.plist` still runs `scripts.post_shorts` at **20:05 every night** as a safety net: for today's story it makes any already-uploaded Shorts public and fixes their titles, and uploads them if they were never uploaded. It refuses while the long video is still private — a Short pointing at a private video is a dead link exactly when Shorts get most views.

## Gotchas that have actually bitten

- **Quota resets at midnight Pacific (~14:00 Vietnam), not local midnight.** `videos.insert` = 1,600 regardless of size. The default limit is 10,000/day, **but on 05/10 about 21,000 units' worth of calls (1 long video + 12 Shorts + updates) went through in one Pacific day with no quota error** — this project's real limit is higher. Check Google Cloud Console → YouTube Data API v3 → Quotas before planning around 10,000. `series_cli` stops cleanly on `quotaExceeded` and saves progress, so a rerun the next day picks up where it stopped.
- **OAuth token dies every 7 days** (project in Testing mode). Symptom: `invalid_grant` in `output/daily/shorts.err.log` or the upload log. Fix: `uv run python -m upload.auth` — the browser consent is the operator's to click, never Claude's.
- **`run_daily.sh` runs on macOS `/bin/bash` 3.2.** Under `set -u`, expanding an empty array as `"${arr[@]}"` is an "unbound variable" error that kills the run. Use `${arr[@]+"${arr[@]}"}`. And never edit `run_daily.sh` while a run is executing it — bash reads the file as it goes.
- **Prologue "Mở đầu" (26/10, full format):** after all chapters, stage 1 asks (same conversation) for a 100–150-word flash-forward into the climax that stops before the payoff and ends with a bridge back to the start; it becomes chapter 1 (`scripts.models.PROLOGUE_HEADING`). With a prologue there is no audio cold open (`episodes/full.py`), QA exempts it from the 300-word floor, and cold open / Shorts / TikTok quote-matching skip it (`without_prologue`) — otherwise they match the retelling instead of the real climax. If the prologue fails twice it is skipped and the old cold open is used.
- **Claude counts Vietnamese compound words as one word** and overshot the 590–770 chapter limit (944) until the chapter prompt said to count by syllable ("con gái" = 2). Even so, Claude's dialogue-heavy prose (~39 paragraphs/chapter vs Gemini's ~11) reads at ~3.75 words/s, not 4.25: story #43 had 11,913 words and came out 53:47. `scripts/prompts.py words_per_second()` now picks the rate by `STORY_LLM`, so Claude is asked for 7,900–10,100 words (530–670/chapter) and QA's full-format floor scales with it. Measured on one story — re-measure after a few more. Stages 3/5/6 still use Gemini cookies even when stage 1 writes with Claude.
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
uv run python -m episodes.cli <script.json> <audio.json> [<images.json>]   # prints Manifest:
uv run python -m metadata.cli <script.json> --episodes <manifest.json>     # prints Danh sách:
uv run python -m shorts.cli <audio.json> [<images.json>] --script <script.json>
uv run python -m scripts.post_shorts --record <metadata-index.json> <shorts-prefix>
uv run python -m scripts.story_bank --mark-used <id>
```

Leave out `<images.json>` to render on background video. The input paths are in `output/daily/<date>/01-*.log` and `02-*.log` (`Đã lưu kịch bản:` / `Metadata:`), plus `03-*.log` when stage 3 ran.
