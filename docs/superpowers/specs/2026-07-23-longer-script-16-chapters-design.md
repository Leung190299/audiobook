# Thiết kế: mở rộng kịch bản từ 8 lên 16 chương

**Ngày**: 2026-07-23
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Pipeline hiện sinh truyện **8 chương, ~6.000 từ, video ~25 phút**. Người vận hành muốn truyện **dài hơn và có chiều sâu hơn** để tăng sức hút, lấy tham chiếu là các kênh truyện audio Việt cùng thể loại (ví dụ video *"Nữ Thần Học Bá Nổi Danh Hoá Ra Lại Là Đồ Gian Lận"* — kênh Dứa Audio; **không lấy được thời lượng video đó qua web**, nên các con số dưới đây suy ra từ chính dữ liệu đo được của dự án, không phải từ kênh tham chiếu).

Mục tiêu: **16 chương × 650-800 từ = ~10.400-12.800 từ ≈ 42-51 phút video** — gấp đôi nội dung so với hiện tại, thêm chiều sâu thật sự (nhiều tình tiết/diễn biến hơn) chứ không chỉ chia nhỏ cùng một lượng chữ.

## 1. Quyết định thiết kế

- **Số chương cố định chính xác 16, đặt thành hằng số** trong `scripts/prompts.py`, nội suy vào prompt — thay vì viết cứng số 8 ở 3 chỗ như hiện nay. Không dùng khoảng ("15-18 chương") vì gemini-webapi (reverse-engineered) đã nhiều lần cho thấy kém tin cậy khi theo chỉ dẫn phức tạp; prompt hiện tại nói "đúng 8 chương" và Gemini tuân thủ tốt, nên giữ nguyên dạng chỉ dẫn đó, chỉ đổi con số. Cố định cũng giúp thời lượng video dự đoán được giữa các tập. Không đưa vào file config YAML (như `voice.yaml`) — thêm hạ tầng cho một tham số hiếm khi đổi, vi phạm YAGNI; hằng số trong code đã đủ để lần sau chỉnh 1 dòng.
- **Giữ nguyên 650-800 từ/chương**: đây là mức đã kiểm chứng qua thực tế (chương sinh ra ~180-200 giây audio mỗi chương, đều đặn). Tăng chiều sâu bằng cách thêm chương, không phải kéo dài từng chương.
- **Không đổi code các module phía sau**: `scripts/generator.py` đã hoàn toàn động (dùng `len(chapter_plans)` từ outline, truyền `total_chapters` vào prompt từng chương); `images/`, `tts/`, `video/`, `metadata/`, `thumbnail/` đều lặp theo số chương thực tế đọc từ script JSON. Không có chỗ nào khác khoá cứng số 8.
- **Nới ngưỡng QA theo đúng biên độ hiện có**: thiết kế cũ đặt mục tiêu 8 chương và cho QA chấp nhận 6-10 (biên độ ±2). Giữ nguyên nguyên tắc đó quanh mục tiêu mới.
- **Sửa luôn 2 con số thời gian sai trong skill doc**: đo lại từ lần chạy pipeline thật ngày 2026-07-22 cho thấy skill đang ghi sai đáng kể (xem mục 4). Đây không phải phạm vi phát sinh — skill là tài liệu vận hành sống, số sai sẽ khiến người vận hành hiểu nhầm là pipeline bị treo.
- **Chỉ cập nhật tài liệu "sống", giữ nguyên hồ sơ lịch sử**: skill doc và spec thiết kế kênh là chuẩn hiện hành → cập nhật. Các spec module cũ (`flux-images`, `seo-metadata`, `thumbnail`, `images-mflux-migration`...) có nhắc "8 chương" là hồ sơ ghi lại quyết định tại thời điểm thiết kế module đó → **giữ nguyên**, sửa hết sẽ thành nhiễu và làm mất giá trị lịch sử của chúng.

## 2. Thay đổi code

**`scripts/prompts.py`** — thêm 2 hằng số ở đầu module và nội suy vào cả 3 chỗ đang viết cứng:

```python
TARGET_CHAPTERS = 16
TOTAL_WORDS_RANGE = "10.000–13.000"
```

Ba chỗ cần nội suy:
1. `SYSTEM_PROMPT`: `"Độ dài: 5.000–8.000 từ tiếng Việt."` → dùng `TOTAL_WORDS_RANGE`; `"Chia thành đúng 8 chương"` → dùng `TARGET_CHAPTERS`.
2. `build_outline_prompt`: `"Đúng 8 chương, mỗi chương có: ..."` → dùng `TARGET_CHAPTERS`.
3. `build_outline_prompt`, phần mô tả JSON: `"CHÍNH XÁC 8 object phẳng"` → dùng `TARGET_CHAPTERS`.

`build_chapter_prompt` **không đổi** — đã nhận `total_chapters` làm tham số.

**`scripts/qa.py`** — nới ngưỡng:

| Hằng số | Cũ | Mới | Lý do |
|---|---|---|---|
| `MIN_WORDS` | 5000 | 9000 | dưới mục tiêu 10.400 một biên an toàn |
| `MAX_WORDS` | 8000 | 14000 | trên mục tiêu 12.800 một biên an toàn |
| `MIN_CHAPTERS` | 6 | 14 | mục tiêu 16, biên độ −2 (giữ đúng nguyên tắc cũ) |
| `MAX_CHAPTERS` | 10 | 18 | mục tiêu 16, biên độ +2 |

## 3. Thay đổi tài liệu

**`.claude/skills/generating-audiobook-video/SKILL.md`**:
- Mục "Parallel TTS": `"Running all 8 chapters"` → 16 chương; ví dụ batching `[2,3], [4,5], [6,7], [8]` → 8 lượt cặp cho 16 chương.
- **Sửa số liệu thời gian sai** (xem mục 4 để biết số đo thật).
- Mục "Common Mistakes": câu về `"each of the 8 chapters (~20-25 min total for stage 3)"` → 16 chương + thời gian đã sửa.

**`docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md`** (3 dòng):
- Dòng 21: `"25–45 phút"` → `"40–55 phút"`.
- Dòng 31: `"nhàm chán khi nghe 25–45 phút"` → `"40–55 phút"`.
- Dòng 38: `"~5.000–8.000 từ/tập"` → `"~10.000–13.000 từ/tập"`.

## 4. Số liệu thời gian thật (đo từ lần chạy pipeline 2026-07-22)

Skill doc đang ghi sai; đây là số đo thật cần thay vào:

| Giai đoạn | Skill doc đang ghi | Đo thật (8 chương) | Suy ra cho 16 chương |
|---|---|---|---|
| TTS, chạy 2 chương song song | "solo ~20-31 phút → ~44-54 phút khi chạy cặp" | **~24 phút mỗi cặp** (4 lượt, tổng ~1.6 giờ) | 8 lượt ≈ **~3.2 giờ** |
| Sinh ảnh nền (stage 3) | "~20-25 phút" | **~5 phút** (8 ảnh) | ~10 phút (16 ảnh) |
| Sinh kịch bản (stage 1) | (không ghi) | **~100 giây** (outline + 8 chương) | ~3,5 phút (outline + 16 chương) |
| Render video (stage 4) | (không ghi) | **~10 phút** cho video 25 phút | ~20 phút cho video ~45 phút |

Nguồn: mốc thời gian trong tên file output và log của lần chạy `xuyen_khong_gia_toc` ngày 2026-07-22.

## 5. Testing

- **`tests/scripts/test_prompts.py`**:
  - `test_build_outline_prompt_includes_trope_details`: assert `"8 chương" in prompt` → `"16 chương"`. Dùng **chuỗi literal `"16 chương"`, không dùng `TARGET_CHAPTERS`** — để test ghi lại giá trị chủ đích, và bất kỳ ai đổi hằng số sau này buộc phải sửa test một cách có ý thức (nếu assert qua hằng số thì test luôn xanh dù giá trị đổi thành gì, mất tác dụng cảnh báo).
  - Thêm assert `"10.000–13.000" in prompt` — cùng lý do: chốt lại khoảng tổng số từ chủ đích. Lưu ý đây chỉ là chốt giá trị, **không** phải kiểm tra `TARGET_CHAPTERS` và `TOTAL_WORDS_RANGE` có nhất quán về mặt số học với nhau (`TOTAL_WORDS_RANGE` là chuỗi hiển thị, không parse được thành số để so).
  - `test_build_chapter_prompt_enforces_minimum_words`: **giữ nguyên** — nó gọi `build_chapter_prompt(3, 8, ...)` với tham số tuỳ ý và hàm này không đổi.
- **`tests/scripts/test_qa.py`**: cập nhật toàn bộ fixture sang ngưỡng mới — các case hợp lệ dùng ~16 chương/~11.000 từ; các case biên (quá ngắn, quá dài, quá ít chương, quá nhiều chương) dịch theo ngưỡng mới. Giữ nguyên cấu trúc test, chỉ đổi số.
- **`tests/scripts/test_generator.py`**: **giữ nguyên 8 chương**, không đổi. Test này chứng minh generator lặp đúng theo *bất kỳ* số chương nào outline trả về — để nguyên số khác 16 chính là bằng chứng nó không khoá cứng con số mục tiêu.
- **Không gọi Gemini thật trong test tự động** — giữ nguyên nguyên tắc xuyên suốt dự án.
- **Smoke test thủ công** (bắt buộc, cuối kế hoạch): chạy `scripts.cli` thật với 1 trope, rồi kiểm tra:
  1. Đúng 16 chương, tổng từ nằm trong 9.000-14.000 (QA tự chặn nếu không).
  2. **Đọc kỹ 3 chương cuối (14, 15, 16)** — kiểm tra tên nhân vật, bối cảnh, mạch thời gian còn nhất quán với chương đầu, không bị trôi. Đây là rủi ro chính của việc tăng số chương (xem mục 6).
  3. Cao trào và kết thúc vẫn rõ ràng, không bị dàn trải/lê thê vì kéo dài gấp đôi.

## 6. Rủi ro & lưu ý

- **Gemini mất nhất quán ở các chương cuối** (rủi ro chính): 16 chương tích luỹ ~11.000 từ ngữ cảnh trong một phiên chat duy nhất. Chương 14-16 có thể trôi tên nhân vật, mâu thuẫn mốc thời gian, hoặc chất lượng văn giảm. Chưa từng chạy thử ở quy mô này nên chưa biết mức độ — bắt buộc kiểm tra ở smoke test. Nếu thực sự trôi, hướng xử lý ở lần lặp sau (ngoài phạm vi): tóm tắt lại bối cảnh vào prompt mỗi vài chương, hoặc chia thành nhiều phiên chat.
- **Gemini trả sai số chương**: QA chặn ở biên 14-18 và báo lỗi rõ ràng, không âm thầm chạy tiếp với script hỏng.
- **TTS tăng lên ~3.2 giờ/video**: đây là giai đoạn chậm nhất và chi phối tổng thời gian pipeline. Với nhịp 2-3 video/tuần nghĩa là ~6.5-10 giờ TTS/tuần trên máy vận hành.
- **Video 42-51 phút vượt định dạng 25-45 phút cũ**: dài hơn có thể tăng tổng watch-time nhưng cũng có thể giảm tỷ lệ xem hết. Không có dữ liệu để dự đoán trước — cần theo dõi retention thật sau vài tập rồi điều chỉnh `TARGET_CHAPTERS` nếu cần (giờ chỉ là sửa 1 hằng số).
- **Không có rủi ro tương thích ngược**: các file output 8 chương đã sinh trước đó vẫn dùng bình thường ở mọi stage — mọi module đọc số chương động từ file, không giả định con số nào.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Chống trôi ngữ cảnh cho Gemini khi sinh nhiều chương (tóm tắt lại bối cảnh định kỳ, chia nhiều phiên chat) — chỉ làm nếu smoke test cho thấy thật sự cần.
- Khả năng resume/sinh lại từng chương riêng lẻ khi Gemini lỗi giữa chừng (hiện tại lỗi ở chương bất kỳ sẽ mất cả lần chạy — chấp nhận được vì stage 1 chỉ mất ~3,5 phút).
- Cập nhật các spec module lịch sử có nhắc "8 chương" — xem mục 1.
- Tối ưu tốc độ TTS (GPU cloud, model khác) để bù phần thời gian tăng thêm.
