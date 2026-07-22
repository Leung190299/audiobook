# Thiết kế module sinh metadata SEO cho video YouTube

**Ngày**: 2026-07-22
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Sub-project thứ 5 của pipeline kênh YouTube truyện audio (xem [docs/superpowers/specs/2026-07-21-youtube-audiobook-channel-design.md](2026-07-21-youtube-audiobook-channel-design.md)), sau các module sinh kịch bản, TTS, ảnh nền, và dựng video Remotion đã hoàn thành.

Module này nhận đầu ra của 3 stage trước (script JSON, TTS metadata JSON, file video .mp4) và tự động sinh **các thành phần SEO có thể tự động hoá được** cho video, dựa trên checklist SEO YouTube mà người vận hành cung cấp: tiêu đề, mô tả (kèm chapters/timestamps thật), tags, hashtags, và đổi tên file video sang dạng chuẩn SEO — sẵn sàng để người vận hành copy-paste khi upload thủ công lên YouTube Studio.

## 1. Quyết định thiết kế

- **Không tự động upload lên YouTube**: module chỉ sinh **file kết quả** (txt + json) để người vận hành tự dán vào YouTube Studio khi upload thủ công. Tự động upload cần OAuth + YouTube Data API quota, là một sub-project khác, ngoài phạm vi bản thiết kế này.
- **Không tích hợp công cụ nghiên cứu từ khóa trả phí** (TubeBuddy/VidIQ/Semrush/Keyword Tool Dominator) — các công cụ này cần tài khoản/API riêng, không có trong hạ tầng hiện tại. Thay vào đó, **Gemini suy luận từ khóa hợp lý trực tiếp từ nội dung kịch bản** (không có dữ liệu search-volume/cạnh tranh thật) — đây là đánh đổi được chấp nhận, ghi rõ trong rủi ro.
- **Tái sử dụng Gemini-API (gemini-webapi)** đã tích hợp sẵn — cùng pattern với module kịch bản/ảnh: khởi tạo client 1 lần, gọi 1 lần duy nhất cho toàn bộ SEO copy (không cần nhiều lượt vì output tương đối ngắn).
- **Output từ Gemini dùng nhãn cố định, KHÔNG dùng JSON**: yêu cầu Gemini trả về text theo format `TITLE:`, `DESCRIPTION:`, `TAGS:`, `HASHTAGS:` mỗi nhãn 1 dòng/đoạn, sau đó parse bằng split đơn giản. Quyết định này dựa trên bài học đã ghi nhận nhiều lần trong dự án: gemini-webapi (reverse-engineered) không đáng tin cậy khi được yêu cầu trả JSON có cấu trúc (thường kèm giải thích thừa hoặc JSON lồng sai định dạng — xem spec module kịch bản và module ảnh). Nhãn dòng-đơn giản dễ parse robust hơn nhiều.
- **Chapters/timestamps KHÔNG qua Gemini** — tính 100% từ dữ liệu thật đã có trong TTS metadata (`start_seconds` từng chương, đã chính xác tuyệt đối vì lấy trực tiếp từ audio đã lồng tiếng). Tránh để Gemini "bịa" thời gian sai. Code tự ghép `heading` chương + thời gian thành dòng `0:00 <tiêu đề chương>` theo đúng quy tắc YouTube (chương đầu bắt buộc `0:00`).
- **Input cho Gemini là tóm tắt, không phải full text truyện**: chỉ gửi `title` truyện + `trope` + danh sách `heading` của 8 chương (không gửi toàn bộ 5.000-8.000 từ) — đủ ngữ cảnh để sinh description tự nhiên mà giữ prompt gọn, tiết kiệm token/thời gian.
- **CTA (kêu gọi đăng ký kênh) là text cố định do code thêm vào**, không để Gemini tự bịa — đảm bảo nhất quán giữa mọi video, đúng thương hiệu kênh.
- **Đổi tên file MP4 tại chỗ (rename, không phải copy)**: slugify tiêu đề (bỏ dấu tiếng Việt, thay khoảng trắng bằng gạch ngang, chỉ giữ chữ/số/gạch ngang) rồi `Path.rename()` file `.mp4` trong `output/video/` sang tên mới — đúng theo bước "đổi tên tệp trước khi tải lên" của checklist gốc. Không xoá/copy sang chỗ khác.
- **Các phần KHÔNG tự động hoá được** (cần thao tác tay trên YouTube Studio khi upload): tạo thumbnail, thiết lập Cards/End Screens, ghim bình luận, theo dõi tương tác 24-48h đầu, nghiên cứu từ khóa bằng công cụ trả phí, phụ đề .srt riêng (đã loại khỏi phạm vi theo yêu cầu người vận hành). Các mục này được ghi thành **checklist ngắn** trong skill `generating-audiobook-video`, không phải code.

## 2. Kiến trúc

```
metadata/
├── __init__.py
├── chapters.py         # thuần Python: TTS metadata thật -> danh sách dòng "0:00 <heading>"
├── seo_generator.py     # Gemini: title + trope + headings -> title/description/tags/hashtags (parse theo nhãn)
├── filename.py            # slugify tiêu đề -> tên file .mp4 chuẩn SEO, rename file video tại chỗ
├── storage.py               # ghi output/metadata/<trope>-<ts>.txt (dễ đọc) + .json (dữ liệu)
└── cli.py                     # entrypoint: script_path, tts_metadata_path, video_path
```

**Luồng xử lý:**

```
[script JSON] + [TTS metadata JSON] + [video .mp4 path] (input: người vận hành cung cấp)
   → 1. Khởi tạo Gemini client 1 lần
   → 2. Gemini sinh SEO copy 1 lần (title/description-nháp/tags/hashtags) từ
        title + trope + headings 8 chương -> parse theo nhãn TITLE:/DESCRIPTION:/TAGS:/HASHTAGS:
   → 3. Ghép chapters/timestamps thật từ TTS metadata (start_seconds thật) + heading
        -> nối vào cuối description-nháp thành description hoàn chỉnh (kèm CTA cố định)
   → 4. Slugify title -> tên file mp4 mới -> rename file .mp4 tại chỗ trong output/video/
   → 5. Lưu output/metadata/<trope>-<ts>.txt (định dạng dễ đọc để copy-paste)
        + output/metadata/<trope>-<ts>.json (dữ liệu có cấu trúc)
```

**`seo_generator.py`** — `generate_seo_copy(script, gemini_client) -> SeoCopy` (dataclass: `title`, `description_draft`, `tags: list[str]`, `hashtags: list[str]`). Prompt yêu cầu rõ:
- Title: tối đa 70 ký tự, từ khóa chính trong 60 ký tự đầu, không giật tít sai sự thật.
- Description nháp: 200-300+ từ, câu mở đầu (150 ký tự đầu) chứa từ khóa chính.
- Tags: 10-15, phân tách dấu phẩy, thẻ đầu tiên là từ khóa chính xác nhất.
- Hashtags: 2-3, có dấu `#`.
Output parse theo nhãn; nếu thiếu nhãn nào hoặc rỗng → raise lỗi rõ ràng (giống nguyên tắc xử lý lỗi đã áp dụng ở `scene_prompt.py`), không âm thầm dùng giá trị rỗng.

**`chapters.py`** — `build_chapter_lines(script, tts_metadata) -> list[str]`. Format mỗi dòng: `"{mm:ss} {heading}"` (hoặc `h:mm:ss` nếu video >1 giờ). Validate: chương đầu phải `start_seconds == 0` (đúng cấu trúc dữ liệu hiện có — luôn đúng vì TTS luôn bắt đầu chương 1 tại 0), tối thiểu 3 chương (script luôn có 8 chương theo spec kênh, luôn thoả), mỗi chương dài ≥10s (thực tế mỗi chương ~150-200s, luôn thoả) — validate mang tính phòng thủ, không chặn chạy nếu script có ít chương hơn dự kiến trong tương lai, chỉ log cảnh báo.

**`filename.py`** — `slugify(title: str) -> str` (bỏ dấu tiếng Việt qua `unicodedata.normalize("NFD")` + lọc ký tự, lowercase, khoảng trắng/ký tự lạ → `-`, cắt tối đa ~100 ký tự để an toàn) và `rename_video_file(video_path: Path, title: str) -> Path` (rename tại chỗ, trả về path mới).

**`storage.py`** — `save_seo_metadata(trope, seo_copy, chapter_lines, new_video_filename, output_dir) -> tuple[Path, Path]`, ghi `.txt` định dạng:
```
TIÊU ĐỀ:
<title>

MÔ TẢ:
<description hoàn chỉnh kèm chapters + CTA>

TAGS:
<tag1, tag2, ...>

HASHTAGS:
<#tag1 #tag2 ...>

TÊN FILE VIDEO (đã đổi):
<new_filename>.mp4
```
và `.json` chứa cùng dữ liệu ở dạng có cấu trúc.

**`cli.py`** — `uv run python -m metadata.cli <script_path> <tts_metadata_path> <video_path>`, in ra đường dẫn `.txt`/`.json` đã lưu và tên file video mới, theo đúng pattern `print()` các module khác đã dùng.

## 3. Testing & vận hành

- **Không gọi Gemini thật trong test tự động** — dùng client giả, giống nguyên tắc đã áp dụng xuyên suốt dự án.
- Test `chapters.py` bằng dữ liệu TTS giả (không cần audio thật).
- Test `filename.py` với các trường hợp tiếng Việt có dấu, ký tự đặc biệt, tiêu đề rất dài.
- Test `seo_generator.py` parse đúng khi Gemini trả nhãn chuẩn, và raise lỗi rõ ràng khi thiếu nhãn.
- **Smoke test thủ công** (cuối kế hoạch triển khai): chạy CLI thật với 1 bộ script + TTS metadata + video đã có sẵn từ các lần chạy trước, đọc qua file `.txt` sinh ra để xác nhận: title không giật tít sai sự thật, description tự nhiên và đúng nội dung truyện, chapters đúng thời gian thật, tags/hashtags liên quan.

## 4. Rủi ro & lưu ý

- **Chất lượng SEO copy phụ thuộc gemini-webapi**: đã biết kém tin cậy hơn API chính thức (xem ghi chú ở spec module kịch bản) — copy sinh ra cần người vận hành đọc lại trước khi đăng, không tự động đăng thẳng lên YouTube.
- **Từ khóa không có dữ liệu search-volume/cạnh tranh thật**: chỉ là suy luận hợp lý từ nội dung, không thay thế được nghiên cứu bằng công cụ chuyên dụng — chấp nhận đánh đổi này ở giai đoạn hiện tại.
- **Không tự động**: thumbnail, Cards/End Screens, ghim bình luận, theo dõi tương tác đầu 24-48h, phụ đề .srt riêng — cần checklist tay, ghi trong skill `generating-audiobook-video`, không phải trong module này.
- **Rename file video là thao tác không thể hoàn tác dễ dàng qua path cũ** — nhưng an toàn vì chỉ đổi tên tại chỗ (không xoá nội dung), và metadata JSON lưu lại tên file mới rõ ràng.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Tự động upload video + metadata lên YouTube qua YouTube Data API (cần OAuth, quota riêng).
- Tích hợp công cụ nghiên cứu từ khóa trả phí (TubeBuddy/VidIQ/Semrush).
- Tạo thumbnail tự động.
- Sinh file phụ đề `.srt` riêng để upload lên YouTube (đã loại khỏi phạm vi theo yêu cầu người vận hành lần này — có thể làm ở lần lặp sau, tái sử dụng `video/captions.py` đã có).
- Thiết lập Cards/End Screens, ghim bình luận, theo dõi/chatbot trả lời bình luận tự động.
