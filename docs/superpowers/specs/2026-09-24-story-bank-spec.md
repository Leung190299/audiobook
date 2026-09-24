# Spec: Pipeline audiobook đọc kho 100 truyện (story_bank.json) — 24/09/2026

Repo `/Users/lee/Project/Apps/audiobook`, làm tiếp trên nhánh `feat/topics-full-format`.
Kế thừa: `2026-09-24-topics-full-format-spec.md` (3 chủ đề + định dạng FULL đã làm).

## Mục tiêu
Hiện Stage 1 tự chọn bối cảnh trong `scripts/topics.py` rồi để Gemini nghĩ tiêu đề và cốt truyện. Từ nay truyện lấy từ kho biên tập sẵn `data/story_bank.json`. Pipeline dùng đúng tiêu đề, hook, câu hỏi, từ khoá thumbnail và dàn ý (nếu có) của kho. Chế độ cũ `--topic` vẫn giữ làm dự phòng.

## Cấu trúc `data/story_bank.json` (đã có sẵn, không sửa tay trong code)
- `writing_rules`: luật viết chung → chèn vào prompt Stage 1.
- `series`: `{ "<tên series>": {topic, narrator, cast{tên: tính cách}, setting} }` → nếu truyện thuộc series, chèn nguyên khối vào prompt để giữ tên và tính cách nhân vật nhất quán giữa các truyện.
- `stories[]`: `id, topic, series, title, premise, twist, hook, comment_question, thumb_keywords[], timing, priority (A/B/C), publish_date (YYYY-MM-DD hoặc null), outline[] (tuỳ chọn, 16 chương)`.

## Thay đổi

1. **`scripts/story_bank.py` (mới)**
   - `load_bank()`, `get_story(id)`.
   - `pick_story(date)`: trả về truyện có `publish_date == date`. Nếu không có: chọn truyện ưu tiên A, rồi B, chưa dùng, đúng chủ đề của ngày theo `AUDIOBOOK_TOPIC_ROTATION`. Bỏ qua truyện có `timing` "Trước Tết" trừ khi ngày nằm trong 04/01–05/02/2027. Không chọn C trừ khi hết A/B.
   - State tách riêng `output/story_bank_state.json` (`{id: {status, video_id, published_at}}`); không ghi vào story_bank.json.

2. **`run_daily.sh`**
   - Thêm `--story <id|auto>`. `auto` = `pick_story(ngày phát sóng kế tiếp lúc 20h, giờ Asia/Saigon)`.
   - Không truyền `--story`, `--topic` hay `--trope` → mặc định `--story auto`. Nếu kho không còn truyện phù hợp, rơi về `--topic auto` và in cảnh báo.
   - Thêm `--dry-run-pick`: chỉ in truyện sẽ được chọn cho 7 ngày tới rồi thoát (để kiểm tra lịch).

3. **Stage 1 (kịch bản)** khi có story:
   - Không gọi bước chọn bối cảnh hay nghĩ tiêu đề. `title` giữ nguyên, không kiểm tra trùng với `topics_history.json`, nhưng vẫn ghi premise vào history.
   - Prompt gồm: `writing_rules` + khối series (nếu có) + premise + twist + hook + `outline`.
   - Có `outline`: số chương = số dòng outline, chương N theo đúng dòng N.
   - Không có `outline`: Gemini lập dàn ý 14–16 chương trước, lưu vào script JSON, rồi mới viết.
   - Câu đầu chương 1 = `hook` nguyên văn. `comment_question` và `thumb_keywords` lấy từ kho, không để Gemini sinh lại.
   - Độ dài giữ như spec FULL (8.900–11.500 từ).

4. **Stage 5 (thumbnail)**: tô màu đúng `thumb_keywords` (chuỗi con của tiêu đề). Nếu không khớp, báo lỗi rõ ràng thay vì tự đoán.

5. **Stage 6 (metadata)**: `pinned_comment` = `comment_question`. Truyện thuộc series thì thêm dòng "📚 Series <tên series> — nghe các truyện khác trong playlist" vào mô tả.

6. **Stage 8 (upload)**: `publishAt` = `publish_date` lúc 20:00 +07:00 nếu có, không thì ngày kế tiếp còn trống. Sau upload, ghi `video_id` vào `story_bank_state.json` và `index.jsonl` (thêm trường `story_id`).

7. **Test**
   - `pick_story` với các ngày 28/09, 16/10 (phải ra truyện 70), 10/01/2027 (được phép truyện Tết).
   - Stage 1 với truyện có outline: đúng 16 chương, câu đầu = hook.
   - Thumbnail có từ khoá không khớp → báo lỗi.
   - `run_daily.sh --dry-run-pick` với `tests/fake_stage.sh`.

## Prompt cho Claude Code
> Đọc `docs/superpowers/specs/2026-09-24-story-bank-spec.md`, spec topics-full-format và file `data/story_bank.json`. Làm trên nhánh `feat/topics-full-format`. Lập kế hoạch ngắn rồi làm theo thứ tự 1→7; hỏi tôi nếu code hiện tại khác giả định của spec. Chạy `uv run pytest -q` sau mỗi bước, cuối cùng chạy `./run_daily.sh --dry-run-pick` và cho tôi xem kết quả. Chưa upload gì.
