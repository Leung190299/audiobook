# Thiết kế module TTS (lồng tiếng) — OmniVoice

**Ngày**: 2026-07-21
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Sub-project thứ 2 của pipeline kênh YouTube truyện audio (xem [docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md](2026-07-21-youtube-audiobook-channel-design.md)), tiếp theo module sinh kịch bản đã hoàn thành ([docs/superpowers/plans/2026-07-21-script-generation-module.md](../plans/2026-07-21-script-generation-module.md)).

Module này nhận file JSON kịch bản (`{"trope": str, "title": str, "chapters": [{"index": int, "heading": str, "text": str}]}`, do module trước tạo ra tại `output/scripts/`) và trả về **một file audio hoàn chỉnh** đã lồng tiếng, chuẩn hoá loudness, sẵn sàng cho bước dựng video (Remotion) ở sub-project sau.

Công nghệ TTS: [OmniVoice](https://github.com/k2-fsa/OmniVoice) — TTS zero-shot đa ngôn ngữ (đã xác nhận hỗ trợ tiếng Việt, mã `vi`, 8.482 giờ dữ liệu training), license Apache-2.0, chạy local (tự host, không cần API key/chi phí trả phí).

## 1. Quyết định thiết kế

- **Nguồn giọng đọc**: **voice design** bằng mô tả text (ví dụ "giọng nữ, ấm áp, tốc độ vừa") — không dùng voice cloning từ audio mẫu có sẵn, để tránh cần tìm nguồn giọng và rủi ro bản quyền/quyền giọng nói.
- **Hạ tầng chạy**: local trên máy Mac của người vận hành (Apple Silicon/MPS backend của OmniVoice) — không thuê GPU cloud, giữ chi phí bằng 0. Nếu sau này tốc độ không đủ, cân nhắc chuyển sang GPU cloud (ngoài phạm vi thiết kế này).
- **Phạm vi module**: gộp cả **TTS (đọc từng chương) + hậu kỳ audio (chuẩn hoá loudness + nối chương)** — khớp bước 3 và 4 trong pipeline tổng ở spec kênh. Lý do gộp: kết quả cuối cùng hữu ích ngay (1 file audio dùng được), dễ test end-to-end (script → audio hoàn chỉnh) hơn là tách thành 2 sub-project rời rạc chỉ để xuất audio thô từng chương chưa dùng được ngay.
- **Nhạc nền**: mục "tuỳ chọn" trong spec kênh — **ngoài phạm vi module này**. Có thể thêm ở bước dựng video (Remotion) sau, giữ module TTS gọn, chỉ lo phần giọng đọc.
- **Xử lý độ dài văn bản**: mỗi chương (650–900 từ theo QA của module trước) được đưa vào TTS như một lần gọi riêng — không cần chia nhỏ thêm, vì cấu trúc chương đã có sẵn từ module trước và tài liệu OmniVoice không nêu giới hạn độ dài text/lần gọi.
- **Model load**: model OmniVoice được load một lần (nặng, cần GPU/MPS), tái sử dụng cho toàn bộ các chương trong một lần chạy CLI — không load lại mỗi chương.

## 2. Kiến trúc

```
tts/
├── __init__.py
├── voice_profile.py     # đọc config/voice.yaml -> VoiceProfile (mô tả giọng, target LUFS, sample rate, gap giây)
├── synthesizer.py         # wrap OmniVoice: synthesize_chapter(text, model, voice_profile) -> audio np.ndarray @24kHz
├── audio_postprocess.py   # chuẩn hoá loudness từng chương (pyloudnorm) + nối chương + tính timestamp
├── storage.py              # lưu file .wav (audio hoàn chỉnh) + file .json (timestamp từng chương)
└── cli.py                  # entrypoint: nhận đường dẫn file script JSON, chạy toàn bộ, in kết quả
```

**Luồng xử lý:**

```
[File JSON kịch bản] (input: đường dẫn do người vận hành cung cấp)
   → 1. Load OmniVoice model 1 lần (nếu chưa có model được truyền vào)
   → 2. Với mỗi chương: gọi OmniVoice.generate(text=chapter.text, instruct=voice_profile.instruction)
        → audio np.ndarray @ 24kHz cho chương đó
   → 3. Chuẩn hoá loudness từng đoạn audio chương về target LUFS (config)
   → 4. Nối các đoạn audio đã chuẩn hoá theo đúng thứ tự chương, chèn khoảng lặng ngắn
        (config, mặc định 0.5s) giữa các chương
   → 5. Trong lúc nối, ghi lại timestamp bắt đầu/kết thúc (giây) của từng chương trong
        audio hoàn chỉnh
   → 6. Lưu file .wav (audio hoàn chỉnh) và file .json (metadata: tiêu đề, timestamp
        từng chương) vào output/audio/
```

**Cấu hình** (`config/voice.yaml`, theo đúng pattern `config/tropes.yaml` đã có):

```yaml
instruction: "giọng nữ, ấm áp, tốc độ đọc vừa phải, ngữ điệu tự nhiên như đang kể chuyện cho người nghe"
target_lufs: -16.0
sample_rate: 24000
gap_seconds: 0.5
```

## 3. Testing & vận hành

- **Không load model OmniVoice thật trong test tự động** — model nặng (cần tải về, cần GPU/MPS, khởi tạo chậm), giống nguyên tắc "ngân sách thấp, không tốn tài nguyên thật trong test" đã áp dụng cho module sinh kịch bản (mock Claude/Gemini client). Tests luôn truyền vào một model giả (mock) trả về mảng audio ngắn có kiểm soát được (ví dụ vài trăm sample) để kiểm tra logic nối/chuẩn hoá loudness/timestamp mà không cần chạy inference thật.
- **`pyloudnorm`** dùng để đo và chuẩn hoá loudness (chuẩn ITU-R BS.1770, phổ biến cho audio/podcast) — chạy nhanh trên CPU, không cần GPU, nên test tự động có thể chạy thật với audio ngắn giả lập (sine wave/silence) mà không tốn tài nguyên đáng kể.
- **Smoke test thủ công** (cuối kế hoạch triển khai, không tự động hoá): chạy CLI thật với 1 file script JSON đã có sẵn (ví dụ từ lần chạy module trước), nghe thử audio hoàn chỉnh để xác nhận chất lượng giọng đọc, độ tự nhiên, và không có lỗi ở điểm nối giữa các chương.

## 4. Rủi ro & lưu ý

- **License OmniVoice**: Apache-2.0, dùng thương mại được. README có điều khoản cấm dùng để "giả mạo/lừa đảo giọng người khác" — không áp dụng ở đây vì dùng voice design (mô tả), không clone giọng người thật.
- **Hiệu năng trên Apple Silicon**: chưa được đo thực tế trong thiết kế này — nếu tốc độ sinh audio quá chậm cho khối lượng 2-3 video/tuần, cần đánh giá lại hạ tầng (GPU cloud) ở giai đoạn triển khai/vận hành, không chặn thiết kế module.
- **Chất lượng đọc số/từ viết tắt tiếng Việt**: OmniVoice có thể đọc sai số/ký hiệu/từ viết tắt trong văn bản gốc — không xử lý chuẩn hoá text đặc biệt (number normalization) trong phạm vi thiết kế này; nếu smoke test phát hiện vấn đề rõ rệt, sẽ xử lý ở lần lặp sau.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Nhạc nền/SFX trộn vào audio — để lại cho bước dựng video (Remotion) sau.
- Voice cloning từ audio mẫu cụ thể.
- Xử lý chuẩn hoá số/từ viết tắt trong text trước khi đưa vào TTS.
- Chạy trên GPU cloud (nếu cần sau này khi local không đủ nhanh).
