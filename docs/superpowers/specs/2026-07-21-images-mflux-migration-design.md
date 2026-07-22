# Thiết kế: chuyển module sinh ảnh nền từ Together AI sang mflux (local)

**Ngày**: 2026-07-21
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Module sinh ảnh nền ([docs/superpowers/specs/2026-07-21-flux-images-module-design.md](2026-07-21-flux-images-module-design.md)) hiện dùng FLUX.1-schnell qua API Together AI. Thiết kế này thay thế backend đó bằng **[mflux](https://github.com/filipstrand/mflux)** (MIT license) — port MLX-native của FLUX.2, chạy **local trên Apple Silicon**, cụ thể qua CLI `mflux-generate-flux2` với model FLUX.2 Klein 4B.

Lý do chuyển: chạy local, không phụ thuộc free tier của bên thứ ba (có thể thay đổi/ngừng bất kỳ lúc nào), không cần API key. Khác với sự cố MPS (PyTorch) đã gặp ở module TTS, mflux dùng MLX — framework khác, được thiết kế riêng cho Apple Silicon, nên không thừa hưởng rủi ro đó.

Có sẵn code tham khảo đã chạy thực tế ở project khác của người vận hành (`/Users/lee/Project/Apps/youtube/mflux_generator.py`), dùng chung một pattern subprocess — thiết kế này áp dụng lại đúng pattern đó, chỉ khớp lại các tham số (kích thước ảnh, số bước) theo spec module ảnh audiobook đã duyệt trước đó.

Toàn bộ phần còn lại của module (scene prompt qua Gemini, style suffix, storage, cli orchestration) **không đổi** — chỉ thay thế `images/generator.py` và các phần phụ thuộc liên quan.

## 1. Quyết định thiết kế

- **Model**: `Runpod/FLUX.2-klein-4B-mflux-4bit` (bản Klein 4B đã quantize 4-bit sẵn trên HuggingFace) với `--base-model flux2-klein-4b`. Chọn 4B thay vì 9B vì máy vận hành có 16GB RAM hợp nhất — 4B nhẹ hơn, rủi ro ổn định bộ nhớ thấp hơn.
- **Cơ chế gọi**: subprocess gọi CLI `mflux-generate-flux2` (không dùng Python API nội bộ của mflux) — khớp với code tham khảo đã chạy thực tế, không cần học bề mặt API của thư viện.
  - **Trade-off đã biết**: mỗi lần gọi subprocess sẽ load lại toàn bộ model weights từ đầu — khác với nguyên tắc "load model 1 lần, tái dùng cho mọi chương" đã áp dụng cho OmniVoice (TTS) và Together AI client (module ảnh cũ). Với 8 chương/truyện, nghĩa là model được load 8 lần. Chấp nhận đánh đổi này để giữ đơn giản và đúng theo cách đã kiểm chứng; nếu sau này thấy quá chậm cho khối lượng sản xuất, cân nhắc chuyển sang Python API của mflux (load 1 lần) ở lần lặp sau — **ngoài phạm vi thiết kế này**.
- **Độ phân giải & số bước sinh ảnh**: giữ nguyên như spec module ảnh gốc — **1024×576, 4 bước** (`--width 1024 --height 576 --steps 4`). Không áp dụng 1920×1080 như code tham khảo bên project youtube, vì spec kênh đã chốt tỷ lệ này khớp khung hình video YouTube.
- **Đường dẫn thực thi CLI**: ưu tiên `.venv/bin/mflux-generate-flux2` của chính project audiobook (nếu tồn tại), fallback về `mflux-generate-flux2` trong PATH hệ thống — khớp pattern đã dùng ở code tham khảo, cho phép cả cài qua dependency của project lẫn cài global.
- **Xử lý gotcha "no-op nếu file đã tồn tại"**: đã xác nhận qua code tham khảo — `mflux-generate-flux2` thoát với return code 0 và **không ghi gì** nếu `--output` trỏ tới file đã tồn tại, thay vì ghi đè. Vì vậy: xoá file output (nếu có) **trước khi** gọi subprocess, và coi là thành công chỉ khi `returncode == 0` **và** file output tồn tại sau khi chạy — không chỉ dựa vào return code.
- **Giữ nguyên interface trả về `bytes`**: `generate_background_image` vẫn trả về `bytes` (không đổi thành trả về path) để `images/storage.py` và `images/cli.py` không cần sửa đổi — sinh ảnh vào một file tạm (`tempfile`), đọc bytes, xoá file tạm, trả bytes ra ngoài.
- **Không giữ Together AI làm dự phòng**: thay thế hoàn toàn. Xoá `together` khỏi `pyproject.toml`, xoá `TOGETHER_API_KEY` khỏi `.env.example`. Đơn giản hơn, không giữ code không dùng đến; nếu mflux không ổn định trên máy vận hành trong giai đoạn smoke test, sẽ xử lý lại ở lần lặp sau (không phải trong thiết kế này).

## 2. Kiến trúc

```
images/
├── generator.py     # ĐỔI: subprocess gọi mflux-generate-flux2 thay vì Together AI client
├── style.py          # không đổi (STYLE_SUFFIX)
├── scene_prompt.py    # không đổi (Gemini sinh mô tả cảnh)
├── storage.py          # không đổi (vẫn nhận list[(index, description, bytes)])
└── cli.py               # ĐỔI: bỏ khởi tạo Together client, gọi thẳng generator mới
```

**`generate_background_image(scene_description: str) -> bytes`:**

```
1. Ghép prompt = f"{scene_description}, {STYLE_SUFFIX}"
2. Tạo một đường dẫn file tạm DUY NHẤT nhưng CHƯA tạo file thật (vd:
   tempfile.mkdtemp() lấy thư mục tạm rồi ghép "scene.png" vào trong, thay vì
   NamedTemporaryFile — NamedTemporaryFile tạo file rỗng ngay khi gọi, và vì
   mflux-generate-flux2 no-op khi --output đã tồn tại, dùng nó sẽ luôn kích
   hoạt đúng lỗi no-op mà thiết kế này đang tránh)
3. Xác định đường dẫn thực thi CLI: ".venv/bin/mflux-generate-flux2" nếu tồn tại,
   ngược lại "mflux-generate-flux2" (PATH)
4. Gọi subprocess.run([...], capture_output=True, text=True) với:
   --model Runpod/FLUX.2-klein-4B-mflux-4bit
   --base-model flux2-klein-4b
   --prompt <prompt>
   --steps 4
   --width 1024 --height 576
   --output <file tạm>
5. Nếu returncode != 0 HOẶC file tạm không tồn tại sau khi chạy:
   raise ImageGenerationError(kèm stderr/stdout)
6. Đọc bytes từ file tạm, xoá thư mục tạm (shutil.rmtree), trả bytes
```

**`cli.py`** bỏ hoàn toàn `_load_flux_client()` và import `Together` — không còn client object nào cần khởi tạo cho bước sinh ảnh (mỗi lần gọi subprocess độc lập, không có state cần tái sử dụng). Vòng lặp chương giữ nguyên cấu trúc, chỉ đổi lời gọi:

```python
for chapter in script.chapters:
    scene_description = await generate_scene_description(chapter, gemini_client)
    image_bytes = generate_background_image(scene_description)
    images.append((chapter.index, scene_description, image_bytes))
```

## 3. Dependencies & cấu hình

- `pyproject.toml`: xoá `"together>=1.3.0"`, thêm `"mflux"` vào `dependencies` (cài CLI vào `.venv/bin` của project qua `uv sync`/`uv add`).
- `.env.example`: xoá dòng `TOGETHER_API_KEY=...` (không còn cần credential nào cho bước sinh ảnh).
- Không cần file config riêng (giữ nguyên quyết định từ spec gốc) — model, `--base-model`, kích thước, số bước vẫn là hằng số trong `generator.py`.

## 4. Testing & vận hành

- **Không gọi mflux thật trong test tự động** — model nặng, cần tải weights (vài GB) và chạy inference thật, đi ngược nguyên tắc "ngân sách thấp, không tốn tài nguyên thật trong test" đã áp dụng xuyên suốt project.
- Test bằng cách mock `subprocess.run` (thay cho mock `Together` client trước đây):
  - **Thành công**: mock tạo file thật tại `--output` (test dùng `tmp_path` của pytest) + trả `returncode=0` → hàm đọc đúng bytes đã ghi, xoá file tạm.
  - **Lỗi return code**: mock trả `returncode=1` kèm `stderr` → raise `ImageGenerationError` chứa nội dung stderr.
  - **Gotcha no-op**: mock trả `returncode=0` nhưng **không** tạo file → raise `ImageGenerationError` (phát hiện qua kiểm tra file tồn tại, không chỉ dựa return code).
  - Assert các tham số CLI được truyền đúng (`--model`, `--base-model`, `--steps 4`, `--width 1024`, `--height 576`, prompt chứa `STYLE_SUFFIX`).
- **Smoke test thủ công** (cuối kế hoạch triển khai, không tự động hoá): chạy CLI thật (`uv run python -m images.cli <script.json>`) với 1 file script JSON có sẵn, xác nhận:
  - `mflux` chạy được ổn định trên máy vận hành (không crash/treo, khác biệt với sự cố MPS ở TTS)
  - 8 ảnh sinh ra đúng phong cách, tỷ lệ 1024×576
  - Đo thời gian sinh 8 ảnh thực tế (bao gồm chi phí load lại model 8 lần) để đánh giá có chấp nhận được cho nhịp sản xuất 2-3 video/tuần hay không

## 5. Rủi ro & lưu ý

- **Smoke test thật đã chạy (2026-07-22), kết quả: THÀNH CÔNG, không lặp lại rủi ro hạ tầng của lần thử schnell trước đó**:
  1. Tải model `Runpod/FLUX.2-klein-4B-mflux-4bit` (~4.3GB) qua HuggingFace **không cần `HF_TOKEN`** (không phải gated repo, khác với `black-forest-labs/FLUX.1-schnell` gốc) và **không gặp lại bug "xet" transfer backend** (không cần set `HF_HUB_DISABLE_XET=1`).
  2. Đủ dung lượng ổ đĩa trên máy vận hành hiện tại (~8-13GB trống lúc chạy) — không lặp lại sự cố "No space left on device" đã gặp với schnell.
  3. mflux (MLX) chạy ổn định trên máy này qua toàn bộ 8 chương, không crash/treo — xác nhận không thừa hưởng rủi ro MPS đã gặp ở TTS.
  4. Đo thời gian thực tế: **~22 phút 25 giây cho 8 ảnh** (bao gồm chi phí load lại model 8 lần, không tính lần tải weight đầu tiên) — chấp nhận được cho nhịp sản xuất 2-3 video/tuần đã đặt ra, dù chậm hơn nhiều so với giữ model trong bộ nhớ.
  5. Chất lượng ảnh: đúng phong cách watercolor/flat-illustration đã duyệt, tông màu ấm nhất quán giữa các ảnh, không có chữ/logo lạ chèn vào ảnh (runes cách điệu ở ảnh có phép thuật không phải chữ thật).
- **Chi phí load lại model 8 lần/truyện**: xem mục "Quyết định thiết kế" — đã đo thực tế ở trên (~22.5 phút/8 ảnh). Nếu sau này thấy quá chậm cho khối lượng sản xuất lớn hơn, cân nhắc chuyển sang Python API của mflux (load 1 lần, tái dùng) ở lần lặp sau.
- **Tải model lần đầu**: `Runpod/FLUX.2-klein-4B-mflux-4bit` cần tải về từ HuggingFace ở lần chạy đầu tiên (~4.3GB, đã xác nhận thực tế) — không tính trong thời gian sinh ảnh của các lần chạy sau, nhưng cần lưu ý khi đo performance lần đầu.
- **Phụ thuộc vào công cụ bên thứ ba (mflux) còn khá mới**: FLUX.2 Klein mới phát hành (2026-01), CLI/tham số có thể đổi ở phiên bản sau — nếu `uv sync` nâng cấp mflux và CLI đổi tham số, cần cập nhật lại `generator.py`.
- **License**: mflux (MIT) và FLUX.2 Klein — cần xác nhận license của riêng weights `Runpod/FLUX.2-klein-4B-mflux-4bit` trên HuggingFace cho phép dùng thương mại trước khi publish kênh kiếm tiền (chưa xác nhận trong thiết kế này — **ngoài phạm vi**, cần kiểm tra ở giai đoạn vận hành trước khi bật kiếm tiền).

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Chuyển sang dùng Python API của mflux để load model 1 lần thay vì subprocess-per-chương (tối ưu hiệu năng, chỉ làm nếu smoke test cho thấy cần thiết).
- Xác nhận license thương mại chi tiết của weights `Runpod/FLUX.2-klein-4B-mflux-4bit`.
- Thử nghiệm FLUX.2 Klein 9B (chất lượng cao hơn) nếu 4B không đạt yêu cầu chất lượng hình ảnh.
- Retry/kiểm duyệt tự động khi ảnh sinh ra có lỗi (chữ/logo lạ) — đã ghi nhận là ngoài phạm vi ở spec gốc, giữ nguyên.
