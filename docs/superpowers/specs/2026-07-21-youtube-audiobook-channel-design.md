# Thiết kế kênh YouTube truyện audio (lấy cảm hứng từ Phù Mỏ Audio)

**Ngày**: 2026-07-21
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Xây một kênh YouTube đọc truyện audio ngắn, cùng thể loại và định dạng với kênh tham khảo [Phù Mỏ Audio](https://www.youtube.com/@Ph%C3%B9M%E1%BB%8FAudio) (14.9K sub, 250 video, truyện chuyển thể các thể loại "hot": trọng sinh, xuyên không, ngôn tình gia tộc...; video 30–58 phút; views cao 300–400K/video).

Ràng buộc của người thực hiện:
- Làm một mình, ngân sách thấp.
- Lồng tiếng bằng [OmniVoice](https://github.com/k2-fsa/OmniVoice) (TTS zero-shot đa ngôn ngữ, license Apache-2.0, hỗ trợ voice cloning/voice design, tự host).
- Kịch bản/cốt truyện do AI sáng tác, không dịch/chuyển thể nguyên tác có sẵn.
- Muốn pipeline sản xuất full tự động, người vận hành chỉ duyệt trước khi publish.

## 1. Định vị kênh

- **Khác biệt cốt lõi so với kênh mẫu**: AI sáng tác truyện gốc dựa trên các *motif/trope* đang thịnh hành, không chuyển thể tiểu thuyết cụ thể của tác giả nào — giảm rủi ro bản quyền so với mô hình "dịch truyện".
- **Thể loại lõi**: trọng sinh/báo thù, xuyên không, gia tộc hào môn, "phế vật nghịch tập", dưỡng nữ/con nuôi bị hắt hủi rồi phản đòn, tổng tài lạnh lùng sủng vợ, anh chị em ruột tranh sủng.
- **Đối tượng nghe**: nữ 18–45, nghe khi làm việc nhà/lái xe/trước khi ngủ — nội dung phải "nghe được không cần nhìn màn hình" (thoại rõ nhân vật, ít mô tả thị giác thuần tuý).
- **Định dạng video**: audio full 1 tập/truyện, 25–45 phút, ảnh nền tĩnh hoặc pan nhẹ (Ken Burns), tiêu đề dạng "câu hook giật + #Full audio".
- **Tên kênh & thương hiệu**: cần khác hẳn "Phù Mỏ Audio" để tránh nhầm lẫn thương hiệu. Chốt tên, logo, banner ở giai đoạn triển khai (không chặn thiết kế pipeline).

### Phong cách hình ảnh (template video)

Dựa trên bộ ảnh tham khảo do người thực hiện cung cấp, mọi video dùng chung một template gồm:

- **Avatar kênh** (hình tròn, cố định mọi video): nhân vật minh hoạ đặc trưng của kênh — đây là yếu tố nhận diện thương hiệu, cần thiết kế nhất quán qua tất cả video.
- **Icon waveform** nhỏ ngay dưới avatar, báo hiệu đang phát audio.
- **Tiêu đề tập truyện** in nghiêng, ngay dưới waveform.
- **Nền minh hoạ full-khung hình**: tranh watercolor/flat-illustration ấm áp, chủ đề nội thất hoặc thiên nhiên (núi đồi, hồ nước, bãi biển, tiệm sách...), đổi theo từng phân đoạn/chương để tránh nhàm chán khi nghe 25–45 phút. Sinh bằng **Flux**.
- **Caption cháy nền**: phụ đề trắng trên nền pill bán trong suốt, căn giữa, tự động wrap 2 dòng, đồng bộ theo audio — tăng khả năng giữ chân người xem lướt thấy video (kể cả khi tắt tiếng).

## 2. Pipeline sản xuất (full tự động)

```
[Kho ý tưởng/trope]
   → 1. LLM sinh kịch bản: outline + full script (~5.000–8.000 từ/tập), chia theo chương/phân đoạn
   → 2. Kiểm tra tự động: độ dài, cấu trúc, lọc từ nhạy cảm/vi phạm thương hiệu bên thứ 3
   → 3. OmniVoice TTS: đọc theo giọng đã chọn/thiết kế, xuất audio + timestamp theo chương
   → 4. Hậu kỳ audio: chuẩn hoá loudness, nối chương, (tuỳ chọn) nhạc nền royalty-free nhẹ
   → 5. Sinh ảnh nền: Flux tạo tranh minh hoạ theo từng phân đoạn, đúng style template (avatar, nội thất/thiên nhiên ấm áp)
   → 6. Sinh caption: transcript có timestamp (từ script gốc hoặc forced-alignment với audio TTS)
   → 7. Dựng video bằng Remotion: component React ghép avatar + waveform + tiêu đề + ảnh nền Flux (Ken Burns) + audio + caption cháy nền theo template, render ra MP4
   → 8. Sinh metadata: tiêu đề, mô tả, tag, chapters bằng LLM
   → 9. Upload: YouTube Data API, lên lịch đăng
```

Toàn bộ điều phối bằng script orchestration (Python cho script/TTS/ảnh, gọi sang Remotion CLI cho bước dựng video). Người vận hành duyệt nhanh (nghe lướt audio + đọc kịch bản) trước khi publish — kể cả ở chế độ full tự động, để chặn nội dung phản cảm/lỗi mà AI có thể tạo ra mà không ai phát hiện.

## 3. Cấu trúc thư mục kỹ thuật

```
audiobook/
├── config/          # kho trope, cấu hình giọng đọc, branding, style prompt Flux
├── scripts/         # gọi LLM sinh kịch bản
├── tts/             # wrapper OmniVoice
├── images/          # wrapper gọi Flux sinh ảnh nền theo phân đoạn
├── remotion/         # dự án Remotion (React/TS) — component avatar/waveform/caption/Ken Burns, render video
├── assets/          # nhạc nền royalty-free, avatar/logo cố định
├── metadata/        # sinh title/desc/tag/thumbnail
├── upload/          # YouTube Data API
└── output/          # video thành phẩm
```

Lưu ý: đây là dự án lai Python (script gen, TTS, gọi Flux) + Node/TypeScript (Remotion). Script orchestration chính có thể viết bằng Python, gọi `npx remotion render` như một subprocess ở bước dựng video.

## 4. Rủi ro pháp lý & cách giảm thiểu

- **Bản quyền nội dung**: chỉ đạo AI viết truyện *gốc lấy cảm hứng từ trope*, không yêu cầu "chuyển thể" một tác phẩm cụ thể — tránh LLM tái tạo gần nguyên văn tác phẩm có bản quyền.
- **Nhạc nền/SFX**: chỉ dùng nguồn royalty-free (YouTube Audio Library, Pixabay Music) — tránh Content ID strike.
- **Ảnh nền/thumbnail**: dùng ảnh AI tự tạo hoặc stock có giấy phép thương mại, không lấy ảnh chưa rõ nguồn.
- **Công khai nội dung AI**: bật mục khai báo "nội dung tổng hợp/AI-generated" khi upload theo chính sách YouTube.
- **OmniVoice**: Apache-2.0, dùng thương mại được — nhưng nếu clone giọng một người thật/nghệ sĩ lồng tiếng cụ thể, cần được người đó đồng ý (quyền giọng nói).
- **Flux (sinh ảnh)**: `FLUX.1 [dev]` chỉ miễn phí cho mục đích **phi thương mại** — dùng cho kênh kiếm tiền bắt buộc phải mua license thương mại từ Black Forest Labs. `FLUX.1 [schnell]` là Apache-2.0, miễn phí và **được phép dùng thương mại** — mặc định dùng schnell để tránh vi phạm license; nếu cần chất lượng cao hơn dev, cân nhắc trả phí qua API chính thức (BFL API/Replicate/fal.ai) vốn cấp quyền thương mại cho ảnh xuất ra.
- **Remotion**: miễn phí cho cá nhân/nhóm tối đa 3 người kể cả dùng thương mại — phù hợp với việc làm một mình hiện tại; chỉ cần mua license nếu sau này mở rộng đội nhóm ≥4 người.

## 5. Chiến lược tăng trưởng

- **Tần suất đăng**: bắt đầu 2–3 video/tuần để theo dõi retention trước khi tăng tốc, dù pipeline cho phép nhanh hơn — tránh lãng phí khi công thức ăn khách chưa rõ.
- **SEO/thumbnail**: giữ công thức tiêu đề giật + "Full audio" đã được kênh mẫu chứng minh hiệu quả; tổ chức playlist theo thể loại.
- **Shorts**: cắt đoạn cao trào 30–60s từ mỗi video để kéo traffic, tái dùng cùng pipeline audio.
- **Mốc kiếm tiền**: 1.000 sub & 4.000 giờ watch time (hoặc 10 triệu lượt xem Shorts/90 ngày) để bật YouTube Partner Program; sau đó cân nhắc thêm affiliate app đọc truyện.

## 6. Lộ trình

- **Tuần 1–2**: dựng pipeline kỹ thuật (sinh kịch bản, tích hợp OmniVoice, dựng video), test giọng đọc, chốt branding/tên kênh, sản xuất 2–3 video mẫu.
- **Tuần 3**: publish batch đầu, theo dõi CTR/retention.
- **Tháng 2–3**: tối ưu theo dữ liệu thật (thể loại giữ chân tốt, thumbnail CTR cao), tăng tần suất nếu công thức hiệu quả.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Thiết kế chi tiết prompt kỹ thuật cho từng bước LLM (sẽ nằm trong kế hoạch triển khai).
- Chọn nhà cung cấp LLM cụ thể và chi phí API.
- Thiết kế logo/branding cụ thể (avatar nhân vật, tên kênh) — cần chốt trước khi sinh style prompt Flux cố định.
- Chọn nơi chạy Flux (local GPU vs API trả phí) và cấu hình chi tiết prompt/LoRA để giữ phong cách nhất quán qua nhiều video.
- Thiết kế chi tiết component Remotion (layout, animation timing, font, forced-alignment caption).
