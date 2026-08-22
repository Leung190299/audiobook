# Thiết kế module sinh video ngắn (YouTube Shorts) cho mỗi tập truyện

**Ngày**: 2026-08-21
**Trạng thái**: Chờ duyệt

## Bối cảnh & mục tiêu

Pipeline hiện dựng ra một tập dài ~50 phút mỗi lượt chạy, nhưng không có gì kéo người xem mới đến kênh. Module này lấp khoảng trống đó: **mỗi tập dài sinh thêm 1 video dọc 1080×1920 dài khoảng 60-80 giây**, trích đúng chương gay cấn nhất, kết bằng card kêu gọi nghe trọn tập trên kênh.

Mục tiêu là dẫn lưu lượng từ Shorts về video dài, nên short **không kể trọn câu chuyện** — nó cắt ở cao trào.

## 1. Quyết định thiết kế

- **Stage độc lập, không nhồi vào stage sẵn có.** Đã cân nhắc mở rộng stage 1/2/4 để chúng sinh luôn phần short. Bác bỏ: làm phình ba stage đang chạy ổn định, và khi short lỗi thì phải chạy lại cả lượt 45 phút. Module riêng chạy lại được độc lập.

- **Chỉ phụ thuộc stage 1 (kịch bản) và stage 3 (ảnh nền).** Không cần audio tập dài, không cần video đã render, không cần metadata SEO. Hệ quả quan trọng: stage này **chạy được ngay cho các tập cũ đã dựng xong** mà không phải dựng lại gì. Vị trí "sau stage 6" chỉ là quy ước vận hành, không phải ràng buộc dữ liệu.

- **TTS lại đoạn trích thay vì cắt từ file .wav tập dài.** Metadata TTS chỉ có mốc thời gian theo chương (`start_seconds`/`end_seconds`), không có mốc theo câu. Muốn cắt đúng câu trong một chương dài 3-4 phút thì phải ước lượng theo tỉ lệ ký tự — dễ cụt đầu cụt đuôi và phụ đề lệch vài giây. Đọc lại đoạn trích cho ra âm thanh sạch, cắt đúng câu, chỉ tốn thêm ~1 phút.

- **Đọc từng câu riêng để có mốc phụ đề thật.** Đây là điểm khác `Caption.tsx` của video dài: component đó chia phụ đề đều theo số ký tự trong chương, nên chữ lệch tiếng. Ở đây, đoạn trích được tách thành câu, mỗi câu `synthesize_chapter` một lần, rồi ghép bằng `tts.audio_postprocess.concatenate_chapters` — hàm này vốn đã trả về mốc thời gian cho từng phần tử. Mỗi câu phụ đề vì thế có `startSeconds`/`endSeconds` chính xác. Đoạn trích ~180 từ chỉ 8-10 câu nên không chậm thêm đáng kể.

- **Không viết code TTS mới.** Dùng lại nguyên `tts.synthesizer.synthesize_chapter`, `tts.audio_postprocess`, `tts.voice_profile` — short vì thế luôn cùng giọng clone với tập dài, và mọi thay đổi ở `config/voice.yaml` tự động áp dụng cho cả hai.

- **Tách câu bằng dấu kết câu** (`.`, `!`, `?`, `…`) thuần túy, mỗi câu thành một dòng phụ đề — câu trong thể loại truyện này vốn ngắn và dứt khoát.

- **`gap_seconds` giữa các câu là 0.15s, không dùng giá trị trong `config/voice.yaml`.** Giá trị ở đó (~0.5s) dành cho khoảng nghỉ giữa các chương; áp vào giữa câu sẽ nghe rời rạc.

- **Dùng lại ảnh nền của chính chương được trích**, không sinh ảnh mới. Ảnh 1024×576 được phóng lấp khung dọc kèm zoom chậm. Sinh ảnh dọc riêng đẹp hơn về bố cục nhưng tốn thêm ~40 giây mỗi tập, không tương xứng với mức cải thiện.

- **Một lần gọi Gemini duy nhất** trả về cả 5 thứ: số chương được chọn, câu hook, đoạn trích, tiêu đề short, mô tả short. Dùng format nhãn dòng-đơn (`CHAPTER:`, `HOOK:`, ...) chứ không JSON — theo đúng tiền lệ `seo_generator.py` và `prompt_generator.py`, vì `gemini-webapi` trả JSON không đủ tin cậy.

- **Stage 7 ghi luôn file metadata riêng cho short.** Short đăng lên YouTube cần tiêu đề và mô tả khác tập dài (kèm `#shorts`), nên không dùng chung được file của stage 6.

## 2. Kiến trúc

```
shorts/
├── __init__.py
├── excerpt.py          # Gemini: script -> ShortExcerpt(chapter_index, hook, excerpt, title, description)
├── props_builder.py    # ShortExcerpt + mốc thời gian + ảnh -> ShortProps cho Remotion
├── storage.py          # lưu output/shorts/<trope>-<ts>.{wav,json,mp4,txt}
└── cli.py              # entrypoint: nhận script_path + images_metadata_path

remotion/src/
├── ShortVideo.tsx      # composition dọc 1080x1920
└── Root.tsx            # (sửa) đăng ký thêm composition ShortVideo
```

**Luồng xử lý:**

```
script.json ────┐
                ├─> excerpt.py ──> ShortExcerpt
images.json ────┘                      │
                                       v
                         tách câu -> synthesize_chapter (từng câu)
                                       │
                                       v
                    concatenate_chapters -> audio + mốc từng câu
                                       │
                                       v
                         props_builder -> short-props.json
                                       │
                                       v
                    npx remotion render ShortVideo -> .mp4
                                       │
                                       v
                              storage -> .txt metadata
```

## 3. Hợp đồng dữ liệu

`ShortExcerpt` (dataclass trong `excerpt.py`):

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `chapter_index` | int | Chương được chọn, 1-based, phải tồn tại trong kịch bản |
| `hook_text` | str | Câu giật tít hiện 3 giây đầu, 4-10 từ |
| `excerpt_text` | str | Đoạn trích để đọc, 120-320 từ |
| `short_title` | str | Tiêu đề đăng short, ≤100 ký tự |
| `short_description` | str | Mô tả short, có CTA và `#shorts` |

`ShortProps` (JSON truyền cho Remotion):

```ts
interface ShortProps {
  trope: string;
  title: string;          // tên tập dài, hiện ở card cuối
  audioPath: string;
  imagePath: string;
  hookText: string;
  captions: { text: string; startSeconds: number; endSeconds: number }[];
  audioDurationSeconds: number;
  ctaSeconds: number;     // 4
}
```

Thời lượng composition = `audioDurationSeconds + ctaSeconds`.

`audioPath` và `imagePath` là đường dẫn tương đối so với gốc repo, và Remotion được gọi kèm `--public-dir=<repo_root>` — giống hệt cách `video/props_builder.py` và `video/cli.py` đang làm.

## 4. Bố cục hình ảnh

- **Nền**: ảnh chương, `object-fit: cover` lấp 1080×1920, zoom chậm từ 1.0 đến 1.08 suốt thời lượng; phủ gradient tối từ trên xuống và dưới lên để chữ luôn đọc được.
- **3 giây đầu**: `hookText` cỡ lớn, đậm, canh giữa vùng trên.
- **Suốt thời lượng**: phụ đề ở giữa dưới, đổi theo mốc thật của từng câu, nền mờ bo góc như `Caption.tsx` nhưng cỡ chữ lớn hơn nhiều cho khung dọc.
- **4 giây cuối**: card CTA — nền tối, tên tập đầy đủ, dòng "Nghe full trên kênh".

Font dùng `assets/fonts/BeVietnamPro-Black.ttf` đã có sẵn trong repo.

## 5. Đầu ra

Tất cả nằm trong `output/shorts/`, đặt tên theo `<trope>-<timestamp>`:

| File | Nội dung |
|---|---|
| `.wav` | Audio đoạn trích đã đọc |
| `-props.json` | Props truyền cho Remotion (lưu vết) |
| `.mp4` | Video dọc hoàn chỉnh |
| `.txt` | Tiêu đề + mô tả + hashtag, sẵn sàng copy-paste |

stdout in ra:

```
Đã render short: output/shorts/<trope>-<ts>.mp4
Metadata short: output/shorts/<trope>-<ts>.txt
```

## 6. Xử lý lỗi

Mọi trường hợp dưới đây dừng stage với thông báo tiếng Việt rõ ràng, không render ra short hỏng:

- Gemini trả `chapter_index` ngoài phạm vi chương của kịch bản.
- Đoạn trích ngoài khoảng 120-320 từ sau **hai** lần hỏi Gemini. Lần đầu sai độ dài
  thì hỏi lại một lần với yêu cầu độ dài gắt hơn — đo thực tế cho thấy Gemini vượt
  trần ở phần lớn lượt đầu. Lỗi phân tích nhãn hay lỗi API thì KHÔNG thử lại.
- Thiếu bất kỳ nhãn nào trong phản hồi Gemini.
- File ảnh của chương được chọn không tồn tại trong thư mục ảnh.
- Remotion trả mã lỗi, hoặc trả mã thành công nhưng không có file — bắt cả hai như `video/cli.py` đang làm.

## 7. Ghép vào pipeline

`run_daily.sh` thêm **Stage 7: Short**, đẩy upload YouTube thành **Stage 8**.

Bốn chỗ khác cùng parse stdout theo chuỗi cố định, phải sửa đồng bộ nếu không dây chuyền đứt âm thầm:

- `tests/fake_stage.sh` — thêm nhánh in đúng định dạng stdout của stage 7.
- `tests/test_run_daily.py` — mở rộng để bao stage mới.
- `n8n/audiobook-pipeline.workflow.json` — workflow thay thế, parse cùng chuỗi.
- `.claude/skills/generating-audiobook-video/SKILL.md` — bảng stage và số thứ tự upload.

## 8. Kiểm thử

Thêm `tests/shorts/` theo đúng khuôn `tests/thumbnail/`:

- `test_excerpt.py` — parse phản hồi Gemini giả: trường hợp đủ nhãn, thiếu nhãn, `chapter_index` sai phạm vi, đoạn trích quá ngắn/quá dài.
- `test_props_builder.py` — mốc thời gian từng câu khớp với timings đầu vào; đường dẫn ảnh trỏ đúng chương được chọn.
- `test_storage.py` — quy tắc đặt tên và nội dung file `.txt`.

Không test render Remotion thật (chậm, cần npm) — theo đúng cách `tests/video/` đang làm.

## 9. Ngoài phạm vi

- Tự động đăng short lên YouTube — giữ nguyên nguyên tắc "không tự động upload" của dự án; stage 8 (upload) chỉ xử lý video dài.
- Sinh nhiều short mỗi tập. Chốt 1 short/tập; muốn 3 thì mở rộng sau bằng cờ `--count`.
- Sinh ảnh dọc riêng cho short.
- Nhạc nền cho short.
