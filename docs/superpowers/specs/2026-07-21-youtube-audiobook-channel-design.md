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

## 2. Pipeline sản xuất (full tự động)

```
[Kho ý tưởng/trope]
   → 1. LLM sinh kịch bản: outline + full script (~5.000–8.000 từ/tập)
   → 2. Kiểm tra tự động: độ dài, cấu trúc, lọc từ nhạy cảm/vi phạm thương hiệu bên thứ 3
   → 3. OmniVoice TTS: đọc theo giọng đã chọn/thiết kế, xuất audio theo chương
   → 4. Hậu kỳ audio: chuẩn hoá loudness, nối chương, (tuỳ chọn) nhạc nền royalty-free nhẹ
   → 5. Dựng video: ffmpeg ghép ảnh nền/waveform + audio, card tiêu đề, chương mục
   → 6. Sinh metadata: tiêu đề, mô tả, tag, chapters bằng LLM
   → 7. Thumbnail: AI image gen hoặc template cố định (Pillow/Canva API)
   → 8. Upload: YouTube Data API, lên lịch đăng
```

Toàn bộ điều phối bằng một script Python duy nhất. Người vận hành duyệt nhanh (nghe lướt audio + đọc kịch bản) trước khi publish — kể cả ở chế độ full tự động, để chặn nội dung phản cảm/lỗi mà AI có thể tạo ra mà không ai phát hiện.

## 3. Cấu trúc thư mục kỹ thuật

```
audiobook/
├── config/          # kho trope, cấu hình giọng đọc, branding
├── scripts/         # gọi LLM sinh kịch bản
├── tts/             # wrapper OmniVoice
├── video/           # ffmpeg assembly
├── assets/          # ảnh nền, nhạc nền royalty-free
├── metadata/        # sinh title/desc/tag/thumbnail
├── upload/          # YouTube Data API
└── output/          # video thành phẩm
```

## 4. Rủi ro pháp lý & cách giảm thiểu

- **Bản quyền nội dung**: chỉ đạo AI viết truyện *gốc lấy cảm hứng từ trope*, không yêu cầu "chuyển thể" một tác phẩm cụ thể — tránh LLM tái tạo gần nguyên văn tác phẩm có bản quyền.
- **Nhạc nền/SFX**: chỉ dùng nguồn royalty-free (YouTube Audio Library, Pixabay Music) — tránh Content ID strike.
- **Ảnh nền/thumbnail**: dùng ảnh AI tự tạo hoặc stock có giấy phép thương mại, không lấy ảnh chưa rõ nguồn.
- **Công khai nội dung AI**: bật mục khai báo "nội dung tổng hợp/AI-generated" khi upload theo chính sách YouTube.
- **OmniVoice**: Apache-2.0, dùng thương mại được — nhưng nếu clone giọng một người thật/nghệ sĩ lồng tiếng cụ thể, cần được người đó đồng ý (quyền giọng nói).

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
- Thiết kế logo/branding cụ thể.
