# Thiết kế module sinh thumbnail cho video YouTube

**Ngày**: 2026-07-22
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Spec module SEO metadata ([docs/superpowers/specs/2026-07-22-seo-metadata-module-design.md](2026-07-22-seo-metadata-module-design.md)) đã liệt kê "tạo thumbnail tự động" là ngoài phạm vi, cần thao tác tay trên YouTube Studio. Module này lấp khoảng trống đó: **tự động sinh 1 ảnh thumbnail 1280×720** ngay sau khi video render xong (stage 4), độc lập với stage 5 (SEO metadata) — người vận hành chỉ cần tải ảnh lên khi upload thủ công (upload thumbnail qua YouTube Studio vẫn là thao tác tay, giữ đúng quyết định "không tự động upload" đã chốt ở spec SEO).

## 1. Quyết định thiết kế

- **Không tái sử dụng ảnh nền chương (`images/`)**: `images/style.py`'s `STYLE_SUFFIX` cố tình cấm "no human faces in close-up" (tránh lỗi AI vẽ mặt sai/lệch khi ảnh lặp lại xuyên suốt video 25-45 phút). Thumbnail YouTube chuẩn lại cần ngược lại — gương mặt/nhân vật cận cảnh, cảm xúc rõ nét, để tăng CTR. Vì 2 yêu cầu về mặt hình ảnh trực tiếp mâu thuẫn nhau, thumbnail sinh **ảnh riêng, style riêng, prompt riêng** — không mở rộng `images/`.
- **Sinh bằng mflux, không dùng lại code `images/generator.py`**: cùng công cụ nền tảng (`mflux-generate-flux2`, model `Runpod/FLUX.2-klein-4B-mflux-4bit`) nhưng tham số khác hẳn (1280×720 thay vì 1024×576, 8 bước thay vì 4 — chất lượng cao hơn cho prompt phức tạp/nhân vật, khớp pattern đã thấy ở project tham khảo khác dùng chung mflux cho cả ảnh nền lẫn thumbnail). Không trích xuất code dùng chung giữa `images/` và `thumbnail/` ở lần lặp này — theo đúng tiền lệ hiện có của dự án (`tts/synthesizer.py` và `images/generator.py` là 2 cách gọi công cụ ngoài độc lập, chưa từng hợp nhất); tránh refactor không cần thiết vào code đã chạy ổn định.
- **Chữ tiêu đề (hook text) KHÔNG để mflux tự vẽ**: đã ghi nhận nhiều lần trong dự án rằng model sinh ảnh có thể tự chèn chữ sai/lỗi (xem rủi ro ở spec module ảnh nền). Thay vào đó: Gemini sinh câu hook ngắn (2-4 từ tiếng Việt, IN HOA, kiểu giật gân nhưng đúng nội dung), rồi dùng **Pillow** (dependency mới) vẽ đè chữ đậm + viền đen tương phản cao lên ảnh đã sinh — đảm bảo chữ luôn đọc được, không phụ thuộc độ tin cậy của model ảnh.
- **1 lần gọi Gemini duy nhất** cho cả hook text (tiếng Việt) và visual description (tiếng Anh, cho mflux) — dùng format nhãn `HOOK:`/`VISUAL:` giống pattern `seo_generator.py` đã dùng (nhãn dòng-đơn giản, không dùng JSON — bài học đã ghi nhận nhiều lần về độ tin cậy gemini-webapi).
- **Input cho Gemini là tóm tắt** (title + trope + toàn bộ heading 8 chương), không gửi full text truyện — giống đúng quyết định đã áp dụng ở `seo_generator.py`, để Gemini tự suy luận cao trào/cảm xúc chủ đạo mà không cần code tự chọn "chương nào là cao trào".
- **Không phụ thuộc vào stage 5 (metadata)**: thumbnail không cần title SEO đã sinh, không cần video đã đổi tên — chỉ cần `script.json`. Trình tự "ngay sau khi render xong" là quy ước vận hành (ghi trong skill), không phải phụ thuộc dữ liệu bắt buộc.
- **Cần 1 file font TTF chữ đậm, hỗ trợ dấu tiếng Việt đầy đủ**, đóng gói sẵn trong repo tại `assets/fonts/` (không dựa vào font hệ thống — không đảm bảo tồn tại/nhất quán giữa các máy). Dùng **Noto Sans Bold** (SIL Open Font License, miễn phí thương mại, hỗ trợ đầy đủ tổ hợp dấu tiếng Việt).
- **Không tự động upload thumbnail lên YouTube**: giữ đúng quyết định "không tự động hoá upload" đã chốt ở spec SEO metadata — người vận hành tự tải ảnh `.png` lên khi upload video thủ công.

## 2. Kiến trúc

```
thumbnail/
├── __init__.py
├── style.py               # THUMBNAIL_STYLE_SUFFIX (cho phép cận cảnh, cảm xúc mạnh)
├── prompt_generator.py      # Gemini: script -> ThumbnailPrompt(hook_text, visual_description)
├── generator.py                # mflux: visual_description -> ảnh PNG bytes (1280x720, 8 bước)
├── compositor.py                 # Pillow: đè hook_text lên ảnh -> PNG bytes hoàn chỉnh
├── storage.py                      # lưu output/thumbnails/<trope>-<ts>.png
└── cli.py                            # entrypoint: nhận script_path

assets/
└── fonts/
    └── NotoSans-Bold.ttf    # font đóng gói sẵn (SIL OFL), dùng cho compositor.py
```

**Luồng xử lý:**

```
[script.json] (input: người vận hành cung cấp, thường ngay sau khi stage 4 render xong)
   → 1. Khởi tạo Gemini client 1 lần
   → 2. Gemini sinh 1 lần: title + trope + 8 heading -> parse nhãn HOOK:/VISUAL:
        → ThumbnailPrompt(hook_text: str, visual_description: str)
   → 3. mflux-generate-flux2: f"{visual_description}, {THUMBNAIL_STYLE_SUFFIX}"
        --width 1280 --height 720 --steps 8 -> ảnh PNG (bytes)
   → 4. Pillow: mở ảnh, vẽ hook_text (in hoa, font Noto Sans Bold, viền đen, căn giữa
        theo chiều ngang, đặt ở 1/3 dưới khung hình, tự co cỡ chữ nếu bề rộng vượt
        ~90% chiều rộng ảnh) -> PNG bytes hoàn chỉnh
   → 5. Lưu output/thumbnails/<trope>-<ts>.png
```

**`prompt_generator.py`** — `generate_thumbnail_prompt(script, client) -> ThumbnailPrompt` (dataclass: `hook_text: str`, `visual_description: str`). Prompt:

```
Bạn là chuyên gia thiết kế thumbnail YouTube. Dựa trên thông tin truyện audio
tiếng Việt sau, hãy tạo nội dung cho thumbnail hấp dẫn.

Tiêu đề truyện: {title}
Thể loại: {trope}
Danh sách chương:
{headings}

Trả lời CHÍNH XÁC theo format sau, mỗi nhãn bắt đầu một dòng mới, KHÔNG thêm
giải thích nào khác:

HOOK: <câu hook 2-4 từ tiếng Việt, IN HOA, giật gân nhưng đúng nội dung truyện,
phù hợp làm chữ nổi bật trên thumbnail>
VISUAL: <mô tả bằng tiếng Anh, 1-2 câu, một cảnh cận cảnh nhân vật thể hiện cảm
xúc chủ đạo/cao trào của truyện (ví dụ: shocked expression, triumphant smirk,
tearful determination) - KHÔNG dùng tên riêng, KHÔNG mô tả toàn bộ cốt truyện>
```

Parse lại đúng cơ chế `_parse_label` đã có ở `metadata/seo_generator.py` (tách theo nhãn, raise lỗi rõ ràng nếu thiếu/rỗng nhãn nào — không dùng lại y hệt code, viết bản riêng cho 2 nhãn `HOOK`/`VISUAL` theo cùng nguyên tắc).

**`style.py`**:
```python
THUMBNAIL_STYLE_SUFFIX = (
    "dramatic close-up portrait, intense emotional expression, cinematic lighting, "
    "vivid warm color palette, high contrast, YouTube thumbnail style, "
    "no text, no logos, no watermark"
)
```

**`generator.py`** — `generate_thumbnail_image(visual_description: str) -> bytes`, cấu trúc y hệt `images/generator.py` (subprocess gọi `mflux-generate-flux2`, tạo thư mục tạm qua `tempfile.mkdtemp()` — KHÔNG dùng `NamedTemporaryFile()` vì gotcha đã biết, kiểm tra `returncode == 0 VÀ file tồn tại`, dọn thư mục tạm trong `finally`), khác các hằng số:
```python
MODEL = "Runpod/FLUX.2-klein-4B-mflux-4bit"
BASE_MODEL = "flux2-klein-4b"
WIDTH = 1280
HEIGHT = 720
STEPS = 8
```
Raise `ThumbnailGenerationError` (exception riêng của module, không dùng chung `images.generator.ImageGenerationError`).

**`compositor.py`** — `overlay_hook_text(image_bytes: bytes, hook_text: str) -> bytes`. Dùng `PIL.Image`/`PIL.ImageDraw`/`PIL.ImageFont`:
- Mở ảnh từ bytes, vẽ text `hook_text.upper()` bằng font `assets/fonts/NotoSans-Bold.ttf`.
- Màu chữ trắng, viền đen (stroke) độ dày đủ để đọc được trên mọi nền ảnh.
- Căn giữa theo chiều ngang, đặt tại khoảng 1/3 dưới khung hình (không che khuôn mặt thường nằm giữa/trên ảnh).
- Cỡ chữ mặc định lớn (ví dụ ~100px ở ảnh 1280×720), tự giảm dần nếu bề rộng dòng chữ vượt quá ~90% chiều rộng ảnh (dùng `font.getlength()`/`draw.textlength()` để đo trước khi vẽ).
- Trả về PNG bytes (encode lại qua `io.BytesIO`).

**`storage.py`** — `save_thumbnail(trope: str, image_bytes: bytes, output_dir: Path) -> Path`, lưu `output_dir / f"{trope}-{timestamp}.png"`, tạo thư mục nếu chưa có — cùng pattern các `storage.py` khác trong dự án.

**`cli.py`** — `uv run python -m thumbnail.cli <script_path>`, in ra đường dẫn file đã lưu.

## 3. Dependencies

- Thêm `Pillow` vào `pyproject.toml` (dependency mới, chưa có trong dự án).
- Thêm file `assets/fonts/NotoSans-Bold.ttf` (tải từ Google Fonts, SIL Open Font License — cần ghi rõ nguồn/license trong thư mục `assets/fonts/` khi triển khai, ví dụ 1 file `LICENSE.txt` đi kèm).
- Không cần thêm dependency Node/Remotion nào (thumbnail là ảnh tĩnh, không qua Remotion).

## 4. Testing & vận hành

- **Không gọi Gemini/mflux thật trong test tự động** — dùng client/subprocess giả, đúng nguyên tắc xuyên suốt dự án.
- `prompt_generator.py`: test bằng Gemini client giả — parse đúng khi có đủ 2 nhãn, raise lỗi rõ ràng khi thiếu nhãn hoặc nhãn rỗng.
- `generator.py`: test bằng mock `subprocess.run` — thành công, lỗi returncode khác 0, và case no-op (returncode 0 nhưng không tạo file) — giống hệt cấu trúc test đã có ở `tests/images/test_generator.py`.
- `compositor.py`: **test thật, không mock** — Pillow xử lý nhanh, không gọi mạng/tool ngoài, giống nguyên tắc đã áp dụng cho `pyloudnorm` ở module TTS. Test: ảnh đầu vào giả (PNG nhỏ tạo bằng Pillow trong test), verify ảnh đầu ra là PNG hợp lệ, có kích thước đúng 1280×720, và test riêng hàm đo/co cỡ chữ với chuỗi hook dài để xác nhận không vẽ tràn khung hình.
- `storage.py`: test bằng `tmp_path`, giống các `storage.py` khác.
- `cli.py`: test bằng cách monkeypatch từng hàm con (`generate_thumbnail_prompt`, `generate_thumbnail_image`, `overlay_hook_text`), giống pattern test `cli.py` các module khác.
- **Smoke test thủ công** (cuối kế hoạch triển khai): chạy CLI thật với 1 file `script.json` đã có sẵn (ví dụ script `xuyen_khong_gia_toc` đã sinh ở lần chạy trước), xem ảnh thumbnail: chữ hook đọc rõ, không tràn khung, ảnh nhân vật đúng cảm xúc/không có chữ lạ do mflux tự vẽ, không có gương mặt bị lỗi/méo rõ rệt.
- **Cập nhật skill `generating-audiobook-video`**: thêm 1 dòng/bước mới vào bảng "The Five Stages" (thành 6 stage) ghi rõ `thumbnail.cli` chạy ngay sau stage 4 (render video), độc lập dữ liệu với stage 5 — thực hiện như một task trong kế hoạch triển khai, không phải quyết định thiết kế riêng.

## 5. Rủi ro & lưu ý

- **mflux vẫn có thể vẽ mặt người lỗi/méo dù dùng 8 bước** — model diffusion nhỏ (4B, quantize 4-bit) không đảm bảo tuyệt đối khuôn mặt đúng giải phẫu, đặc biệt cận cảnh. Cần xem qua ảnh ở smoke test; nếu chất lượng không đạt, cân nhắc tăng bước hoặc đổi model ở lần lặp sau — ngoài phạm vi thiết kế này.
- **Chất lượng hook text phụ thuộc gemini-webapi** — như đã ghi nhận nhiều lần, kém tin cậy hơn API chính thức; người vận hành nên đọc lại hook text trước khi dùng nếu thấy bất thường (dù đã có validate parse nhãn).
- **Không tự động hoá việc chọn thumbnail nào là "đẹp nhất"** — module luôn sinh đúng 1 ảnh/lần chạy; nếu người vận hành muốn nhiều lựa chọn, chạy lại CLI nhiều lần (mỗi lần Gemini/mflux có thể cho kết quả khác nhau do tính ngẫu nhiên).
- **Trùng lặp code với `images/generator.py`**: chấp nhận đánh đổi (xem mục "Quyết định thiết kế") — nếu sau này phát hiện bug chung ở cơ chế gọi mflux (ví dụ gotcha no-op), cần sửa ở cả 2 nơi.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Tự động upload thumbnail lên YouTube (vẫn thao tác tay qua YouTube Studio, giữ đúng quyết định spec SEO).
- Sinh nhiều phương án thumbnail để người vận hành chọn (A/B test).
- Trích xuất code dùng chung giữa `images/generator.py` và `thumbnail/generator.py`.
- Tự động kiểm duyệt chất lượng ảnh (phát hiện mặt lỗi/méo bằng công cụ khác).
