# Remotion Video Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the video-assembly stage of the audiobook pipeline: a Remotion (React/TypeScript) project that renders the final MP4 from script + TTS audio + background images, glued together by a new Python `video/` module.

**Architecture:** `video/props_builder.py` joins the script JSON, TTS metadata JSON, and images metadata JSON (by chapter index) into one `VideoProps` JSON that matches a TypeScript interface in `remotion/src/types.ts`. `video/cli.py` writes that JSON and invokes `npx remotion render` as a subprocess (cwd inside `remotion/`). The Remotion side is a self-contained Node/TypeScript project with one `MainVideo` composition assembled from `Avatar`, `ChapterBackground` (Ken Burns + crossfade), `Waveform` (real audio-amplitude sync), and `Caption` sub-components.

**Tech Stack:** Python 3.11 + `uv` (existing), Node.js v22 (confirmed present) + `npm`, Remotion 4.0.495 (`remotion`, `@remotion/cli`, `@remotion/media-utils`), React 18, TypeScript 5.

## Global Constraints

- Spec: [docs/superpowers/specs/2026-07-21-remotion-video-module-design.md](../specs/2026-07-21-remotion-video-module-design.md)
- Video: **1024×576**, **30fps**. `durationInFrames = round(chapters.at(-1).endSeconds * fps)`, computed dynamically via Remotion's `calculateMetadata` — no extra buffer.
- Crossfade between adjacent chapters' backgrounds: **0.5s**, matching the TTS module's `gap_seconds` (the silent gap already baked into the audio between chapters) — implemented so the fade window exactly coincides with that gap.
- Caption: **chapter-level timing only** (no forced alignment). Split each chapter's text into ~70-90-character chunks; distribute chunk display time across `[chapter.startSeconds, chapter.endSeconds]` proportional to each chunk's character length.
- Avatar/branding assets: **placeholder** at `remotion/public/avatar.png` (operator swaps in the real file later, no code change needed).
- **CORRECTED during Task 1** (the plan originally assumed this, verified false in practice): `npx remotion render` cannot mux audio/images from raw absolute filesystem paths or `file://` URLs — `@remotion/renderer`'s asset-download step requires `http://`/`https://` (confirmed against https://www.remotion.dev/docs/miscellaneous/absolute-paths and https://www.remotion.dev/docs/assets, and by tracing the failure into `@remotion/renderer`'s own source). The corrected mechanism: pass `--public-dir=<repo root>` to `npx remotion render` (Remotion serves that directory over its own ephemeral local HTTP server for the render's duration only — no server to manage, no files copied). Because `remotion/public/avatar.png` (versioned, lives with the Remotion project) and `output/audio/`, `output/images/` (gitignored, generated per run) share no common ancestor except the repo root, the repo root is the directory to point `--public-dir` at. Consequently:
  - `VideoProps.audioPath`/`ChapterProps.imagePath` are paths **relative to the repo root** (e.g. `"output/audio/demo-20260721T120000Z.wav"`, `"output/images/demo-chapter-1.png"`), read in components via `staticFile(...)` — never a raw `src={...}`.
  - The avatar reference changes accordingly: `staticFile("remotion/public/avatar.png")` (relative to repo root), not `staticFile("avatar.png")`.
  - `video/cli.py` adds `--public-dir=<repo root absolute path>` to the render command (alongside `--props=`), and `video/props_builder.py` computes both paths via `.relative_to(repo_root)`.
- `video/cli.py` invokes `npx remotion render src/index.ts MainVideo <output.mp4> --props=<props.json>` with `cwd` set to the `remotion/` directory.
- Success = `returncode == 0` **AND** the output `.mp4` file exists afterward — same no-op-guard discipline already used in `images/generator.py` for mflux.
- **No automated tests for the React/TypeScript side** this iteration (no JS test framework in this repo yet) — verify each Remotion task by actually running `npx remotion render` against small fixture inputs and inspecting the result (`ffprobe`, file size). The Python side (`video/props_builder.py`, `video/storage.py`, `video/cli.py`) follows the same TDD + mocked-`subprocess.run` pattern already used in `images/generator.py`.
- `VideoProps` field names are camelCase (`startSeconds`, `endSeconds`, `sampleRate`, `imagePath`, `audioPath`) even though the Python-side source JSONs use snake_case (`start_seconds`, `end_seconds`, `sample_rate`) — `props_builder.py` does this conversion.

---

### Task 1: Bootstrap the `remotion/` Node project with a minimal working composition

**Files:**
- Create: `remotion/package.json`
- Create: `remotion/tsconfig.json`
- Create: `remotion/remotion.config.ts`
- Create: `remotion/src/types.ts`
- Create: `remotion/src/MainVideo.tsx`
- Create: `remotion/src/index.ts`

**Interfaces:**
- Produces: `VideoProps`/`ChapterProps` TypeScript interfaces in `remotion/src/types.ts` (relied on by every later Remotion task and mirrored by `video/props_builder.py`'s output shape). Produces a registered Remotion composition named `"MainVideo"`, 1024×576, 30fps, with `calculateMetadata` computing `durationInFrames` from `props.chapters`.

- [ ] **Step 1: Create the project scaffold**

Create `remotion/package.json`:

```json
{
  "name": "audiobook-remotion",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "remotion": "4.0.495",
    "@remotion/cli": "4.0.495",
    "@remotion/media-utils": "4.0.495",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "@types/react": "^18.0.0",
    "@types/react-dom": "^18.0.0"
  }
}
```

Create `remotion/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2018",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

Create `remotion/remotion.config.ts`:

```typescript
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
```

- [ ] **Step 2: Install dependencies**

Run: `cd remotion && npm install`

Expected: completes without error, creates `remotion/node_modules/` and `remotion/package-lock.json`. If npm reports a peer-dependency conflict for `react`/`react-dom`, read the exact version range npm prints and narrow the caret range in `package.json` to match, then re-run `npm install`.

- [ ] **Step 3: Write `types.ts`**

Create `remotion/src/types.ts`:

```typescript
export interface ChapterProps {
  index: number;
  heading: string;
  text: string;
  startSeconds: number;
  endSeconds: number;
  imagePath: string;
}

export interface VideoProps {
  trope: string;
  title: string;
  audioPath: string;
  sampleRate: number;
  chapters: ChapterProps[];
}
```

- [ ] **Step 4: Write a minimal `MainVideo.tsx`**

Create `remotion/src/MainVideo.tsx` (this will grow in later tasks — for now it only proves audio + props flow through correctly):

```tsx
import React from "react";
import { AbsoluteFill, Audio, staticFile } from "remotion";
import type { VideoProps } from "./types";

export const MainVideo: React.FC<VideoProps> = ({ audioPath }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 5: Register the composition with dynamic duration**

Create `remotion/src/index.ts`:

```typescript
import React from "react";
import { Composition, registerRoot } from "remotion";
import { MainVideo } from "./MainVideo";
import type { VideoProps } from "./types";

const FPS = 30;
const WIDTH = 1024;
const HEIGHT = 576;

const calculateMetadata = async ({ props }: { props: VideoProps }) => {
  const lastChapter = props.chapters[props.chapters.length - 1];
  const durationInSeconds = lastChapter ? lastChapter.endSeconds : 0;
  return {
    durationInFrames: Math.max(1, Math.round(durationInSeconds * FPS)),
  };
};

const defaultProps: VideoProps = {
  trope: "",
  title: "",
  audioPath: "",
  sampleRate: 24000,
  chapters: [],
};

const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MainVideo"
      component={MainVideo}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      durationInFrames={1}
      calculateMetadata={calculateMetadata}
      defaultProps={defaultProps}
    />
  );
};

registerRoot(RemotionRoot);
```

- [ ] **Step 6: Type-check**

Run: `cd remotion && npm run typecheck`

Expected: exits 0, no type errors.

- [ ] **Step 7: Smoke-render with fixture inputs**

Create fixture files (outside the repo, in `/tmp`, so they never get committed):

```bash
python3 -c "
import wave, struct
with wave.open('/tmp/remotion-task1-audio.wav', 'w') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(24000)
    n_frames = 24000 * 4
    w.writeframes(struct.pack('<' + 'h' * n_frames, *([0] * n_frames)))
"
```

Create `/tmp/remotion-task1-props.json`. Since these fixtures live flat in `/tmp` (no repo involved yet), use `--public-dir=/tmp` for this standalone smoke test and paths relative to `/tmp` (just the filename); the real pipeline in later tasks points `--public-dir` at the repo root instead — see Global Constraints:

```json
{
  "trope": "demo",
  "title": "Demo",
  "audioPath": "remotion-task1-audio.wav",
  "sampleRate": 24000,
  "chapters": [
    { "index": 1, "heading": "Chuong 1", "text": "Noi dung demo.", "startSeconds": 0, "endSeconds": 4, "imagePath": "does-not-matter-yet.png" }
  ]
}
```

Run:

```bash
cd remotion
npx remotion render src/index.ts MainVideo /tmp/remotion-task1-output.mp4 --props=/tmp/remotion-task1-props.json --public-dir=/tmp
```

Expected: command exits 0, prints a "rendered" success message, `/tmp/remotion-task1-output.mp4` exists and is non-empty.

Verify duration matches the computed `durationInFrames` (4 seconds at 30fps):

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 /tmp/remotion-task1-output.mp4
```

Expected: prints a value close to `4.0` (within ~0.1s is fine — frame rounding).

- [ ] **Step 8: Commit**

```bash
git add remotion/package.json remotion/package-lock.json remotion/tsconfig.json remotion/remotion.config.ts remotion/src/types.ts remotion/src/MainVideo.tsx remotion/src/index.ts
git commit -m "feat: bootstrap Remotion project with dynamic-duration composition"
```

---

### Task 2: Avatar + Ken-Burns/crossfade background components

**Files:**
- Create: `remotion/public/avatar.png` (placeholder)
- Create: `remotion/src/Avatar.tsx`
- Create: `remotion/src/ChapterBackground.tsx`
- Modify: `remotion/src/MainVideo.tsx`

**Interfaces:**
- Consumes: `VideoProps`/`ChapterProps` from Task 1's `types.ts`.
- Produces: `Avatar` (no props, reads `remotion/public/avatar.png` via `staticFile()`), `ChapterBackground` component with props `{ chapter: ChapterProps; startFrame: number; endFrame: number; crossfadeFrames: number; panDirection: "in" | "out" }` — relied on by `MainVideo.tsx` in this task and unchanged by later tasks.

- [ ] **Step 1: Add the placeholder avatar asset**

```bash
mkdir -p remotion/public
python3 -c "
import base64
data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
open('remotion/public/avatar.png', 'wb').write(data)
"
```

Expected: `remotion/public/avatar.png` exists (a valid, if tiny, 1x1 transparent PNG placeholder — the operator will replace this file with real branding art later; no code change needed when they do).

- [ ] **Step 2: Write `Avatar.tsx`**

Create `remotion/src/Avatar.tsx`:

```tsx
import React from "react";
import { Img, staticFile } from "remotion";

export const Avatar: React.FC = () => {
  return (
    <div
      style={{
        position: "absolute",
        top: 24,
        left: 24,
        width: 96,
        height: 96,
        borderRadius: "50%",
        overflow: "hidden",
      }}
    >
      <Img
        src={staticFile("remotion/public/avatar.png")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </div>
  );
};
```

- [ ] **Step 3: Write `ChapterBackground.tsx`**

Create `remotion/src/ChapterBackground.tsx`:

```tsx
import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import type { ChapterProps } from "./types";

interface ChapterBackgroundProps {
  chapter: ChapterProps;
  startFrame: number;
  endFrame: number;
  crossfadeFrames: number;
  panDirection: "in" | "out";
}

export const ChapterBackground: React.FC<ChapterBackgroundProps> = ({
  chapter,
  startFrame,
  endFrame,
  crossfadeFrames,
  panDirection,
}) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(
    frame,
    [startFrame - crossfadeFrames, startFrame, endFrame, endFrame + crossfadeFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scale = interpolate(
    frame,
    [startFrame, endFrame],
    panDirection === "in" ? [1, 1.15] : [1.15, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <Img
        src={staticFile(chapter.imagePath)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
```

Note on the crossfade math: chapter *i*'s fade-out window is `[endFrame(i), endFrame(i) + crossfadeFrames]`. Because the TTS module inserts a `gap_seconds` silence between chapters, chapter *i+1*'s `startFrame` equals chapter *i*'s `endFrame` plus that same gap — so when `crossfadeFrames` is set to that gap's frame count, chapter *i*'s fade-out window and chapter *i+1*'s fade-in window (`[startFrame(i+1) - crossfadeFrames, startFrame(i+1)]`) are the *same* window. Both chapters render simultaneously during that window with complementary opacity ramps, producing a real crossfade dissolve. `MainVideo.tsx` (next step) is responsible for computing `crossfadeFrames` from the 0.5s constant and passing the same value to every chapter.

- [ ] **Step 4: Wire into `MainVideo.tsx`**

Replace the contents of `remotion/src/MainVideo.tsx`:

```tsx
import React from "react";
import { AbsoluteFill, Audio, staticFile, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { ChapterBackground } from "./ChapterBackground";

const CROSSFADE_SECONDS = 0.5;

export const MainVideo: React.FC<VideoProps> = ({ audioPath, chapters }) => {
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {chapters.map((chapter, i) => (
        <ChapterBackground
          key={chapter.index}
          chapter={chapter}
          startFrame={Math.round(chapter.startSeconds * fps)}
          endFrame={Math.round(chapter.endSeconds * fps)}
          crossfadeFrames={crossfadeFrames}
          panDirection={i % 2 === 0 ? "in" : "out"}
        />
      ))}
      <Avatar />
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 5: Type-check**

Run: `cd remotion && npm run typecheck`

Expected: exits 0, no type errors.

- [ ] **Step 6: Smoke-render with 2 dummy chapters (verifies crossfade + avatar don't crash)**

Reuse the placeholder PNG as both chapters' background image (content doesn't matter for a crash test):

```bash
python3 -c "
import base64
data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
open('/tmp/remotion-task2-bg.png', 'wb').write(data)
"
```

Create `/tmp/remotion-task2-props.json` (chapter 2 starts 0.5s after chapter 1 ends, matching `gap_seconds`). As in Task 1, paths are relative to `/tmp` since `--public-dir=/tmp` is used for this standalone fixture render:

```json
{
  "trope": "demo",
  "title": "Demo",
  "audioPath": "remotion-task1-audio.wav",
  "sampleRate": 24000,
  "chapters": [
    { "index": 1, "heading": "Chuong 1", "text": "Noi dung mot.", "startSeconds": 0, "endSeconds": 2, "imagePath": "remotion-task2-bg.png" },
    { "index": 2, "heading": "Chuong 2", "text": "Noi dung hai.", "startSeconds": 2.5, "endSeconds": 4, "imagePath": "remotion-task2-bg.png" }
  ]
}
```

Run:

```bash
cd remotion
npx remotion render src/index.ts MainVideo /tmp/remotion-task2-output.mp4 --props=/tmp/remotion-task2-props.json --public-dir=/tmp
```

Expected: exits 0, no runtime errors in the output, `/tmp/remotion-task2-output.mp4` exists and is non-empty.

- [ ] **Step 7: Commit**

```bash
git add remotion/public/avatar.png remotion/src/Avatar.tsx remotion/src/ChapterBackground.tsx remotion/src/MainVideo.tsx
git commit -m "feat: add avatar and Ken Burns/crossfade chapter backgrounds"
```

---

### Task 3: Waveform (real amplitude sync), chapter title, and caption

**Files:**
- Create: `remotion/src/Waveform.tsx`
- Create: `remotion/src/Caption.tsx`
- Modify: `remotion/src/MainVideo.tsx`

**Interfaces:**
- Consumes: `VideoProps`/`ChapterProps` from Task 1, `Avatar`/`ChapterBackground` from Task 2 (unchanged).
- Produces: `Waveform` component with props `{ audioPath: string }`, `Caption` component with props `{ chapters: ChapterProps[] }` — both self-contained, no other file depends on their internals.

- [ ] **Step 1: Write `Waveform.tsx`**

Create `remotion/src/Waveform.tsx`:

```tsx
import React from "react";
import { staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";

interface WaveformProps {
  audioPath: string;
}

const BAR_COUNT = 5;

export const Waveform: React.FC<WaveformProps> = ({ audioPath }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const audioData = useAudioData(staticFile(audioPath));

  if (!audioData) {
    return null;
  }

  const amplitudes = visualizeAudio({
    fps,
    frame,
    audioData,
    numberOfSamples: BAR_COUNT,
  });

  return (
    <div style={{ position: "absolute", top: 130, left: 24, display: "flex", gap: 4 }}>
      {amplitudes.map((amplitude, i) => (
        <div
          key={i}
          style={{
            width: 6,
            height: Math.max(4, amplitude * 40),
            backgroundColor: "#fff",
            borderRadius: 3,
          }}
        />
      ))}
    </div>
  );
};
```

- [ ] **Step 2: Write `Caption.tsx`**

Create `remotion/src/Caption.tsx`:

```tsx
import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { ChapterProps } from "./types";

interface CaptionProps {
  chapters: ChapterProps[];
}

const CHUNK_CHAR_BUDGET = 80;

function splitIntoChunks(text: string): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const chunks: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > CHUNK_CHAR_BUDGET && current) {
      chunks.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) {
    chunks.push(current);
  }
  return chunks;
}

export const Caption: React.FC<CaptionProps> = ({ chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;

  const chapter = chapters.find((c) => seconds >= c.startSeconds && seconds < c.endSeconds);
  if (!chapter) {
    return null;
  }

  const chunks = splitIntoChunks(chapter.text);
  const totalChars = chunks.reduce((sum, c) => sum + c.length, 0) || 1;
  const chapterDuration = chapter.endSeconds - chapter.startSeconds;

  let cursor = chapter.startSeconds;
  let activeChunk: string | null = null;
  for (const chunk of chunks) {
    const chunkDuration = (chunk.length / totalChars) * chapterDuration;
    if (seconds >= cursor && seconds < cursor + chunkDuration) {
      activeChunk = chunk;
      break;
    }
    cursor += chunkDuration;
  }

  if (!activeChunk) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        left: "10%",
        right: "10%",
        textAlign: "center",
        color: "#fff",
        fontSize: 28,
        padding: "8px 16px",
        backgroundColor: "rgba(0,0,0,0.55)",
        borderRadius: 12,
      }}
    >
      {activeChunk}
    </div>
  );
};
```

- [ ] **Step 3: Wire `Waveform`, chapter title, and `Caption` into `MainVideo.tsx`**

Replace the contents of `remotion/src/MainVideo.tsx`:

```tsx
import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { ChapterBackground } from "./ChapterBackground";
import { Waveform } from "./Waveform";
import { Caption } from "./Caption";

const CROSSFADE_SECONDS = 0.5;

export const MainVideo: React.FC<VideoProps> = ({ audioPath, chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);
  const seconds = frame / fps;

  const currentChapter = chapters.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {chapters.map((chapter, i) => (
        <ChapterBackground
          key={chapter.index}
          chapter={chapter}
          startFrame={Math.round(chapter.startSeconds * fps)}
          endFrame={Math.round(chapter.endSeconds * fps)}
          crossfadeFrames={crossfadeFrames}
          panDirection={i % 2 === 0 ? "in" : "out"}
        />
      ))}
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

- [ ] **Step 4: Type-check**

Run: `cd remotion && npm run typecheck`

Expected: exits 0, no type errors.

- [ ] **Step 5: Smoke-render (verifies Waveform's real audio-data read + Caption don't crash)**

Reuse `/tmp/remotion-task2-props.json` from Task 2 (already has 2 chapters with real `text`):

```bash
cd remotion
npx remotion render src/index.ts MainVideo /tmp/remotion-task3-output.mp4 --props=/tmp/remotion-task2-props.json --public-dir=/tmp
```

Expected: exits 0, no runtime errors (this is the first render that actually decodes `/tmp/remotion-task1-audio.wav` for the waveform — a crash here would most likely mean `useAudioData` couldn't read the fixture file), `/tmp/remotion-task3-output.mp4` exists and is non-empty.

- [ ] **Step 6: Commit**

```bash
git add remotion/src/Waveform.tsx remotion/src/Caption.tsx remotion/src/MainVideo.tsx
git commit -m "feat: add amplitude-synced waveform, chapter title, and captions"
```

---

### Task 4: `video/props_builder.py` — join script + TTS + images metadata

**Files:**
- Create: `video/__init__.py`
- Create: `video/props_builder.py`
- Test: `tests/video/__init__.py`
- Test: `tests/video/test_props_builder.py`

**Interfaces:**
- Consumes: `scripts.models.Script`/`Chapter` (existing dataclasses: `Script.trope: str`, `Script.title: str`, `Script.chapters: list[Chapter]`; `Chapter.index: int`, `Chapter.heading: str`, `Chapter.text: str`).
- Produces: `build_video_props(script: Script, tts_metadata: dict, images_metadata: dict, audio_path: Path, images_dir: Path, repo_root: Path) -> dict` and `PropsBuildError(Exception)` — relied on by Task 6's `video/cli.py`. **Note:** `audioPath`/`imagePath` in the returned dict are paths **relative to `repo_root`** (a Global Constraint corrected after Task 1's finding that Remotion can't consume raw absolute paths) — `repo_root` must be an ancestor of both `audio_path` and `images_dir` or `Path.relative_to()` raises `ValueError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/video/__init__.py` (empty file).

Create `tests/video/test_props_builder.py`:

```python
from pathlib import Path

import pytest

from scripts.models import Chapter, Script
from video.props_builder import PropsBuildError, build_video_props


def _make_script():
    return Script(
        trope="demo",
        title="Tieu de demo",
        chapters=[
            Chapter(index=1, heading="Chuong 1", text="Noi dung mot."),
            Chapter(index=2, heading="Chuong 2", text="Noi dung hai."),
        ],
    )


def test_build_video_props_joins_all_sources():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0},
            {"index": 2, "heading": "Chuong 2", "start_seconds": 2.5, "end_seconds": 4.5},
        ],
    }
    images_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "chapters": [
            {"index": 1, "filename": "demo-chapter-1.png", "scene_description": "a"},
            {"index": 2, "filename": "demo-chapter-2.png", "scene_description": "b"},
        ],
    }

    repo_root = Path("/repo")
    props = build_video_props(
        script,
        tts_metadata,
        images_metadata,
        audio_path=Path("/repo/output/audio/demo.wav"),
        images_dir=Path("/repo/output/images"),
        repo_root=repo_root,
    )

    assert props["trope"] == "demo"
    assert props["title"] == "Tieu de demo"
    assert props["audioPath"] == str(Path("output/audio/demo.wav"))
    assert props["sampleRate"] == 24000
    assert len(props["chapters"]) == 2
    assert props["chapters"][0] == {
        "index": 1,
        "heading": "Chuong 1",
        "text": "Noi dung mot.",
        "startSeconds": 0.0,
        "endSeconds": 2.0,
        "imagePath": str(Path("output/images/demo-chapter-1.png")),
    }
    assert props["chapters"][1]["imagePath"] == str(Path("output/images/demo-chapter-2.png"))


def test_build_video_props_raises_on_title_mismatch():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "TIEU DE KHAC",
        "sample_rate": 24000,
        "chapters": [],
    }
    images_metadata = {"trope": "demo", "title": "Tieu de demo", "chapters": []}

    with pytest.raises(PropsBuildError, match="trope/title"):
        build_video_props(
            script,
            tts_metadata,
            images_metadata,
            audio_path=Path("/repo/a.wav"),
            images_dir=Path("/repo/images"),
            repo_root=Path("/repo"),
        )


def test_build_video_props_raises_on_missing_chapter():
    script = _make_script()
    tts_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "sample_rate": 24000,
        "chapters": [
            {"index": 1, "heading": "Chuong 1", "start_seconds": 0.0, "end_seconds": 2.0}
        ],
    }
    images_metadata = {
        "trope": "demo",
        "title": "Tieu de demo",
        "chapters": [
            {"index": 1, "filename": "a.png", "scene_description": "a"},
            {"index": 2, "filename": "b.png", "scene_description": "b"},
        ],
    }

    with pytest.raises(PropsBuildError, match="Thiếu chương"):
        build_video_props(
            script,
            tts_metadata,
            images_metadata,
            audio_path=Path("/repo/a.wav"),
            images_dir=Path("/repo/images"),
            repo_root=Path("/repo"),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/video/test_props_builder.py -v`

Expected: FAIL — collection error, since `video/props_builder.py` and `video/__init__.py` don't exist yet.

- [ ] **Step 3: Write the implementation**

Create `video/__init__.py` (empty file).

Create `video/props_builder.py`:

```python
# video/props_builder.py
from pathlib import Path

from scripts.models import Script


class PropsBuildError(Exception):
    pass


def build_video_props(
    script: Script,
    tts_metadata: dict,
    images_metadata: dict,
    audio_path: Path,
    images_dir: Path,
    repo_root: Path,
) -> dict:
    for source_name, source in (("tts", tts_metadata), ("images", images_metadata)):
        if source["trope"] != script.trope or source["title"] != script.title:
            raise PropsBuildError(
                f"trope/title của {source_name}_metadata không khớp với script "
                f"(script: {script.trope!r}/{script.title!r}, "
                f"{source_name}: {source['trope']!r}/{source['title']!r})"
            )

    script_indices = {c.index for c in script.chapters}
    tts_by_index = {c["index"]: c for c in tts_metadata["chapters"]}
    images_by_index = {c["index"]: c for c in images_metadata["chapters"]}

    missing_in_tts = script_indices - tts_by_index.keys()
    missing_in_images = script_indices - images_by_index.keys()
    if missing_in_tts or missing_in_images:
        raise PropsBuildError(
            f"Thiếu chương trong dữ liệu đầu vào — thiếu trong TTS: "
            f"{sorted(missing_in_tts)}, thiếu trong images: {sorted(missing_in_images)}"
        )

    chapters = []
    for chapter in script.chapters:
        tts_chapter = tts_by_index[chapter.index]
        image_chapter = images_by_index[chapter.index]
        chapters.append(
            {
                "index": chapter.index,
                "heading": chapter.heading,
                "text": chapter.text,
                "startSeconds": tts_chapter["start_seconds"],
                "endSeconds": tts_chapter["end_seconds"],
                "imagePath": str((images_dir / image_chapter["filename"]).relative_to(repo_root)),
            }
        )

    return {
        "trope": script.trope,
        "title": script.title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "sampleRate": tts_metadata["sample_rate"],
        "chapters": chapters,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/video/test_props_builder.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add video/__init__.py video/props_builder.py tests/video/__init__.py tests/video/test_props_builder.py
git commit -m "feat: join script/TTS/images metadata into VideoProps"
```

---

### Task 5: `video/storage.py` — persist the props JSON

**Files:**
- Create: `video/storage.py`
- Test: `tests/video/test_storage.py`

**Interfaces:**
- Consumes: the `dict` shape produced by `build_video_props` from Task 4 (must contain at minimum a `"trope"` key, used for the output filename).
- Produces: `save_video_props(video_props: dict, output_dir: Path) -> Path` — relied on by Task 6's `video/cli.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/video/test_storage.py`:

```python
import json

from video.storage import save_video_props


def test_save_video_props_writes_json(tmp_path):
    video_props = {
        "trope": "demo",
        "title": "T",
        "audioPath": "/a.wav",
        "sampleRate": 24000,
        "chapters": [],
    }

    props_path = save_video_props(video_props, tmp_path)

    assert props_path.exists()
    assert props_path.suffix == ".json"
    assert "demo" in props_path.name
    data = json.loads(props_path.read_text(encoding="utf-8"))
    assert data == video_props


def test_save_video_props_creates_output_dir_if_missing(tmp_path):
    missing_dir = tmp_path / "nested" / "output"
    video_props = {
        "trope": "t",
        "title": "T",
        "audioPath": "/a.wav",
        "sampleRate": 24000,
        "chapters": [],
    }

    props_path = save_video_props(video_props, missing_dir)

    assert props_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/video/test_storage.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'video.storage'`.

- [ ] **Step 3: Write the implementation**

Create `video/storage.py`:

```python
# video/storage.py
import json
from datetime import datetime, timezone
from pathlib import Path


def save_video_props(video_props: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    props_path = output_dir / f"{video_props['trope']}-{timestamp}.json"
    props_path.write_text(
        json.dumps(video_props, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return props_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/video/test_storage.py -v`

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add video/storage.py tests/video/test_storage.py
git commit -m "feat: persist VideoProps JSON to output/video/"
```

---

### Task 6: `video/cli.py` — orchestrate the render

**Files:**
- Create: `video/cli.py`
- Test: `tests/video/test_cli.py`

**Interfaces:**
- Consumes: `scripts.models.Script.from_dict(dict) -> Script` (existing), `build_video_props(script, tts_metadata, images_metadata, audio_path, images_dir, repo_root) -> dict` and `PropsBuildError` from Task 4 (note the `repo_root` parameter — Task 4's output paths are relative to it), `save_video_props(video_props: dict, output_dir: Path) -> Path` from Task 5.
- Produces: `video.cli._run(script_path: Path, tts_metadata_path: Path, images_metadata_path: Path) -> Path` (returns the rendered `.mp4` path), `video.cli.main() -> None`, `video.cli.VideoRenderError(Exception)`, module-level constants `video.cli.REPO_ROOT: Path`, `video.cli.REMOTION_DIR: Path` and `video.cli.OUTPUT_DIR: Path`. The render command passes `--public-dir=<REPO_ROOT>` (Global Constraints — corrected after Task 1's finding) in addition to `--props=<file>`.

- [ ] **Step 1: Write the failing tests**

Create `tests/video/test_cli.py`:

```python
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from video import cli


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    script_path = tmp_path / "script.json"
    _write_json(
        script_path,
        {
            "trope": "demo",
            "title": "T",
            "chapters": [{"index": 1, "heading": "C1", "text": "Noi dung"}],
        },
    )

    tts_metadata_path = tmp_path / "tts.json"
    _write_json(
        tts_metadata_path,
        {
            "trope": "demo",
            "title": "T",
            "sample_rate": 24000,
            "chapters": [
                {"index": 1, "heading": "C1", "start_seconds": 0.0, "end_seconds": 2.0}
            ],
        },
    )
    (tmp_path / "tts.wav").write_bytes(b"fake wav")

    images_metadata_path = tmp_path / "images.json"
    _write_json(
        images_metadata_path,
        {
            "trope": "demo",
            "title": "T",
            "chapters": [
                {"index": 1, "filename": "demo-chapter-1.png", "scene_description": "a"}
            ],
        },
    )

    return script_path, tts_metadata_path, images_metadata_path


def test_run_builds_props_and_renders_video(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    # REPO_ROOT must be an ancestor of the fixture files for build_video_props'
    # Path.relative_to() to succeed — tmp_path stands in for the repo root here.
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    script_path, tts_metadata_path, images_metadata_path = _write_fixture_inputs(tmp_path)

    def fake_run(cmd, **kwargs):
        output_path = Path(cmd[5])
        output_path.write_bytes(b"fake mp4")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("video.cli.subprocess.run", side_effect=fake_run) as mock_run:
        result_path = cli._run(script_path, tts_metadata_path, images_metadata_path)

    assert result_path.exists()
    assert result_path.suffix == ".mp4"

    cmd = mock_run.call_args.args[0]
    kwargs = mock_run.call_args.kwargs
    assert kwargs["cwd"] == cli.REMOTION_DIR
    assert cmd[:5] == ["npx", "remotion", "render", "src/index.ts", "MainVideo"]
    assert cmd[5] == str(result_path)
    assert cmd[6].startswith("--props=")
    assert cmd[7] == f"--public-dir={tmp_path}"

    # audio/image paths are relative to REPO_ROOT (tmp_path here), not absolute
    props_path = Path(cmd[6].removeprefix("--props="))
    saved_props = json.loads(props_path.read_text(encoding="utf-8"))
    assert saved_props["audioPath"] == "tts.wav"
    assert saved_props["chapters"][0]["imagePath"] == "demo-chapter-1.png"


def test_run_raises_on_render_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    script_path, tts_metadata_path, images_metadata_path = _write_fixture_inputs(tmp_path)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="render failed")

    with patch("video.cli.subprocess.run", side_effect=fake_run):
        with pytest.raises(cli.VideoRenderError, match="render failed"):
            cli._run(script_path, tts_metadata_path, images_metadata_path)


def test_run_raises_when_output_file_missing_despite_success_code(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    script_path, tts_metadata_path, images_metadata_path = _write_fixture_inputs(tmp_path)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("video.cli.subprocess.run", side_effect=fake_run):
        with pytest.raises(cli.VideoRenderError):
            cli._run(script_path, tts_metadata_path, images_metadata_path)


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []

    def fake_run(script_path, tts_metadata_path, images_metadata_path):
        calls.append((script_path, tts_metadata_path, images_metadata_path))
        return Path("/fake/output.mp4")

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(
        "sys.argv", ["cli.py", "script.json", "tts.json", "images.json"]
    )

    cli.main()

    assert calls == [(Path("script.json"), Path("tts.json"), Path("images.json"))]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/video/test_cli.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'video.cli'`.

- [ ] **Step 3: Write the implementation**

Create `video/cli.py`:

```python
# video/cli.py
import argparse
import json
import subprocess
from pathlib import Path

from scripts.models import Script
from video.props_builder import build_video_props
from video.storage import save_video_props

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "video"


class VideoRenderError(Exception):
    pass


def _run(
    script_path: Path, tts_metadata_path: Path, images_metadata_path: Path
) -> Path:
    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))
    images_metadata = json.loads(images_metadata_path.read_text(encoding="utf-8"))

    audio_path = tts_metadata_path.with_suffix(".wav")
    images_dir = images_metadata_path.parent

    video_props = build_video_props(
        script,
        tts_metadata,
        images_metadata,
        audio_path=audio_path,
        images_dir=images_dir,
        repo_root=REPO_ROOT,
    )
    props_path = save_video_props(video_props, OUTPUT_DIR)

    output_path = OUTPUT_DIR / f"{props_path.stem}.mp4"

    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        "MainVideo",
        str(output_path),
        f"--props={props_path}",
        f"--public-dir={REPO_ROOT}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REMOTION_DIR)

    if result.returncode != 0 or not output_path.exists():
        raise VideoRenderError(
            f"Lỗi khi render video bằng Remotion: {result.stderr or result.stdout}"
        )

    print(f"Đã render video vào {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dựng video hoàn chỉnh bằng Remotion."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("tts_metadata_path", help="Đường dẫn file JSON metadata TTS")
    parser.add_argument(
        "images_metadata_path", help="Đường dẫn file JSON metadata ảnh"
    )
    args = parser.parse_args()
    _run(
        Path(args.script_path),
        Path(args.tts_metadata_path),
        Path(args.images_metadata_path),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/video/test_cli.py -v`

Expected: 4 passed

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -q`

Expected: all tests pass (existing `scripts`/`tts`/`images` tests plus the new `video` tests), pristine output.

- [ ] **Step 6: Commit**

```bash
git add video/cli.py tests/video/test_cli.py
git commit -m "feat: add video CLI orchestrating props build + Remotion render"
```

---

### Task 7: Manual smoke test (not automated)

**Files:** none (verification only, no code changes)

**Interfaces:** none — this task only exercises the public entry point `python -m video.cli <script.json> <tts_metadata.json> <images_metadata.json>` built by Tasks 1-6.

- [ ] **Step 1: Confirm real outputs from the earlier pipeline stages are available**

```bash
ls output/scripts/*.json output/audio/*.json output/audio/*.wav output/images/*.json 2>/dev/null
```

If any of these are missing, run the corresponding module first (`scripts/cli.py`, `tts/cli.py`, `images/cli.py`) with real credentials configured in `.env`, or ask the user for a matching set of sample files (all three must come from the same script run, so chapter indices/trope/title line up).

- [ ] **Step 2: Run the video CLI for real**

```bash
uv run python -m video.cli output/scripts/<pick-one>.json output/audio/<matching>.json output/images/<matching>.json
```

Expected: no crash. Prints `Đã render video vào output/video/<trope>-<timestamp>.mp4`. First run may take longer if Remotion needs to download/launch its headless Chromium.

- [ ] **Step 3: Review the rendered video**

Open the resulting MP4 and confirm:
- Avatar and waveform are positioned correctly and the waveform visibly reacts to the audio
- Ken Burns pan is smooth, not jarring
- Background image crossfades cleanly between chapters, timed with the audio's silent gaps
- Chapter title updates at the right times
- Captions appear roughly in sync with the chapter being read and don't overflow the frame
- Audio is not cut off or misaligned relative to the visuals

- [ ] **Step 4: Replace the placeholder avatar (optional, once real branding art exists)**

Once real branding art is ready, drop it in at `remotion/public/avatar.png` (same filename) — no code changes needed.
