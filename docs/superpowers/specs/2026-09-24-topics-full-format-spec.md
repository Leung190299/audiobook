# Spec: Pipeline audiobook — 3 chủ đề trọng tâm + định dạng FULL (24/09/2026)

Repo: `/Users/lee/Project/Apps/audiobook`. Đặt file này vào `docs/superpowers/specs/` rồi giao cho Claude Code.
Kế thừa thay đổi ngày 22/09 (`2026-09-22-episodes-design.md`) — KHÔNG xoá chế độ chia tập, chỉ thêm lựa chọn.

## Bối cảnh (từ phân tích đối thủ 24/09)
- Dứa Audio (28,5N sub) và Mê Cung Audio (7N sub): toàn bộ hit là **video FULL 1 truyện 35–90 phút**, giọng **hài + vả mặt**, nữ chính ngôi "tôi" mỏ hỗn/lười/cá mặn, tiêu đề là 1 câu kể chuyện.
- Thumbnail thắng: nền pastel, 1 linh vật/sticker hoạt hình bên trái, **gần như cả câu tiêu đề** (8–12 chữ) bên phải bằng font đậm dạng condensed, 2–3 từ khoá đổi màu, badge tên kênh cố định.
- Cặn bão hoà cần tránh: cá mặn hậu cung, tiệm vàng mã/cõi âm, hệ thống thất đức, ảnh đế/showbiz, xem bói hào môn.

## 1. Registry chủ đề — file mới `scripts/topics.py`
Ba chủ đề (id dùng cho CLI, manifest, playlist, báo cáo):

| id | Tên hiển thị | Nhân vật chính | Bối cảnh | Giọng |
|---|---|---|---|---|
| `ho_hang_viet` | Họ hàng cực phẩm, tôi mỏ hỗn xử đẹp | nữ 25–35, tỉnh táo, mỏ hỗn | gia đình Việt: Tết, giỗ, đám cưới quê, chia đất, vay tiền, so sánh con | hài 70% / vả mặt 30% |
| `nghe_la_hong_bien` | Nghề lạ đời thường, ngày ngày hóng biến | người làm nghề dịch vụ Việt | chủ trọ, xe ôm ca đêm, giặt ủi, cầm đồ, giúp việc theo giờ, livestream bán hàng, shipper, dọn nhà thuê | hài 60% / phá án–lật kèo 40% |
| `bo_me_trong_sinh` | Bố mẹ trọng sinh, không nhịn con bất hiếu | mẹ/bố 55–65 tuổi (hoặc mẹ chồng) | trọng sinh về lúc sắp chia nhà/đi viện dưỡng lão; kiếp này sống cho mình | ấm + vả mặt 50/50, kết có hậu |

Mỗi entry gồm: `name`, `protagonist`, `settings: list[str]` (≥10 bối cảnh để xoay vòng), `title_formulas: list[str]`, `banned_motifs` (danh sách bão hoà ở trên + motif đã dùng), `comment_question_style`, `thumb_palette` (nền, màu từ khoá 1, màu từ khoá 2), `mascot_pose_hints`, `playlist_env` (tên biến .env chứa URL playlist của chủ đề).

Công thức tiêu đề (≤ 60 ký tự, ngôi "Tôi" hoặc câu tình huống):
- `[Tình huống/nghề] + [hành động bất ngờ của tôi]` — "Tôi Làm Chủ Trọ, Mười Phòng Mười Drama"
- `[Kẻ cực phẩm] + [đòi X], + [tôi làm Y]` — "Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn"
- `Trọng Sinh + [tuổi/thời điểm], + [quyết định ngược]` — "Trọng Sinh Năm 60 Tuổi, Tôi Không Chia Nhà Nữa"

Giữ `--trope` cũ chạy được (map `trong_sinh_bao_thu` → `bo_me_trong_sinh` hoặc giữ nguyên như trope cũ, tuỳ code hiện tại).

## 2. `run_daily.sh`
- Thêm `--topic <id>` và `--topic auto`. `auto` xoay vòng theo ngày trong tuần, cấu hình ở `.env`:
  `AUDIOBOOK_TOPIC_ROTATION=ho_hang_viet,nghe_la_hong_bien,ho_hang_viet,bo_me_trong_sinh,nghe_la_hong_bien,ho_hang_viet,bo_me_trong_sinh`
- Thêm `--format full|episodes`, mặc định đọc `AUDIOBOOK_FORMAT` (mặc định `full`).
- Ghi `topic` và `format` vào mọi manifest (`output/...-episodes.json` / `-full.json`) và metadata index.

## 3. Stage 1 — kịch bản (`scripts/prompts.py`, `generator.py`)
- Prompt nhận entry chủ đề; chọn 1 bối cảnh chưa dùng trong `output/topics_history.json` (lưu premise + tiêu đề đã dùng, chặn trùng 30 ngày).
- Luật giọng mới cho cả 3 chủ đề:
  - Ngôi thứ nhất "tôi"; câu đầu là tình huống xung đột + 1 câu chọc cười, không chào hỏi.
  - Mỗi chương có ít nhất 1 "miếng hài" (thoại mỏ hỗn, so sánh bất ngờ) và 1 nhịp "sảng" (kẻ xấu bị bẽ mặt nhỏ); cao trào vả mặt lớn ở chương cuối cụm.
  - `ho_hang_viet`, `nghe_la_hong_bien`: tên người, địa danh, món ăn, phong tục **Việt Nam**; không dùng tên/bối cảnh Trung Quốc.
  - Không bạo lực chi tiết, không khiêu gợi, không nhân vật vị thành niên trong tình huống người lớn.
- Độ dài chế độ `full`: 14–16 chương, mục tiêu 35–45 phút sau TTS (đo bằng số ký tự hiện có của VieNeu; chỉnh hằng số nếu cần).
- Dàn ý trả thêm: `title` (theo công thức), `thumb_text` (= tiêu đề, ≤ 12 chữ), `thumb_keywords` (1–3 cụm cần tô màu, phải là chuỗi con của `thumb_text`), `hook`, `comment_question`, `short_beats` (3 đoạn buồn cười/sảng nhất, mỗi đoạn tự đứng được).

## 4. Chế độ `full` (stage 4)
- Tái dùng code cutter của `episodes/`: 1 video = cold open 20–30s (đoạn sảng nhất, lấy từ `short_beats[0]`) + toàn bộ chương + card kết 8s ("Truyện mới 20h mỗi tối" + gợi ý 1 truyện cùng chủ đề).
- Remotion `MainVideo`: `episodeLabel` để trống khi full; giữ `hookText`.
- Chapters trong mô tả theo mốc chương thật (luật YouTube: 0:00, ≥3 mốc, cách ≥10s).
- Chế độ `episodes` giữ nguyên như 22/09.

## 5. Stage 5 — thumbnail (layout mới "sticker + full title")
- Khung 1280×720. Trái ~42%: ảnh mflux phong cách **sticker hoạt hình phẳng, viền dày, nền trong** của **linh vật riêng của kênh** (1 nhân vật gốc, cố định prompt + seed; đổi tư thế/biểu cảm theo `mascot_pose_hints`). Không dùng nhân vật có bản quyền hay na ná (vịt trắng, capybara đang là nhận diện của đối thủ → chọn con vật/nhân vật khác).
- Phải ~58%: khối chữ `thumb_text` 3–4 dòng, font condensed đậm có dấu tiếng Việt (kiểm tra Oswald Bold / Anton / Bebas Neue Pro VN — render thử chữ "Ố Ẫ Ự Ỹ"), chữ chính màu nâu đen, `thumb_keywords` tô 2 màu theo `thumb_palette`, tự co cỡ chữ để vừa khung (tối thiểu 72px).
- Nền màu pastel riêng cho từng chủ đề (người xem nhận ra chủ đề bằng màu) + badge tên kênh góc trên.
- Vẫn xuất `-thumbnail-b.png` cho Test & compare: bản B đổi từ khoá được tô màu hoặc biểu cảm linh vật.
- Chế độ `episodes` giữ badge "TẬP N/3".

## 6. Stage 6 — metadata
- Tiêu đề: `[Truyện Audio] <title> | <Tên kênh>` (≤ 100 ký tự tổng; phần `<title>` ≤ 60).
- Mô tả: hook → tóm tắt 2 câu → ❓`comment_question` → link playlist chủ đề → CTA đăng ký → chapters → hashtag chủ đề (`#truyenaudio` + 2 hashtag riêng mỗi chủ đề trong registry).
- `pinned_comment` = câu hỏi chọn phe (vd. "Nếu là bạn, bạn có cho bác Cả mượn sổ đỏ không? 1 = cho, 2 = không").

## 7. Stage 7 — Shorts
- 3 Shorts/truyện từ `short_beats`, 30–55s, mở bằng câu thoại buồn cười/sảng, tiêu đề là câu thoại đó (≤ 50 ký tự) + `#Shorts`.
- CTA cuối + mô tả trỏ về video full (link "Video có liên quan" làm tay nếu API không hỗ trợ).

## 8. Stage 8 — upload
- `full`: 1 video/ngày, private + publishAt 20h; thêm vào playlist theo **chủ đề** (`YOUTUBE_PLAYLIST_HO_HANG`, `YOUTUBE_PLAYLIST_NGHE_LA`, `YOUTUBE_PLAYLIST_BO_ME`) thay vì playlist theo truyện.
- Hạn mức: 1 video + 3 Shorts ≈ 6.400/10.000 đơn vị.

## 9. Đo lường để chốt sau 14 ngày
- Ghi `topic`, `format`, `video_id`, `publishAt` vào `output/metadata/index.jsonl`.
- Báo cáo thứ Hai (scheduled task) nhóm KPI theo `topic`: view 48h, CTR, thời lượng xem TB, sub thu được.
- Quy tắc: sau 14 ngày, chủ đề có view 48h trung bình thấp nhất và CTR < 3% → giảm tần suất trong `AUDIOBOOK_TOPIC_ROTATION`.

## 10. Test
- Unit test registry (đủ 3 id, formula ≤ 60 ký tự, keywords là chuỗi con của thumb_text).
- Test `run_daily.sh --topic auto --format full` với `tests/fake_stage.sh`.
- Test thumbnail: render 3 chủ đề với tiêu đề dài 12 chữ có dấu, không tràn khung.
- Test history chặn trùng premise.

## Prompt gợi ý cho Claude Code
> Đọc `docs/superpowers/specs/2026-09-24-topics-full-format-spec.md` và spec 22/09. Lập kế hoạch thay đổi theo từng stage, hỏi tôi trước nếu cấu trúc code khác với spec giả định. Làm theo thứ tự: registry → run_daily flags → stage 1 prompt → chế độ full → thumbnail → metadata → shorts → upload → test. Không xoá chế độ episodes. Chạy `uv run pytest -q` và `tsc --noEmit` sau mỗi bước lớn.
