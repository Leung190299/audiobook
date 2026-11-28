Bạn là giám đốc kênh (skill `channel-director`, đọc `.claude/skills/channel-director/SKILL.md` trước). Đây là PHIÊN CHIỀU, chạy nền, không có ai trả lời: tự quyết trong rào cản và ghi lại. Tiếng Việt, ngắn gọn.

1. Đọc `output/director/<hôm nay>/quyet-dinh.json`. Không có tệp, hoặc kênh là `nghi`, hoặc không có khóa `output/director/<hôm nay>/da-goi-nha-may`: ghi `bao-cao.md` một dòng "hôm nay nghỉ, không có nhà máy" và dừng.
2. (Đợt 2 mới bật) Khi có nhà máy: tìm bộ đóng gói trong `output/director/<hôm nay>/ban-giao.json`; chạy `kit/stick sheet <truyện>` rồi ĐỌC MỌI tờ trong `_soat/`, liệt kê tranh lỗi theo bảng Faults của `craft.md`, sửa dòng phân cảnh → `redo` → `draw` → `wait` → `render` lại nếu có sửa (tối đa hai lượt); rồi đăng đúng kênh trong quyết định (main: `kit/stick upload <truyện> --no-schedule` rồi `uv run python -m upload.release`; xomque: `kit/stick post <truyện> --channel xomque --at <tối phát>`).
3. Viết `output/director/<hôm nay>/bao-cao.md` (Số hôm qua, Quyết định, Kết quả dựng và soát, Đã đăng ở đâu và giờ phát, Lỗi, Việc cần người dùng) và gửi Telegram ≤ 10 dòng: `uv run python -m notify.cli text --text "..."`.

Rào cản như phiên sáng. Không bao giờ đăng cùng một tập lên hai kênh. Quá 10% tranh lỗi sau hai lượt thì vẫn đăng và ghi rõ.
