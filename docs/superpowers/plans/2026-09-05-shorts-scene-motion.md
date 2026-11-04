# Short dùng cảnh + chuyển động như video dài — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Short đổi ảnh đúng lúc cảnh đổi (một phần ~100s thường trải qua 2 cảnh) và mỗi cảnh có pan/zoom/crossfade như video dài, dùng lại `SceneBackground`.

**Architecture:** `shorts/props_builder.py` chọn mọi cảnh giao với khoảng thời gian của phần và **quy mốc về gốc phần** (vì audio của short đã bị cắt, `0` là lúc phần bắt đầu). `ShortProps` thêm `scenes: SceneProps[]`, giữ `imagePath` (= ảnh cảnh đầu) cho `ShortThumbnail`. `ShortVideo.tsx` thay `<Img>` zoom đơn bằng dãy `SceneBackground`, cảnh cuối kéo dài hết composition để nền không tắt lúc card CTA.

**Tech Stack:** Python 3.14 + pytest, Remotion 4.0.495 (`npm run typecheck`).

## Global Constraints

- Mọi thông báo, docstring, bình luận bằng tiếng Việt, đúng giọng văn hiện có.
- **Mốc cảnh trong props short quy về gốc phần** (khác video dài, nơi mốc giữ trục toàn tập) — vì `ShortVideo` so với `frame / fps` của composition đã cắt. Ghi rõ điều này trong comment ở cả hai phía.
- Cảnh đầu luôn có `startSeconds == 0.0`; cảnh cuối có `endSeconds == part.duration_seconds`.
- `imagePath` trong `ShortProps` giữ nguyên ý nghĩa: ảnh của cảnh đang chiếu lúc phần bắt đầu — `ShortThumbnail.tsx` không đổi.
- Không đụng `shorts/planner.py`, `shorts/cli.py`, `remotion/src/SceneBackground.tsx`, `remotion/src/MainVideo.tsx`, `remotion/src/ShortThumbnail.tsx`.
- Test không gọi Remotion thật. Kiểm chứng: `uv run pytest tests/ -q` xanh sạch, `cd remotion && npm run typecheck` sạch.

---

### Task 1: `shorts/props_builder.py` — mảng `scenes` quy về gốc phần

**Files:**
- Modify: `shorts/props_builder.py`
- Test: `tests/shorts/test_props_builder.py`

**Interfaces:**
- Consumes: metadata ảnh `chapters[].scenes[].{number,start_seconds,end_seconds,filename}` (đã sort); `ShortPart.source_start_seconds/source_end_seconds/duration_seconds`.
- Produces: props thêm khoá
  ```python
  "scenes": [{"number": int, "startSeconds": float, "endSeconds": float, "imagePath": str}]
  ```
  `imagePath` (khoá cũ) == `scenes[0]["imagePath"]`.

- [ ] **Step 1: Thêm test**

Fixture `_images_metadata()` hiện có: chương 1 cảnh 1 (0–50, `anh-1-1.png`), cảnh 2 (50–100, `anh-1-2.png`); chương 2 cảnh 1 (100–150, `anh-2-1.png`). `_setup_repo` đã tạo cả ba file. Thêm vào cuối file:

```python
def test_scenes_quy_ve_goc_phan_khi_phan_trai_qua_hai_canh(tmp_path):
    # Phần 30s-80s của chương 1 giao với cảnh 1 (0-50) và cảnh 2 (50-100).
    # Mốc quy về gốc phần: cảnh 1 chiếu 0-20, cảnh 2 chiếu 20-50.
    props = _build(
        tmp_path,
        part=_part(chapter_index=1, source_start_seconds=30.0, source_end_seconds=80.0),
    )

    assert props["scenes"] == [
        {"number": 1, "startSeconds": 0.0, "endSeconds": 20.0,
         "imagePath": "output/images/anh-1-1.png"},
        {"number": 2, "startSeconds": 20.0, "endSeconds": 50.0,
         "imagePath": "output/images/anh-1-2.png"},
    ]
    assert props["imagePath"] == "output/images/anh-1-1.png"


def test_scenes_mot_canh_phu_tron_phan(tmp_path):
    # Phần 110s-115.5s nằm gọn trong cảnh 1 chương 2 (100-150).
    props = _build(tmp_path)

    assert props["scenes"] == [
        {"number": 1, "startSeconds": 0.0, "endSeconds": 5.5,
         "imagePath": "output/images/anh-2-1.png"},
    ]


def test_scenes_khong_lay_canh_ket_thuc_dung_luc_phan_bat_dau(tmp_path):
    # Phần bắt đầu đúng giây 50 = lúc cảnh 1 kết thúc: chỉ lấy cảnh 2.
    props = _build(
        tmp_path,
        part=_part(chapter_index=1, source_start_seconds=50.0, source_end_seconds=60.0),
    )

    assert [s["number"] for s in props["scenes"]] == [2]
    assert props["imagePath"] == "output/images/anh-1-2.png"


def test_thieu_file_anh_cua_canh_thu_hai_thi_bao_loi(tmp_path):
    repo_root, images_dir, audio_path = _setup_repo(tmp_path)
    (images_dir / "anh-1-2.png").unlink()

    with pytest.raises(ShortPropsBuildError, match="anh-1-2.png"):
        build_short_props(
            part=_part(chapter_index=1, source_start_seconds=30.0, source_end_seconds=80.0),
            total_parts=5,
            episode_title=TITLE,
            trope=TROPE,
            images_metadata=_images_metadata(),
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=repo_root,
        )
```

- [ ] **Step 2: Chạy test, xác nhận đỏ**

Run: `uv run pytest tests/shorts/test_props_builder.py -q`
Expected: 4 test mới FAIL — `KeyError: 'scenes'`.

- [ ] **Step 3: Sửa `build_short_props`**

Thay đoạn từ comment `# Lấy cảnh đang chiếu lúc phần bắt đầu` đến hết khối `try: image_path_relative = ...` bằng:

```python
    # Lấy mọi cảnh giao với khoảng thời gian của phần. Planner không bao giờ cắt
    # phần qua ranh giới chương và các cảnh phủ kín chương, nên luôn có ít nhất
    # một cảnh. So "end > start phần" và "start < end phần" để cảnh vừa kết thúc
    # đúng lúc phần bắt đầu không bị lấy thừa.
    part_start = part.source_start_seconds
    part_end = part.source_end_seconds
    overlapping = [
        s for s in scenes
        if s["end_seconds"] > part_start and s["start_seconds"] < part_end
    ]
    if not overlapping:
        raise ShortPropsBuildError(
            f"Không có cảnh nào của chương {part.chapter_index} phủ khoảng "
            f"{part_start:.2f}-{part_end:.2f}s của phần {part.number}"
        )

    def _relative(filename: str) -> str:
        image_path = images_dir / filename
        if not image_path.exists():
            raise ShortPropsBuildError(f"Không tìm thấy file ảnh: {image_path}")
        try:
            return str(image_path.relative_to(repo_root))
        except ValueError as exc:
            raise ShortPropsBuildError(
                f"File ảnh {image_path} nằm ngoài repo ({repo_root}) -- "
                "images_dir phải là thư mục con của repo_root"
            ) from exc

    # Mốc QUY VỀ GỐC PHẦN, khác video dài (giữ trục toàn tập): audio của short
    # đã bị cắt nên ShortVideo.tsx so với thời gian của composition, bắt đầu từ 0.
    scene_props = [
        {
            "number": s["number"],
            "startSeconds": max(0.0, s["start_seconds"] - part_start),
            "endSeconds": min(part.duration_seconds, s["end_seconds"] - part_start),
            "imagePath": _relative(s["filename"]),
        }
        for s in overlapping
    ]
    # Ảnh bìa (ShortThumbnail) vẫn là cảnh đang chiếu lúc phần bắt đầu.
    image_path_relative = scene_props[0]["imagePath"]
```

Trong dict trả về, thêm ngay sau `"imagePath": image_path_relative,`:

```python
        "scenes": scene_props,
```

- [ ] **Step 4: Chạy test, xác nhận xanh**

Run: `uv run pytest tests/shorts/ -q`
Expected: tất cả pass (kể cả `test_file_anh_khong_ton_tai_thi_bao_loi` và `test_anh_ngoai_repo_root_...` — cùng thông báo cũ).

- [ ] **Step 5: Commit**

```bash
git add shorts/props_builder.py tests/shorts/test_props_builder.py
git commit -m "feat(shorts): props short mang mọi cảnh giao với phần, mốc quy về gốc phần"
```

---

### Task 2: Remotion — `ShortVideo` dựng cảnh bằng `SceneBackground`

**Files:**
- Modify: `remotion/src/types.ts` (`ShortProps`)
- Modify: `remotion/src/ShortVideo.tsx`
- Modify: `remotion/src/Root.tsx` (`defaultShortProps`)

**Interfaces:**
- Consumes: props Task 1; `SceneBackground` (`scene`, `startFrame`, `endFrame`, `crossfadeFrames`, `motionIndex`) — không đổi.

- [ ] **Step 1: `types.ts`** — thêm vào `ShortProps` ngay sau `imagePath: string;`:

```ts
  // Cảnh giao với phần, mốc QUY VỀ GỐC PHẦN (audio short đã cắt). Cảnh đầu
  // startSeconds = 0. Khác ChapterProps.scenes của video dài (trục toàn tập).
  scenes: SceneProps[];
```

- [ ] **Step 2: `Root.tsx`** — trong `defaultShortProps`, thêm `scenes: [],` sau `imagePath: "",`.

- [ ] **Step 3: `ShortVideo.tsx`**

Import: bỏ `Img` và `interpolate` khỏi import `remotion` (không còn dùng); thêm `import { SceneBackground } from "./SceneBackground";`.

Thêm hằng sau `FONT_FAMILY`:

```ts
// Dissolve giữa hai cảnh, cùng giá trị với MainVideo.tsx.
const CROSSFADE_SECONDS = 1.0;
```

Trong props destructuring thay `imagePath,` bằng `scenes,` (thumbnail dùng `imagePath`, video không).

Xoá khối `const zoom = interpolate(...)`. Thêm sau `const seconds = frame / fps;`:

```ts
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);
```

Thay khối:

```tsx
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img ... />
      </AbsoluteFill>
```

bằng:

```tsx
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {scenes.map((scene, i) => {
          const next = scenes[i + 1];
          // Cảnh cuối kéo dài hết composition: nền vẫn còn dưới card CTA thay
          // vì tắt đen đúng lúc audio hết. Mốc cảnh đã quy về gốc phần.
          const endFrame = next
            ? Math.round(next.startSeconds * fps)
            : durationInFrames;
          return (
            <SceneBackground
              key={scene.number}
              scene={scene}
              startFrame={Math.round(scene.startSeconds * fps)}
              endFrame={endFrame}
              crossfadeFrames={crossfadeFrames}
              motionIndex={i}
            />
          );
        })}
      </AbsoluteFill>
```

- [ ] **Step 4: Typecheck**

Run: `cd remotion && npm run typecheck`
Expected: sạch. Nếu báo `imagePath` không dùng trong `ShortVideo`: đúng — nó không còn được destructure ở đó.

- [ ] **Step 5: Test Python vẫn xanh, commit**

Run: `uv run pytest tests/ -q` (từ gốc repo).

```bash
git add remotion/src/types.ts remotion/src/ShortVideo.tsx remotion/src/Root.tsx
git commit -m "feat(remotion): short dựng từng cảnh bằng SceneBackground, cảnh cuối kéo qua card CTA"
```

---

### Task 3: Kiểm chứng trên tập thật (phiên chính tự chạy)

- [ ] Tìm một phần trải qua ranh giới cảnh của tập `chong_hien_mau_con` với metadata ảnh mới `output/images/chong_hien_mau_con-20260905T045011Z.json`: chạy `plan_parts` trên `output/audio/chong_hien_mau_con-20260904T015621Z.json`, chọn phần đầu tiên có ≥ 2 cảnh giao.
- [ ] Cắt wav của phần đó (`shorts.audio_cut.cut_wav`), dựng props bằng `build_short_props`, ghi props JSON, render **một** short: `npx remotion render src/index.ts ShortVideo <out.mp4> --props=<json> --public-dir=<repo_root>` trong `remotion/`.
- [ ] Trích khung 1s trước và 1s sau mốc đổi cảnh, kiểm không nháy tối, gửi người dùng clip.
- [ ] Ghi vào ledger. Không đăng gì lên YouTube.
