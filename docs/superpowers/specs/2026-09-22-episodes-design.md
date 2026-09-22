# Chia truyện thành tập 15–20 phút — thiết kế 22/09/2026

## Vì sao

Số liệu YouTube Studio kênh Audio Truyện (28 ngày 24/8–20/9/2026):

- Video dài 40–58 phút: 175,9 N hiển thị, CTR 3,2 %, **thời lượng xem trung bình
  1:43 (~3 %)**. Truyện tốt nhất 129 view all-time; ba tập đăng 21/9: 0–4 view.
  Gần như toàn bộ view của video dài đến từ 3 video karaoke cũ.
- Shorts: 12,5 N view, 43,6 % xem tiếp; trích đoạn 4/5 của một truyện 1,2 N view
  trong khi 1/5 cùng truyện 423 → rải nhiều không bằng chọn đúng.
- 0 bình luận, tab Bài đăng trống, người xem thường xuyên < 0,1 %.
- 847/1.000 sub, 2.911/4.000 giờ xem hợp lệ — sắp đủ điều kiện kiếm tiền.

Thuật toán đề xuất theo % giữ chân; 3 % trên 50 phút là án tử. Tập 15–20 phút
mở bằng cao trào và kết bằng cliffhanger là định dạng chuẩn của các kênh truyện
audio đang tăng trưởng, và một truyện ra 3 lần được đề xuất thay vì 1.

## Quyết định

1. **Một nguồn sự thật cho ranh giới tập:** `episodes/plan.py`. 16 chương →
   5/6/5. Stage 1 hỏi nó để đặt cliffhanger đúng chương 5 và 11; stage 4 hỏi nó
   để cắt; stage 5/6 để đánh số. Đổi số tập là đổi `EPISODE_COUNT` ở một chỗ.
2. **Stage 1** (prompt): chương 1 mở thẳng vào xung đột; chương cuối tập PHẢI
   kết bằng cliffhanger; dàn ý trả thêm `hook` (≤ 20 từ) và `comment_question`
   (≤ 25 từ). Hai trường không bắt buộc — thiếu thì rỗng, không hỏng lượt chạy.
3. **Stage 4 mới `episodes/`** thay `video/` trong `run_daily.sh`:
   - Cold open = đoạn 12–35 s cắt từ ~62 % chương cuối tập, chừa 3 câu cuối
     (không lộ cú lật). Thuần cắt wav đã có, không TTS, không Gemini.
   - Thân tập = các chương của tập. Outro = 6 s im lặng + card
     "Tập N+1 lên sóng 20h mai — đăng ký để không bỏ lỡ" (tập cuối: hết truyện).
   - Props Remotion quy về trục tập; cold open là "chương 0". `MainVideo` nhận
     thêm props tuỳ chọn (`episodeLabel`, `hookText`, `coldOpenSeconds`,
     `outroSeconds`, `outroTitle`, `outroText`) — props cũ của `video.cli`
     vẫn render y hệt.
   - Manifest `<stem>-episodes.json` là hợp đồng với stage 5/6/8.
4. **Stage 5**: hook cắt còn ≤ 4 từ, chữ ≥ 64 pt neo đáy, dải tối 45 % dưới,
   badge "TẬP N/3". Một ảnh nền mflux → 1 + 3 file.
5. **Stage 6**: tiêu đề truyện ≤ 60 ký tự (Gemini vượt thì cắt), tiêu đề tập
   `<truyện> | Tập N/3`; mô tả: hook → mô tả → ❓ câu hỏi → chỗ trống playlist /
   tập sau → CTA → chương (trục tập, 0:00 Mở đầu) → hashtag. Kèm
   `pinned_comment`. Đổi tên mp4 `<slug>-tap-N.mp4`. Index cho stage 8.
6. **Stage 7**: 3 trích đoạn (từ 5), CTA "Nghe trọn tập 1 trên kênh", mô tả có
   câu mời bình luận.
7. **Stage 8 mới `upload.episodes_cli`**: tải 3 tập một lượt, private +
   `publishAt` 20h mỗi ngày một tập; sau khi có id, videos.update gắn link tập
   sau vào tập trước; commentThreads.insert câu hỏi (ghim làm tay — API không
   ghim); shorts trỏ về tập 1. State file để chạy lại không đăng trùng. Hạn mức
   3 + 3 = 9.600/10.000.

## Không làm (cố ý)

- Không TTS thêm lời dẫn/recap: tốn 1–2 phút TTS + một lượt Gemini nữa cho
  mỗi tập và thêm một chỗ hỏng; cold open bằng trích đoạn thật đủ tốt và giữ
  giọng đồng nhất.
- Không bỏ hẳn `video.cli`/`upload.cli`/`upload.episode_cli`: vẫn cần khi muốn
  đăng một bản full 50 phút cho playlist "nghe trọn bộ" sau này.
- Không tự ghim bình luận / tạo playlist: API không hỗ trợ ghim; playlist thì
  làm tay một lần rồi đặt `YOUTUBE_PLAYLIST_URL` trong `.env`.

## Việc tay còn lại (ngoài pipeline)

Ẩn video bị chặn bản quyền và series phim ngắn thuyết minh trước khi nộp đơn
YPP; gom karaoke cũ vào một playlist, không đăng thêm; đổi tên/banner/mô tả kênh
thành kênh truyện; tạo playlist truyện và đặt `YOUTUBE_PLAYLIST_URL`; ghim bình
luận mỗi tập; poll tab Cộng đồng; trả lời bình luận trong 24 h.

## KPI 30 ngày

CTR > 5 %, thời lượng xem TB > 6 phút, người xem quay lại > 5 %, 1.000 sub.
