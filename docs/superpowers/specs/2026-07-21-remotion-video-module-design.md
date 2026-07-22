# Thiết kế module dựng video (Remotion)

**Ngày**: 2026-07-21
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Sub-project thứ 4 của pipeline kênh YouTube truyện audio ([docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md](2026-07-21-youtube-audiobook-channel-design.md)), tiếp theo 3 module đã hoàn thành: sinh kịch bản (`scripts/`), lồng tiếng (`tts/`), sinh ảnh nền (`images/`, hiện dùng mflux local — [2026-07-21-images-mflux-migration-design.md](2026-07-21-images-mflux-migration-design.md)).

Module này nhận đầu ra của 3 module trước — file JSON kịch bản gốc, file `.wav` + JSON timestamp chương từ TTS, và 8 file `.png` + JSON metadata từ module ảnh — và **dựng ra 1 file video MP4 hoàn chỉnh** theo đúng template hình ảnh đã duyệt ở spec kênh (avatar tròn, icon waveform, tiêu đề chương, ảnh nền Ken Burns, caption cháy nền), sẵn sàng cho bước sinh metadata + upload YouTube ở sub-project sau.

Công nghệ dựng video: **Remotion** (React/TypeScript, license miễn phí cho cá nhân/nhóm ≤3 người kể cả dùng thương mại, theo mục 4 spec kênh), gọi qua CLI (`npx remotion render`) như một subprocess từ script orchestration Python — đúng cấu trúc thư mục "lai Python + Node/TypeScript" đã chốt ở spec kênh.

Đây là dự án lai 2 ngôn ngữ đầu tiên trong pipeline: `remotion/` là một dự án Node/TypeScript độc lập (npm, không dùng `uv`), `video/` là module Python mới cùng cấp `scripts/`/`tts/`/`images/`, đóng vai trò gộp dữ liệu và gọi Remotion CLI.

## 1. Quyết định thiết kế

- **Cách đưa dữ liệu vào Remotion**: Python gộp 3 nguồn JSON (script, TTS metadata, images metadata) thành **1 file props JSON duy nhất** (`video/props_builder.py`), rồi gọi `npx remotion render ... --props=<file>`. Khớp đúng pattern đã dùng cho 3 module trước (Python sinh 1 JSON + asset ở mỗi bước) — không tách render theo từng chương rồi ghép bằng ffmpeg (thêm phức tạp không cần thiết vì không có yêu cầu re-render từng phần), và không để Remotion tự đọc/ghép 3 file JSON lúc render (sẽ tách logic nghiệp vụ — chương nào khớp ảnh nào — sang phía TypeScript thay vì giữ ở Python nơi toàn bộ orchestration còn lại đang sống).
- **Caption**: chỉ dùng timing theo **chương** (đã có sẵn `start_seconds`/`end_seconds` từ TTS module) — chia text mỗi chương thành các cụm ~70-90 ký tự (ước lượng 2 dòng), phân bổ thời lượng hiển thị theo tỷ lệ độ dài ký tự trong khoảng thời gian của chương. Không dùng forced-alignment word-level (thêm hẳn dependency ASR tiếng Việt, tăng đáng kể phạm vi module) — chấp nhận caption không khớp chính xác từng từ nói ra ở lần lặp này.
- **Waveform icon**: đồng bộ thật với amplitude audio, dùng `@remotion/media-utils` (`useAudioData` + `visualizeAudio`) đọc trực tiếp từ file `.wav` — không phải animation giả lập hay ảnh tĩnh.
- **Asset thương hiệu (avatar, waveform icon tĩnh nếu cần)**: chưa có file thật — dùng **placeholder** đặt tại `remotion/public/avatar.png` (đường dẫn cố định), người vận hành thay file thật vào đúng vị trí này sau, không cần sửa code.
- **Độ phân giải video**: **1024×576**, khớp đúng độ phân giải ảnh nền hiện có (không upscale — tránh mờ/artifact khi Ken Burns zoom sâu, render nhanh hơn). Vẫn là tỷ lệ 16:9 chuẩn YouTube.
- **Frame rate**: 30fps (mặc định Remotion, chuẩn phổ biến cho YouTube).
- **Thời lượng video**: tính động qua `calculateMetadata` của Remotion — `durationInFrames = chapters.at(-1).endSeconds * fps`, không cộng buffer (audio module đã kết thúc audio đúng tại mốc đó).
- **Đường dẫn asset trong props**: ban đầu định dùng đường dẫn tuyệt đối trực tiếp cho `<Audio src>`/`<Img src>`, nhưng **xác nhận thực tế qua Task 1 của kế hoạch triển khai** rằng `npx remotion render` **không** hỗ trợ path tuyệt đối hay `file://` khi mux audio/ảnh vào MP4 — bước tải asset của `@remotion/renderer` yêu cầu bắt buộc URL `http://`/`https://` (xác nhận qua docs chính thức: remotion.dev/docs/miscellaneous/absolute-paths, remotion.dev/docs/assets). Quyết định cập nhật: dùng **flag `--public-dir` của Remotion CLI**, trỏ vào **thư mục gốc của repo** (không phải chỉ `output/`) — vì `remotion/public/avatar.png` (asset tĩnh, versioned) và `output/audio|images/` (asset sinh động, gitignored) không có thư mục cha chung nào khác ngoài gốc repo, và một lệnh render chỉ nhận 1 `--public-dir`. Theo đó: `VideoProps.audioPath`/`imagePath` là **đường dẫn tương đối so với gốc repo** (ví dụ `"output/audio/demo-20260721T120000Z.wav"`, `"output/images/demo-chapter-1.png"`), đọc qua `staticFile(props.audioPath)`/`staticFile(chapter.imagePath)` thay vì gán thẳng `src`; avatar đổi từ `staticFile("avatar.png")` thành `staticFile("remotion/public/avatar.png")` (cũng tương đối so với gốc repo). Remotion tự phục vụ thư mục này qua HTTP nội bộ khi render (chỉ tồn tại trong lúc render, không phải server thường trực) — không cần dựng/quản lý server riêng, không cần copy file.
- **Chuyển cảnh giữa chương**: crossfade 0.5s giữa 2 ảnh nền chương liền kề — khớp đúng `gap_seconds` (khoảng lặng 0.5s) đã có trong audio, để hình ảnh và âm thanh chuyển cảnh cùng nhịp.
- **Không viết automated test cho code React/TypeScript** ở lần lặp này — repo hiện chưa có hạ tầng test JS/TS (Jest/Vitest), và dựng hạ tầng đó là công sức đáng kể so với lợi ích ở giai đoạn đầu. Bù lại bằng smoke test thủ công chạy CLI thật.

## 2. Kiến trúc

```
remotion/                    # dự án Node/TS riêng (npm, KHÔNG dùng uv/Python)
├── package.json
├── remotion.config.ts
├── public/
│   └── avatar.png            # placeholder tròn, thay file thật sau
└── src/
    ├── index.ts               # registerRoot
    ├── MainVideo.tsx            # Composition, calculateMetadata tính durationInFrames động
    ├── Avatar.tsx
    ├── Waveform.tsx              # @remotion/media-utils đọc amplitude thật từ audio
    ├── ChapterBackground.tsx      # ảnh nền + Ken Burns pan/zoom + crossfade
    ├── Caption.tsx                # caption cháy nền, chia theo chương
    └── types.ts                   # kiểu VideoProps khớp props_builder.py sinh ra

video/                        # module Python mới, cùng cấp scripts/tts/images
├── __init__.py
├── props_builder.py           # gộp script + tts + images JSON -> 1 VideoProps JSON
├── storage.py                   # lưu props JSON vào output/video/
└── cli.py                        # nhận 3 đường dẫn JSON, gọi npx remotion render
```

**Luồng xử lý:**

```
[script.json] + [audio.wav + audio.json] + [images/*.png + images.json]
   (input: 3 đường dẫn do người vận hành cung cấp)
   → 1. props_builder.py: đọc cả 3 file, join theo chapter index
        - Chuyển field snake_case của JSON Python (sample_rate, start_seconds,
          end_seconds) sang camelCase khớp interface TypeScript (sampleRate,
          startSeconds, endSeconds)
        - Chuyển audioPath/imagePath thành đường dẫn TƯƠNG ĐỐI so với GỐC REPO
          (không phải tuyệt đối — xem mục "Quyết định thiết kế")
        - Báo lỗi rõ ràng nếu thiếu chương ở bất kỳ nguồn nào
        - Báo lỗi rõ ràng nếu trope/title không khớp giữa 3 file
        → dict VideoProps (trope, title, audioPath, sampleRate, chapters[])
   → 2. storage.py: lưu VideoProps thành file JSON vào output/video/
   → 3. cli.py: gọi subprocess (cwd=remotion/ để tìm đúng node_modules/package.json)
        npx remotion render src/index.ts MainVideo <output.mp4>
          --props=<props.json> --public-dir=<đường dẫn tuyệt đối tới gốc repo>
   → 4. Coi thành công khi returncode == 0 VÀ file .mp4 tồn tại sau khi chạy
        (không chỉ dựa vào returncode — cùng nguyên tắc đã áp dụng ở module ảnh mflux)
   → 5. Lỗi → raise VideoRenderError kèm stderr/stdout
```

**Data contract (`VideoProps`, khớp `remotion/src/types.ts`):**

```typescript
interface ChapterProps {
  index: number;
  heading: string;
  text: string;
  startSeconds: number;
  endSeconds: number;
  imagePath: string;   // đường dẫn tương đối so với gốc repo (dùng qua staticFile())
}
interface VideoProps {
  trope: string;
  title: string;
  audioPath: string;    // đường dẫn tương đối so với gốc repo (dùng qua staticFile())
  sampleRate: number;
  chapters: ChapterProps[];
}
```

**Hành vi từng component Remotion:**

- `MainVideo.tsx`: root composition, 1024×576, 30fps, `calculateMetadata` tính `durationInFrames` động từ chương cuối.
- `ChapterBackground.tsx`: mỗi chương hiện ảnh nền full-khung trong đúng `[startSeconds, endSeconds]` (đọc qua `staticFile(chapter.imagePath)`), Ken Burns bằng `interpolate` trên scale/translate (đổi hướng pan xen kẽ theo chỉ số chương), crossfade 0.5s giữa 2 chương liền kề.
- `Avatar.tsx`: ảnh tròn cố định từ `remotion/public/avatar.png`, hiển thị xuyên suốt video.
- `Waveform.tsx`: vài thanh nhảy theo amplitude thật, đọc qua `@remotion/media-utils` từ `staticFile(audioPath)`.
- Tiêu đề chương: chữ nghiêng dưới waveform, đổi theo `heading` của chương hiện tại (cắt cảnh đơn giản khi đổi chương).
- `Caption.tsx`: chia `text` mỗi chương thành cụm ~70-90 ký tự, phân bổ thời lượng hiển thị theo tỷ lệ độ dài ký tự trong `[startSeconds, endSeconds]` của chương, hiển thị dạng chữ trắng trên nền pill bán trong suốt, căn giữa.

## 3. Testing & vận hành

- **`props_builder.py`**: hàm Python thuần, test đầy đủ bằng dict giả — verify join đúng theo `index`, verify raise lỗi khi thiếu chương ở 1 nguồn hoặc `trope`/`title` lệch nhau giữa 3 file.
- **`video/cli.py`**: test bằng mock `subprocess.run` (cùng pattern đã dùng ở `images/generator.py`) — không gọi Remotion thật trong test tự động. Verify tham số CLI truyền đúng, verify raise `VideoRenderError` khi `returncode != 0` hoặc file `.mp4` không tồn tại sau khi chạy.
- **Không có automated test cho `remotion/src/*.tsx`** — xem mục "Quyết định thiết kế".
- **Smoke test thủ công** (cuối kế hoạch triển khai, không tự động hoá): chạy `video/cli.py` thật với 1 bộ script+tts+images JSON đã có sẵn từ các module trước, xem video MP4 render ra để xác nhận: avatar/waveform đúng vị trí và đồng bộ amplitude, Ken Burns mượt không giật, caption hiển thị đúng theo chương và không tràn khung, audio không bị lệch/cắt so với hình.

## 4. Dependencies

- `remotion/package.json`: `remotion`, `@remotion/cli`, `@remotion/media-utils`, `react`, `react-dom`, `typescript` — bootstrap qua `npm create video@latest` hoặc scaffold thủ công tối thiểu.
- Module Python `video/`: không cần thêm dependency ngoài thư viện chuẩn (`json`, `subprocess`, `pathlib`) — không giống các module trước, module này không gọi API bên ngoài nào.

## 5. Rủi ro & lưu ý

- **Node.js đã có sẵn trên máy vận hành** (xác nhận v22.21.1) — không cần cài thêm runtime, chỉ cần `npm install` trong `remotion/`.
- **Render Remotion cần Chromium headless** (Remotion tự tải/quản lý qua Puppeteer khi cần) — lần chạy đầu có thể mất thêm thời gian tải Chromium, tương tự việc tải model lần đầu ở các module trước.
- **Caption không khớp chính xác từng từ nói ra** (do chỉ dùng timing theo chương) — chấp nhận đánh đổi này ở lần lặp đầu; nếu retention/feedback cho thấy cần khớp chính xác hơn, cân nhắc forced-alignment ở lần lặp sau.
- **`--public-dir` trỏ vào gốc repo**: phục vụ toàn bộ repo qua HTTP nội bộ của Remotion trong lúc render (bao gồm cả mã nguồn, `.env`...) — chấp nhận được vì server này chỉ tồn tại cục bộ (localhost), trong đúng thời gian chạy `npx remotion render`, không phải server thường trực và không public ra ngoài; phù hợp bối cảnh vận hành 100% local, một người. Cách này cũng hoạt động đúng khi Python (sinh audio/ảnh) và Remotion CLI chạy trên cùng một máy, cùng thấy chung filesystem. Sẽ **không** hoạt động nếu sau này tách render sang máy chủ khác với máy sinh audio/ảnh (cần chuyển sang tự dựng HTTP server hoặc rsync asset trước khi render) — ngoài phạm vi hiện tại.
- **License Remotion**: miễn phí cho cá nhân/nhóm ≤3 người kể cả dùng thương mại (đã xác nhận ở spec kênh mục 4) — phù hợp với việc làm một mình hiện tại.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Forced-alignment caption theo từng từ nói ra.
- Avatar/logo/waveform-icon thật (đang dùng placeholder tại `remotion/public/avatar.png`).
- Nhạc nền royalty-free trộn vào audio (đã ghi là tuỳ chọn/ngoài phạm vi ở spec kênh lẫn spec TTS).
- Sinh metadata video (title/desc/tag/chapters) và upload YouTube — 2 sub-project riêng theo spec kênh.
- Automated test cho component React/TypeScript (Jest/Vitest + Remotion test utils).
- Render trên môi trường không phải local (cloud render, Remotion Lambda).
