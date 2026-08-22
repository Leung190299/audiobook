# Thiết kế lại: short thành series cắt từ cả tập

**Ngày**: 2026-08-22
**Trạng thái**: Đã triển khai
**Thay thế**: [2026-08-21-shorts-module-design.md](2026-08-21-shorts-module-design.md) ở phần chọn nội dung; giữ nguyên phần bố cục hình ảnh và composition Remotion.

## Vì sao phải làm lại

Bản đầu chọn một chương gay cấn nhất rồi đọc trọn chương đó. Đo trên toàn bộ 14 tập đã dựng cho thấy cách đó không dùng được:

| | |
|---|---|
| Chương trung bình | ~800 từ ≈ **3:06** |
| Chương ngắn nhất mỗi tập, trung bình | 708 từ ≈ 2:45 |
| Số tập có ít nhất một chương ≤700 từ, không tính hai chương cuối | **3/14** |

Trần Shorts là 180 giây, nên một chương trọn vẹn của kênh này về cơ bản không lọt. Tập `me_chong_chia_mieng` chạy được chỉ vì nó có chương ngắn bất thường — trần 700 từ ở bản trước được suy ra từ đúng một tập đó, là sai về phương pháp.

Hướng giải quyết đã chốt: **không ép một chương vừa một short, mà cắt cả tập thành một series short đánh số**.

## Hình dạng mới

Mỗi tập sinh ra **~30 short**, mỗi cái 85-165 giây, đánh số liên tiếp `Phần 1` … `Phần N`. Người xem có thể theo dõi trọn truyện trên Shorts, hoặc bấm sang tập dài để nghe một mạch.

Cách cắt: **gói các câu liên tiếp trong cùng một chương** cho tới khi thêm câu kế tiếp sẽ vượt ngân sách, rồi mở phần mới. **Không bắc cầu qua ranh giới chương** — mỗi phần vì thế giữ đúng ảnh nền của chương chứa nó, và không có phần nào ghép hai bối cảnh khác nhau.

```
180s (trần Shorts)
  - 4s   card CTA
  - biên an toàn
  = 165s ngân sách lời đọc mỗi phần
```

Một chương ~800 từ (186 giây) vì thế tách thành 2 phần ~93 giây; chương ≤165 giây giữ nguyên một phần.

## Quyết định thiết kế

- **Stage 2 đọc theo câu thay vì theo chương.** Đây là thay đổi gốc rễ, mọi thứ khác theo sau. Trước đây stage 7 phải đọc lại nội dung mà stage 2 vừa đọc, chỉ để có mốc thời gian theo câu. Nay stage 2 tự ghi mốc từng câu, nên stage 7 chỉ cắt file có sẵn — không TTS lại lần nào. Lượt chạy hằng ngày vì thế không dài thêm dù sinh 30 short.

- **Chuẩn hoá độ ồn một lần trên toàn tập, không theo câu.** `pyloudnorm` ném lỗi với mọi đoạn dưới 0.4 giây, và đo LUFS trên một câu là vô nghĩa. Đây đúng là lỗi đã gặp và sửa ở stage 7 bản trước; stage 2 phải tránh lặp lại. Khác biệt so với hiện tại: trước đây stage 2 chuẩn hoá từng chương rồi mới ghép, nay ghép hết rồi chuẩn hoá một lần — bỏ luôn hiện tượng chênh mức giữa các chương.

- **Phụ đề video dài cũng dùng mốc câu thật.** Khi stage 2 đã có mốc từng câu thì `Caption.tsx` không còn lý do gì để chia đều theo số ký tự. Đây là khiếm khuyết đã biết từ đầu dự án, nay sửa được gần như miễn phí.

- **Bỏ Gemini khỏi stage 7.** Với ~30 phần mỗi tập, không thể nhờ Gemini viết hook/tiêu đề cho từng phần. Tiêu đề thành `<tên tập> — Phần N`, hook lấy tiêu đề chương (vốn đã giật gân sẵn), mô tả theo mẫu. Hệ quả tốt: stage 7 hết sạch lỗi Gemini, chạy được cả khi cookie hết hạn, và thành một stage thuần tính toán — kiểm thử dễ hơn hẳn.

- **Bỏ luật loại hai chương cuối.** Đăng cả tập thành series thì kết cục nằm trong series là đương nhiên.

- **Card CTA đổi nghĩa**: dẫn sang phần tiếp theo, kèm lời mời nghe trọn tập trên kênh. Phần cuối cùng chỉ mời nghe trọn tập.

- **Stage 7 mất khả năng chạy cho tập cũ.** Nó cần mốc câu, mà metadata TTS của các tập đã dựng trước đây chỉ có mốc chương. Muốn làm short cho tập cũ thì phải chạy lại stage 2 cho tập đó. Chấp nhận đánh đổi này để không phải TTS hai lần mỗi ngày.

## Hợp đồng dữ liệu

`output/audio/<trope>-<ts>.json` thêm mảng `sentences`, giữ nguyên `chapters` để stage 4 và stage 6 không phải đổi:

```json
{
  "trope": "...", "title": "...", "sample_rate": 48000,
  "chapters":  [{"index": 1, "heading": "...", "start_seconds": 0.0, "end_seconds": 211.3}],
  "sentences": [{"chapter_index": 1, "index": 1, "text": "...",
                 "start_seconds": 0.0, "end_seconds": 3.9}]
}
```

`output/shorts/` mỗi phần một bộ file, đánh số hai chữ số để sắp xếp đúng thứ tự:

```
<trope>-<ts>-part-01.wav
<trope>-<ts>-part-01-props.json
<trope>-<ts>-part-01.mp4
<trope>-<ts>-part-01.txt
```

`shorts.cli` nhận **hai** đường dẫn: TTS metadata JSON và images metadata JSON. Không cần script JSON — metadata TTS đã chứa `trope`, `title`, heading từng chương và text từng câu, nên truyền thêm script chỉ tạo thêm một chỗ để truyền nhầm. stdout in một dòng cho mỗi phần, theo đúng thứ tự phần:

```
Đã render short: output/shorts/<trope>-<ts>-part-01.mp4
Metadata short: output/shorts/<trope>-<ts>-part-01.txt
...
Đã render 30 short vào output/shorts
```

Dòng tổng kết ở cuối cho `run_daily.sh` biết số lượng để ghi log và kiểm tra.

## Ngoài phạm vi

- Tự động đăng series lên YouTube.
- Sinh ảnh riêng cho từng phần (vẫn dùng ảnh của chương chứa phần đó).
- Nhạc nền.
- Làm lại short cho 13 tập cũ — cần chạy lại stage 2 cho từng tập, là việc riêng người vận hành tự quyết.
