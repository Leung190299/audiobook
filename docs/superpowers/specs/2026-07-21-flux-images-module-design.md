# Thiết kế module sinh ảnh nền (Flux)

**Ngày**: 2026-07-21
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Sub-project thứ 3 của pipeline kênh YouTube truyện audio (xem [docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md](2026-07-21-youtube-audiobook-channel-design.md)), tiếp theo module sinh kịch bản và module TTS đã hoàn thành.

Module này nhận file JSON kịch bản (`{"trope": str, "title": str, "chapters": [{"index": int, "heading": str, "text": str}]}`, do module sinh kịch bản tạo ra tại `output/scripts/`) và trả về **8 ảnh nền** (1 ảnh/chương) theo đúng phong cách visual đã duyệt ở spec kênh (mục "Phong cách hình ảnh": watercolor/flat-illustration ấm áp, nội thất hoặc thiên nhiên), sẵn sàng cho bước dựng video (Remotion) ở sub-project sau.

Công nghệ sinh ảnh: **FLUX.1-schnell** qua [Together AI](https://www.together.ai/) (`black-forest-labs/FLUX.1-schnell-Free`), license Apache-2.0, miễn phí không giới hạn trong chương trình free tier hiện tại của Together AI.

## 1. Quyết định thiết kế

- **Hạ tầng chạy Flux**: dùng **API (Together AI)**, không chạy local. Lý do: FLUX.1-schnell là model diffusion ~12 tỷ tham số + text encoder T5-XXL ~4.7 tỷ, cần tối thiểu 10GB+ VRAM GPU chuyên dụng — máy của người vận hành (16GB RAM hợp nhất, Apple Silicon) đã cho thấy không đủ ổn định ngay cả với model TTS nhỏ hơn nhiều (xem sự cố MPS ở module TTS). Dùng API tránh lặp lại rủi ro phần cứng, và Together AI hiện miễn phí không giới hạn cho FLUX.1-schnell-Free.
- **Số ảnh/chương**: **1 ảnh/chương**, tổng 8 ảnh/truyện — khớp đúng với 8 chunk audio đã có từ module TTS. Remotion sẽ Ken Burns pan mỗi ảnh xuyên suốt thời lượng chương tương ứng (~3-4 phút/ảnh).
- **Sinh mô tả cảnh (scene prompt)**: nội dung chương là văn xuôi tiếng Việt, không phải prompt ảnh — cần một bước LLM tóm tắt chương thành mô tả bối cảnh ngắn (1-2 câu, tiếng Anh) trước khi đưa vào Flux. Tái sử dụng **Gemini-API (gemini-webapi)** đã tích hợp sẵn từ module sinh kịch bản (cùng tài khoản Google phụ) — không cần thêm dịch vụ mới.
- **Nội dung mô tả cảnh**: chỉ tập trung vào **không gian/bối cảnh và không khí** (ví dụ "cozy living room at dusk", "misty mountain valley at dawn") — KHÔNG mô tả nhân vật cụ thể, KHÔNG kể lại cốt truyện, KHÔNG dùng tên riêng. Khớp với phong cách ảnh nền trong template (cảnh vật, không phải chân dung nhân vật) và giảm rủi ro Flux vẽ sai/lệch nhân vật.
- **Style nhất quán**: mọi ảnh dùng chung một `STYLE_SUFFIX` cố định (watercolor/flat-illustration, tông màu ấm, không chữ/logo, không cận mặt người) ghép vào cuối mỗi prompt, đảm bảo tất cả ảnh trong cùng 1 kênh có phong cách đồng nhất.
- **Kích thước ảnh**: 1024×576 (16:9, khớp tỷ lệ khung hình video YouTube), 4 bước sinh ảnh (schnell tối ưu cho 1-4 bước, không cần nhiều hơn).
- **Tái sử dụng client**: cả Gemini client và Together AI client được khởi tạo 1 lần, dùng lại cho toàn bộ 8 chương trong một lần chạy CLI — cùng nguyên tắc với việc load model TTS 1 lần.

## 2. Kiến trúc

```
images/
├── __init__.py
├── style.py           # STYLE_SUFFIX cố định
├── scene_prompt.py     # Gemini: chapter.text -> mô tả bối cảnh ngắn bằng tiếng Anh
├── generator.py         # gọi Together AI FLUX.1-schnell-Free -> ảnh PNG (bytes)
├── storage.py            # lưu 8 ảnh .png + 1 file JSON metadata (chapter -> filename, prompt)
└── cli.py                 # entrypoint: nhận đường dẫn file script JSON, chạy toàn bộ
```

**Luồng xử lý:**

```
[File JSON kịch bản] (input: đường dẫn do người vận hành cung cấp)
   → 1. Khởi tạo Gemini client + Together AI client 1 lần
   → 2. Với mỗi chương (8 chương):
        a. Gemini (single-shot generate_content, không cần chat nhiều lượt vì output ngắn):
           tóm tắt chapter.text thành 1-2 câu mô tả bối cảnh/không khí bằng tiếng Anh
        b. Ghép mô tả cảnh + STYLE_SUFFIX -> gọi Together AI FLUX.1-schnell-Free
           (1024x576, 4 steps) -> ảnh PNG (bytes, qua response base64)
   → 3. Lưu 8 file .png và 1 file .json metadata (trope, title, danh sách
        {index, filename, scene_description}) vào output/images/
```

**Cấu hình**: không cần file config riêng (không có tham số cần tinh chỉnh thường xuyên như `voice.yaml`) — `STYLE_SUFFIX`, kích thước ảnh, số bước sinh là hằng số trong `style.py`/`generator.py`. `TOGETHER_API_KEY` đọc từ `.env` (giống `SECURE_1PSID`/`SECURE_1PSIDTS`).

## 3. Testing & vận hành

- **Không gọi Gemini hoặc Together AI thật trong test tự động** — luôn dùng client giả (mock/fake), giống nguyên tắc đã áp dụng cho module sinh kịch bản và module TTS.
- **Smoke test thủ công** (cuối kế hoạch triển khai, không tự động hoá): chạy CLI thật với 1 file script JSON đã có sẵn, xem qua 8 ảnh sinh ra để xác nhận: đúng phong cách visual đã duyệt, không có chữ/logo lạ xuất hiện trong ảnh (lỗi thường gặp của model sinh ảnh), và các ảnh trong cùng truyện có sự nhất quán về tông màu/phong cách.

## 4. Rủi ro & lưu ý

- **License FLUX.1-schnell**: Apache-2.0, dùng thương mại được — khác với `FLUX.1 [dev]` (chỉ miễn phí phi thương mại), đã ghi rõ trong spec kênh mục 4.
- **Free tier Together AI có thể thay đổi**: chương trình miễn phí không giới hạn cho FLUX.1-schnell-Free là ưu đãi hiện tại, không đảm bảo vĩnh viễn — nếu ngừng, cần chuyển sang trả phí (~$0.003/ảnh, vẫn rất rẻ cho khối lượng 2-3 video/tuần × 8 ảnh) hoặc nhà cung cấp khác (fal.ai, Replicate).
- **Model sinh ảnh có thể tự chèn chữ/logo lạ vào ảnh**: lỗi phổ biến của các model diffusion — `STYLE_SUFFIX` đã có chỉ định "no text, no logos, no words" nhưng không đảm bảo tuyệt đối; cần kiểm tra qua smoke test, xử lý thêm (vd retry, hậu kỳ crop) nếu phát hiện vấn đề rõ rệt ở giai đoạn vận hành.
- **Chất lượng mô tả cảnh từ Gemini**: vì dùng gemini-webapi (reverse-engineered, đã biết là kém tin cậy hơn structured output chính thức — xem ghi chú ở spec module sinh kịch bản), mô tả cảnh trả về có thể không đúng định dạng ngắn gọn mong muốn (vd kèm giải thích thừa); `scene_prompt.py` cần xử lý làm sạch output cơ bản (strip, bỏ dấu ngoặc kép thừa) nhưng không cần parse JSON phức tạp vì output chỉ là 1 câu text.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Ảnh avatar kênh (nhân vật minh hoạ cố định) — thiết kế 1 lần, không phải sinh tự động theo từng video, đã ghi trong spec kênh là "ngoài phạm vi" cần chốt riêng.
- Waveform icon, tiêu đề overlay, caption cháy nền — thuộc phạm vi module dựng video (Remotion) sau, không phải module này.
- Xử lý retry/kiểm duyệt tự động khi Flux sinh ảnh có chữ/logo lạ — ghi nhận là rủi ro, xử lý ở giai đoạn vận hành nếu cần.
- Chọn nhà cung cấp API thay thế nếu Together AI ngừng free tier.
