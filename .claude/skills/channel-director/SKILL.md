---
name: channel-director
description: Use when running or debugging the daily "giám đốc kênh" sessions (scripts/director.sh sang|chieu, launchd 08:00/17:30) that read both channels' Analytics, decide today's channel/story/brief, (from đợt 2) trigger run_daily.sh, review the drawn images, publish and report via Telegram. Also when asked "giám đốc kênh hôm nay làm gì", "đọc báo cáo sáng", or to change the director's guardrails.
---

# Giám đốc kênh (channel-director)

Thiết kế: `docs/superpowers/specs/2026-11-28-daily-director-design.md`. Kế hoạch đợt 1: `docs/superpowers/plans/2026-11-28-director-dot-1.md`.

## Hai phiên một ngày

| Giờ | Lệnh | Việc | Ghi ra |
|---|---|---|---|
| 08:00 | `scripts/director.sh sang` (prompt `prompt-sang.md`, `--max-turns 60`) | số liệu hai kênh → nhận xét → quyết định → (đợt 2) gọi nhà máy → báo cáo | `output/director/<ngày>/so-lieu.{json,md}`, `quyet-dinh.json`, `bao-cao-sang.md`, `claude-sang.log` |
| 17:30 | `scripts/director.sh chieu` (prompt `prompt-chieu.md`, `--max-turns 120`) | soát tranh, chữa, đăng, báo cáo | `bao-cao.md`, `claude-chieu.log` |
| 10:30 | `scripts/daily_fallback.sh` | chưa có khóa và là ngày phát kênh chính → `run_daily.sh --upload` như cũ | khóa `da-goi-nha-may` |

Tệp dùng chung: `output/director/trang-thai.json` (nhịp, tối đã chiếm, tối trống kế tiếp từng kênh, bàn giao), `output/director/thay-doi.log` (sổ sửa cấu hình), `output/director/CHI-BAO-CAO` (tồn tại = phiên sáng không được gọi nhà máy).

## Lệnh tất định (Python làm, Claude chỉ phán đoán)

- `uv run python -m director.report [--date D] [--out DIR]` → in `Số liệu: <so-lieu.md>`; kênh lỗi nằm ở mục `loi`.
- `uv run python -m director.state --refresh | --show` → in `Trạng thái: <path>`.
- `uv run python -m director.lock [--check]` → mã 0 đang/vừa khóa, 3 chưa khóa.
- `uv run python -m director.changelog --file F --reason R --old O --new N` → một dòng TSV vào sổ.
- `uv run python -m notify.cli text --text "..."` → Telegram.

## Lược đồ `quyet-dinh.json`

```json
{"ngay": "2026-11-29", "kenh": "xomque", "ly_do": "...", "toi_phat": "2026-11-30T20:00:00+07:00",
 "truyen": {"id": null, "phrase": "truyện ma nhìn thấy vong hồn"},
 "brief": {"huong_ke": "...", "luat_tieu_de": "≤ 60 ký tự, không đuôi, không trùng 3 chữ đầu/cuối", "luat_bia": "3-4 dòng ≤ 12 ký tự, chữ khác tiêu đề"},
 "viec_can_nguoi_dung": ["..."]}
```
`kenh` là `nghi` khi không kênh nào vừa còn tối trống trong 7 ngày vừa trống kho.

## Quyết định kênh và nhịp

Khởi điểm: `main` = drama gia đình, Thứ Tư và Chủ nhật; `xomque` = hồi hộp, tâm linh, học đường, Thứ Hai, Thứ Năm, Thứ Bảy. Tổng không quá một video mới mỗi ngày. Dồn ngày cho kênh có xem trung bình và view/ngày cao hơn trong 14 ngày gần nhất; mỗi lần dồn ghi vào `thu_nghiem` của `trang-thai.json` và giữ ít nhất 14 ngày. Khung mỗi kênh 2–4 video/tuần.

## Rào cản (không ngoại lệ)

- Không xóa video, không đổi cài đặt kênh, không mua gì, không gia hạn token (`invalid_grant` → ghi "việc cần người dùng").
- Không `--allow-second`; không đăng cùng một tập lên hai kênh; chỉ đụng video do chính mình đăng trong 7 ngày.
- Chỉ được sửa: `config/keywords.yaml` (thêm ≤ 5 hạt giống/tuần, không xóa), `scripts/craft_drama.py` phần "luật mềm" (đợt 3), hai biến nhịp trong `.env` (`AUDIOBOOK_RELEASE_WEEKDAYS`, `AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE`) và chỉ sau khi `uv run python -m upload.release --dry-run` báo "Bỏ hẹn" trống. Mọi sửa: ghi `director.changelog` rồi `git commit` với message mở bằng `director:` (không push, không tạo nhánh).
- Không đọc, in hay gửi nội dung `.env`, `config/youtube_*.json`, `kit/.youtube_token_*.json`.

## Soát tranh (phiên chiều, đợt 2)

Đọc hết mọi tờ `_soat/soat-*.jpg` của truyện; lỗi theo bảng Faults trong `~/.claude/skills/making-stickman-story-video/craft.md` (mặt màu da, người thừa, chữ giả, hói, bong bóng thoại). Sửa dòng phân cảnh trước, rồi `kit/stick redo <truyện> <id>`, `draw`, `wait`, `render --no-mouth`, `check --proxy`, `package`. Hai lượt vẫn lỗi thì chấp nhận và ghi báo cáo.

## Kiểm tay

```bash
touch output/director/CHI-BAO-CAO          # đợt 1: luôn chỉ báo cáo
bash scripts/director.sh sang && tail -40 output/director/$(date +%F)/claude-sang.log
cat output/director/$(date +%F)/bao-cao-sang.md
```
