# Thiết kế module sinh ảnh nền (Flux)

**Ngày**: 2026-07-21
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Sub-project thứ 3 của pipeline kênh YouTube truyện audio (xem [docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md](2026-07-21-youtube-audiobook-channel-design.md)), tiếp theo module sinh kịch bản và module TTS đã hoàn thành.

Module này nhận file JSON kịch bản (`{"trope": str, "title": str, "chapters": [{"index": int, "heading": str, "text": str}]}`, do module sinh kịch bản tạo ra tại `output/scripts/`) và trả về **8 ảnh nền** (1 ảnh/chương) theo đúng phong cách visual đã duyệt ở spec kênh (mục "Phong cách hình ảnh": watercolor/flat-illustration ấm áp, nội thất hoặc thiên nhiên), sẵn sàng cho bước dựng video (Remotion) ở sub-project sau.

Công nghệ sinh ảnh: **FLUX.1-schnell**, chạy local qua [mflux](https://github.com/filipstrand/mflux) (MLX-native, lượng tử hoá 4-bit), license Apache-2.0.

## 1. Quyết định thiết kế

- **Hạ tầng chạy Flux — CẬP NHẬT (2026-07-21, sau khi module đã triển khai xong với Together AI)**: người vận hành muốn chạy **local** thay vì API, dù đã được cảnh báo rủi ro (FLUX.1-schnell ~12 tỷ tham số + T5-XXL ~4.7 tỷ, ở fp16 cần ~24GB chỉ riêng trọng số — vượt quá 16GB RAM hợp nhất của máy, và module TTS đã cho thấy PyTorch/MPS không ổn định ngay cả với model nhỏ hơn nhiều). Giải pháp: dùng **[mflux](https://github.com/filipstrand/mflux)** — port MLX-native của Flux cho Apple Silicon, KHÔNG dùng PyTorch/MPS (né được đúng lớp lỗi đã gặp ở OmniVoice) — với **lượng tử hoá 4-bit** (`--quantize 4`) để giảm bộ nhớ xuống mức vừa với 16GB RAM, kèm `--low-ram` để giảm thêm áp lực bộ nhớ (đổi lại tốc độ chậm hơn). Gọi qua CLI `mflux-generate` bằng subprocess — theo đúng pattern đã dùng cho Remotion trong spec kênh (gọi công cụ ngoài qua subprocess thay vì phụ thuộc vào Python API nội bộ chưa ổn định của thư viện). Vẫn còn rủi ro thực sự chưa được xác nhận bằng smoke test thật (xem mục 4).
- **Không còn dùng Together AI**: bỏ hẳn phụ thuộc `together` và `TOGETHER_API_KEY`.
- **Số ảnh/chương**: **1 ảnh/chương**, tổng 8 ảnh/truyện — khớp đúng với 8 chunk audio đã có từ module TTS. Remotion sẽ Ken Burns pan mỗi ảnh xuyên suốt thời lượng chương tương ứng (~3-4 phút/ảnh).
- **Sinh mô tả cảnh (scene prompt)**: nội dung chương là văn xuôi tiếng Việt, không phải prompt ảnh — cần một bước LLM tóm tắt chương thành mô tả bối cảnh ngắn (1-2 câu, tiếng Anh) trước khi đưa vào Flux. Tái sử dụng **Gemini-API (gemini-webapi)** đã tích hợp sẵn từ module sinh kịch bản (cùng tài khoản Google phụ) — không cần thêm dịch vụ mới.
- **Nội dung mô tả cảnh**: chỉ tập trung vào **không gian/bối cảnh và không khí** (ví dụ "cozy living room at dusk", "misty mountain valley at dawn") — KHÔNG mô tả nhân vật cụ thể, KHÔNG kể lại cốt truyện, KHÔNG dùng tên riêng. Khớp với phong cách ảnh nền trong template (cảnh vật, không phải chân dung nhân vật) và giảm rủi ro Flux vẽ sai/lệch nhân vật.
- **Style nhất quán**: mọi ảnh dùng chung một `STYLE_SUFFIX` cố định (watercolor/flat-illustration, tông màu ấm, không chữ/logo, không cận mặt người) ghép vào cuối mỗi prompt, đảm bảo tất cả ảnh trong cùng 1 kênh có phong cách đồng nhất.
- **Kích thước ảnh**: 1024×576 (16:9, khớp tỷ lệ khung hình video YouTube), 4 bước sinh ảnh (schnell tối ưu cho 1-4 bước, không cần nhiều hơn).
- **Tái sử dụng tiến trình**: mỗi lần gọi `mflux-generate` là 1 tiến trình con độc lập (mflux tự load lại model mỗi lần chạy CLI) — khác với TTS (load model 1 lần, tái dùng trong process). Đây là giới hạn của việc gọi qua CLI/subprocess thay vì Python API; chấp nhận đánh đổi để có giao diện ổn định, tránh phụ thuộc Python API nội bộ chưa rõ ràng của mflux. Nếu tốc độ quá chậm ở giai đoạn vận hành, cân nhắc chuyển sang gọi Python API trực tiếp (rủi ro: API có thể thay đổi giữa các phiên bản mflux).
- Gemini client vẫn khởi tạo 1 lần, tái sử dụng cho 8 lần gọi scene-prompt (không đổi so với thiết kế API cũ).

## 2. Kiến trúc

```
images/
├── __init__.py
├── style.py           # STYLE_SUFFIX cố định
├── scene_prompt.py     # Gemini: chapter.text -> mô tả bối cảnh ngắn bằng tiếng Anh
├── generator.py         # gọi mflux-generate (subprocess, local, MLX) -> ảnh PNG (bytes)
├── storage.py            # lưu 8 ảnh .png + 1 file JSON metadata (chapter -> filename, prompt)
└── cli.py                 # entrypoint: nhận đường dẫn file script JSON, chạy toàn bộ
```

**Luồng xử lý:**

```
[File JSON kịch bản] (input: đường dẫn do người vận hành cung cấp)
   → 1. Khởi tạo Gemini client 1 lần
   → 2. Với mỗi chương (8 chương):
        a. Gemini (single-shot generate_content, không cần chat nhiều lượt vì output ngắn):
           tóm tắt chapter.text thành 1-2 câu mô tả bối cảnh/không khí bằng tiếng Anh
        b. Ghép mô tả cảnh + STYLE_SUFFIX -> gọi `mflux-generate` qua subprocess
           (model schnell, 1024x576, 4 steps, quantize 4, --low-ram) -> đọc file PNG
           tạm mflux tạo ra, trả về bytes
   → 3. Lưu 8 file .png và 1 file .json metadata (trope, title, danh sách
        {index, filename, scene_description}) vào output/images/
```

**Cấu hình**: `STYLE_SUFFIX`, kích thước ảnh, số bước sinh, mức lượng tử hoá là hằng số trong `style.py`/`generator.py`. Không còn `TOGETHER_API_KEY`. `mflux` cài qua `pyproject.toml` (dependency chuẩn của project, cung cấp lệnh `mflux-generate` trong `.venv`).

## 3. Testing & vận hành

- **Không gọi Gemini thật hoặc chạy `mflux-generate` thật trong test tự động** — luôn dùng client/subprocess giả (mock/fake), giống nguyên tắc đã áp dụng cho module sinh kịch bản và module TTS. `mflux-generate` thật nặng (load model, tốn thời gian/bộ nhớ thật), tuyệt đối không chạy trong test.
- **Smoke test thủ công** (cuối kế hoạch triển khai, không tự động hoá): chạy CLI thật với 1 file script JSON đã có sẵn, xem qua 8 ảnh sinh ra để xác nhận: (a) `mflux-generate` chạy được ổn định trên máy này với `--quantize 4 --low-ram` mà không crash/treo (rủi ro chính, xem mục 4), (b) đúng phong cách visual đã duyệt, (c) không có chữ/logo lạ xuất hiện trong ảnh, (d) các ảnh trong cùng truyện nhất quán về tông màu/phong cách. Nếu smoke test thất bại (crash/treo tương tự OmniVoice), quay lại phương án Together AI API đã có sẵn trong lịch sử git (branch/commit trước khi đổi sang mflux).

## 4. Rủi ro & lưu ý

- **License FLUX.1-schnell**: Apache-2.0, dùng thương mại được — khác với `FLUX.1 [dev]` (chỉ miễn phí phi thương mại), đã ghi rõ trong spec kênh mục 4.
- **Rủi ro phần cứng CHƯA được xác nhận bằng smoke test thật**: quyết định dùng mflux (MLX-native) dựa trên suy luận hợp lý (né PyTorch/MPS — lớp gây lỗi ở OmniVoice — và dùng lượng tử hoá 4-bit để vừa 16GB RAM), nhưng **chưa chạy thử thật** trên máy này tại thời điểm viết spec. Có khả năng vẫn gặp vấn đề bộ nhớ/ổn định khác (MLX cũng cần tải toàn bộ working set vào RAM hợp nhất, dù nhẹ hơn PyTorch/MPS nhiều). Bắt buộc chạy smoke test thật trước khi coi module này là hoàn thành.
- **Chất lượng ảnh có thể thấp hơn bản đầy đủ (fp16)**: lượng tử hoá 4-bit đánh đổi chất lượng lấy bộ nhớ — cần đánh giá qua smoke test xem có chấp nhận được cho mục đích ảnh nền hay không.
- **Không tái sử dụng model giữa các lần gọi**: gọi qua subprocess CLI nghĩa là mflux load lại model từ đầu mỗi lần gọi `mflux-generate` (8 lần/truyện) — chậm hơn đáng kể so với giữ model trong bộ nhớ suốt quá trình (như TTS làm) nhưng đơn giản/ổn định hơn về giao diện gọi.
- **Model sinh ảnh có thể tự chèn chữ/logo lạ vào ảnh**: lỗi phổ biến của các model diffusion — `STYLE_SUFFIX` đã có chỉ định "no text, no logos, no words" nhưng không đảm bảo tuyệt đối; cần kiểm tra qua smoke test, xử lý thêm (vd retry, hậu kỳ crop) nếu phát hiện vấn đề rõ rệt ở giai đoạn vận hành.
- **Chất lượng mô tả cảnh từ Gemini**: vì dùng gemini-webapi (reverse-engineered, đã biết là kém tin cậy hơn structured output chính thức — xem ghi chú ở spec module sinh kịch bản), mô tả cảnh trả về có thể không đúng định dạng ngắn gọn mong muốn (vd kèm giải thích thừa); `scene_prompt.py` cần xử lý làm sạch output cơ bản (strip, bỏ dấu ngoặc kép thừa) nhưng không cần parse JSON phức tạp vì output chỉ là 1 câu text.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Ảnh avatar kênh (nhân vật minh hoạ cố định) — thiết kế 1 lần, không phải sinh tự động theo từng video, đã ghi trong spec kênh là "ngoài phạm vi" cần chốt riêng.
- Waveform icon, tiêu đề overlay, caption cháy nền — thuộc phạm vi module dựng video (Remotion) sau, không phải module này.
- Xử lý retry/kiểm duyệt tự động khi Flux sinh ảnh có chữ/logo lạ — ghi nhận là rủi ro, xử lý ở giai đoạn vận hành nếu cần.
- Gọi Python API trực tiếp của mflux thay vì subprocess CLI (nếu cần tái sử dụng model giữa các lần gọi để tăng tốc) — cân nhắc sau nếu tốc độ subprocess không đủ.
