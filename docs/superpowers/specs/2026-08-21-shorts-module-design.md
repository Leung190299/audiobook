# Thiết kế module sinh video ngắn (YouTube Shorts) cho mỗi tập truyện

**Ngày**: 2026-08-21
**Trạng thái**: Chờ duyệt

## Bối cảnh & mục tiêu

Pipeline hiện dựng ra một tập dài ~50 phút mỗi lượt chạy, nhưng không có gì kéo người xem mới đến kênh. Module này lấp khoảng trống đó: **mỗi tập dài sinh thêm 1 video dọc 1080×1920, đọc trọn một chương gay cấn nhất** (không phải đoạn trích), kết bằng card kêu gọi nghe trọn tập trên kênh.

Số liệu đo thật từ tập `me_chong_chia_mieng` (16 chương): tốc độ đọc 4.30 từ/giây, chương ngắn nhất 575 từ (2:13), chương dài nhất 908 từ (3:31), trung bình ~700 từ (2:48). Thời lượng thực tế của short vì thế rơi vào khoảng **~2:10 đến ~2:50**, tuỳ chương Gemini chọn.

**Ràng buộc cứng: YouTube Shorts giới hạn 180 giây (3 phút).** Không phải chương nào cũng đủ ngắn để lọt — xem mục Ngân sách thời lượng bên dưới.

Mục tiêu là dẫn lưu lượng từ Shorts về video dài, nên short **không kể trọn câu chuyện** — nó dừng ở chương gay cấn, không phải hai chương kết.

### Ngân sách thời lượng

```
180s (trần Shorts)
  - 4s   card CTA
  - ~6s  khoảng nghỉ giữa câu (~40 câu × 0.15s)
  = 170s cho lời đọc
170s × 4.30 từ/giây ≈ 730 từ
```

Lấy **700 từ** làm trần cứng (`MAX_CHAPTER_WORDS` trong `excerpt.py`) để chừa biên an toàn cho dao động tốc độ đọc giữa các giọng và các câu.

## 1. Quyết định thiết kế

- **Stage độc lập, không nhồi vào stage sẵn có.** Đã cân nhắc mở rộng stage 1/2/4 để chúng sinh luôn phần short. Bác bỏ: làm phình ba stage đang chạy ổn định, và khi short lỗi thì phải chạy lại cả lượt 45 phút. Module riêng chạy lại được độc lập.

- **Chỉ phụ thuộc stage 1 (kịch bản) và stage 3 (ảnh nền).** Không cần audio tập dài, không cần video đã render, không cần metadata SEO. Hệ quả quan trọng: stage này **chạy được ngay cho các tập cũ đã dựng xong** mà không phải dựng lại gì. Vị trí "sau stage 6" chỉ là quy ước vận hành, không phải ràng buộc dữ liệu.

- **TTS lại cả chương thay vì cắt từ file .wav tập dài.** Metadata TTS chỉ có mốc thời gian theo chương (`start_seconds`/`end_seconds`), không có mốc theo câu. Muốn cắt đúng câu trong một chương dài 3-4 phút thì phải ước lượng theo tỉ lệ ký tự — dễ cụt đầu cụt đuôi và phụ đề lệch vài giây. Đọc lại cả chương cho ra âm thanh sạch, cắt đúng câu.

- **Đọc từng câu riêng để có mốc phụ đề thật.** Đây là điểm khác `Caption.tsx` của video dài: component đó chia phụ đề đều theo số ký tự trong chương, nên chữ lệch tiếng. Ở đây, chương được chọn tách thành câu, mỗi câu `synthesize_chapter` một lần, rồi ghép bằng `tts.audio_postprocess.concatenate_chapters` — hàm này vốn đã trả về mốc thời gian cho từng phần tử. Mỗi câu phụ đề vì thế có `startSeconds`/`endSeconds` chính xác. Một chương ~700 từ ra khoảng 40-50 câu (thay vì 8-10 câu của đoạn trích cũ), nên stage 7 chạy lâu hơn hẳn — ước tính ~5 phút thay vì ~1.5 phút trước đây. Đó là dự kiến, không phải lỗi.

- **Không viết code TTS mới.** Dùng lại nguyên `tts.synthesizer.synthesize_chapter`, `tts.audio_postprocess`, `tts.voice_profile` — short vì thế luôn cùng giọng clone với tập dài, và mọi thay đổi ở `config/voice.yaml` tự động áp dụng cho cả hai.

- **Tách câu bằng dấu kết câu** (`.`, `!`, `?`, `…`) thuần túy, mỗi câu thành một dòng phụ đề — câu trong thể loại truyện này vốn ngắn và dứt khoát.

- **`gap_seconds` giữa các câu là 0.15s, không dùng giá trị trong `config/voice.yaml`.** Giá trị ở đó (~0.5s) dành cho khoảng nghỉ giữa các chương; áp vào giữa câu sẽ nghe rời rạc.

- **Dùng lại ảnh nền của chính chương được chọn**, không sinh ảnh mới. Ảnh 1024×576 được phóng lấp khung dọc kèm zoom chậm. Sinh ảnh dọc riêng đẹp hơn về bố cục nhưng tốn thêm ~40 giây mỗi tập, không tương xứng với mức cải thiện.

- **Một lần gọi Gemini duy nhất** trả về cả 4 thứ: số chương được chọn, câu hook, tiêu đề short, mô tả short. Gemini không sinh nội dung đọc — nội dung đó lấy nguyên văn từ kịch bản (xem quyết định bên dưới). Dùng format nhãn dòng-đơn (`CHAPTER:`, `HOOK:`, ...) chứ không JSON — theo đúng tiền lệ `seo_generator.py` và `prompt_generator.py`, vì `gemini-webapi` trả JSON không đủ tin cậy.

- **Stage 7 ghi luôn file metadata riêng cho short.** Short đăng lên YouTube cần tiêu đề và mô tả khác tập dài (kèm `#shorts`), nên không dùng chung được file của stage 6.

- **Gemini chỉ chọn chương, không viết lại nội dung đọc.** Trước đây Gemini trích 120-320 từ để đọc; điều đó tạo ra một nguồn lỗi riêng (đoạn trích sai độ dài) và cần vòng thử lại. Nay short đọc trọn chương nên nội dung đọc luôn là nguyên văn kịch bản — Gemini chỉ cần chọn số chương, không còn nguồn lỗi độ dài đó nữa, và vòng thử lại bị bỏ hẳn.

- **Chỉ cho Gemini chọn trong số chương đủ ngắn (`eligible_chapters`).** Không tăng tốc audio, không chấp nhận video vượt quá 180 giây — xem Ngân sách thời lượng ở trên. Chương nào vượt `MAX_CHAPTER_WORDS` (700 từ) bị loại khỏi danh sách được phép chọn trước khi hỏi Gemini; nếu không còn chương nào đủ ngắn, stage báo lỗi ngay, không âm thầm chọn đại.

- **Loại hai chương cuối khỏi danh sách được chọn (`RESERVED_ENDING_CHAPTERS = 2`).** Đó là phần kết truyện — lấy làm short thì lộ luôn kết cục và mất lý do bấm vào tập dài, đi ngược mục tiêu dẫn lưu lượng của module này.

## 2. Kiến trúc

```
shorts/
├── __init__.py
├── excerpt.py          # Gemini: script -> ShortPick(chapter_index, hook, chapter_text, title, description)
├── props_builder.py    # ShortPick + mốc thời gian + ảnh -> ShortProps cho Remotion
├── storage.py          # lưu output/shorts/<trope>-<ts>.{wav,json,mp4,txt}
└── cli.py              # entrypoint: nhận script_path + images_metadata_path

remotion/src/
├── ShortVideo.tsx      # composition dọc 1080x1920
└── Root.tsx            # (sửa) đăng ký thêm composition ShortVideo
```

**Luồng xử lý:**

```
script.json ────┐
                ├─> excerpt.py ──> ShortPick (chapter_text = nguyên văn chương trong script.json)
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

`ShortPick` (dataclass trong `excerpt.py`):

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `chapter_index` | int | Chương được chọn, 1-based, phải nằm trong danh sách `eligible_chapters(script)` |
| `hook_text` | str | Câu giật tít hiện 3 giây đầu, 4-10 từ |
| `chapter_text` | str | Nội dung đọc — nguyên văn `text` của chương được chọn, lấy từ kịch bản, không phải từ phản hồi Gemini |
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
| `.wav` | Audio cả chương được chọn, đã đọc |
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

- Không chương nào đủ ngắn (`<= MAX_CHAPTER_WORDS`) sau khi loại `RESERVED_ENDING_CHAPTERS` chương cuối — `eligible_chapters` báo lỗi trước cả khi hỏi Gemini, kèm số từ của chương ngắn nhất trong số được xét.
- Gemini trả `chapter_index` ngoài danh sách chương hợp lệ — kể cả khi chương đó tồn tại trong kịch bản (ví dụ nằm trong hai chương kết bị loại).
- Thiếu bất kỳ nhãn nào trong phản hồi Gemini (`CHAPTER`, `HOOK`, `TITLE`, `DESCRIPTION`).
- Lỗi phân tích nhãn hay lỗi gọi API: ném lỗi ngay, không thử lại. Một lần gọi Gemini là đủ — vì Gemini không còn sinh nội dung đọc, nguồn lỗi "sai độ dài" khiến bản thiết kế trước cần thử lại đã không còn tồn tại.
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

- `test_excerpt.py` — parse phản hồi Gemini giả: trường hợp đủ nhãn, thiếu nhãn, `chapter_index` ngoài danh sách hợp lệ (kể cả khi tồn tại trong kịch bản); `eligible_chapters` lọc đúng theo số từ và loại chương kết; `chapter_text` khớp nguyên văn chương trong kịch bản, không đến từ phản hồi Gemini.
- `test_props_builder.py` — mốc thời gian từng câu khớp với timings đầu vào; đường dẫn ảnh trỏ đúng chương được chọn.
- `test_storage.py` — quy tắc đặt tên và nội dung file `.txt`.

Không test render Remotion thật (chậm, cần npm) — theo đúng cách `tests/video/` đang làm.

## 9. Ngoài phạm vi

- Tự động đăng short lên YouTube — giữ nguyên nguyên tắc "không tự động upload" của dự án; stage 8 (upload) chỉ xử lý video dài.
- Sinh nhiều short mỗi tập. Chốt 1 short/tập; muốn 3 thì mở rộng sau bằng cờ `--count`.
- Sinh ảnh dọc riêng cho short.
- Nhạc nền cho short.
