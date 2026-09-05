# Dựng video truyện tự động mỗi ngày

Pipeline gốc có 6 stage và dừng ở chỗ sinh metadata SEO. Bản này thêm:

| Stage | Module | Việc |
|---|---|---|
| 0 | `trend/` | Đọc tín hiệu xu hướng từ RSS công khai, sinh ý tưởng truyện gốc cho hôm nay |
| 1–6 | (như cũ) | Kịch bản → TTS → ảnh → video → thumbnail → SEO |
| 7 | `shorts/` | Cắt cả tập thành series ~30 video ngắn (Shorts) dọc 1080×1920 đánh số liên tục, gói theo mốc câu từ stage 2, không bắc cầu qua chương. Cần output stage 2+3 — **không chạy được cho tập dựng trước khi stage 2 biết ghi mốc câu** (chỉ có mốc chương). Hỏng không làm dừng lượt chạy |
| 8 | `upload/` | **Tuỳ chọn.** Đăng lên YouTube — mặc định tắt, bạn tự up |
| — | `notify/` | Báo khi dựng xong hoặc khi lỗi (thông báo macOS, hoặc Telegram) |

`run_daily.sh` xâu tất cả lại. `launchd/com.lee.audiobook.daily.plist` đặt lịch chạy.

---

## Cài đặt

```bash
./setup.sh
```

Đi qua 5 bước theo thứ tự phụ thuộc, bỏ qua bước nào đã xong, chạy lại bao nhiêu lần
cũng an toàn. Nó tự làm: `uv sync`, tạo `.env`, `npm install` cho Remotion, chạy
preflight, nạp lịch launchd.

Thứ duy nhất nó **không** làm thay bạn được là dán cookie Gemini vào `.env` — đó là
credential tài khoản riêng của bạn. Script sẽ dừng lại và chỉ rõ chỗ cần điền.

Cookie lấy ở: mở gemini.google.com đã đăng nhập → DevTools → Application → Cookies →
copy `__Secure-1PSID` và `__Secure-1PSIDTS`.

### Kiểm tra bất cứ lúc nào

```bash
uv run python -m preflight.cli --deep
```

Kiểm 9 điều kiện trong ~10 giây, mỗi mục hỏng in kèm dòng lệnh cần chạy để sửa.
`--deep` tải thử feed thật và hiện một thông báo thử. Thêm `--upload` nếu có dùng
tính năng đăng YouTube.

---

## Chạy

```bash
./run_daily.sh                              # bắt trend rồi dựng một tập (~50 phút)
./run_daily.sh --trope trong_sinh_bao_thu   # bỏ qua bắt trend, dùng trope có sẵn
./run_daily.sh --upload                     # dựng xong đăng luôn lên YouTube
```

Một lượt:

```
├─ Stage 0  trend.cli          ~30s   → output/ideas/<slug>-<ts>.txt
├─ Stage 1  scripts.cli        ~5m    → output/scripts/<slug>-<ts>.json
├─ Stage 2  tts.cli            ~14m   → output/audio/<slug>-<ts>.wav + .json
├─ Stage 3  images.cli         ~50m   → output/images/<slug>-<ts>.json + ~64 png
├─ Stage 4  video.cli          ~15m   → output/video/<slug>-<ts>.mp4
├─ Stage 5  thumbnail.cli      ~1m    → output/thumbnails/<slug>-<ts>.png
├─ Stage 6  metadata.cli       ~30s   → output/metadata/<slug>-<ts>.txt + .json
└─ Stage 7  shorts.cli         chưa đo → output/shorts/<slug>-<ts>-part-NN.mp4 + .txt (~30 phần)
```

Tổng khoảng **45–53 phút** cộng thời gian Stage 7 — bản mới dựng ~30 short thay vì 1,
mỗi phần vẫn cần một lượt render Remotion riêng nên thời gian tăng theo số phần;
chưa đo thực tế cho bản mới, xem `output/daily/<ngày>/07-short.log` để biết thời
gian lượt chạy gần nhất. Xong thì hiện thông báo trên màn hình. Stage 7 (short)
hỏng không làm lượt chạy báo thất bại — video dài, thumbnail, metadata đã xong hết
trước đó rồi. Stage 7 nay phụ thuộc **stage 2** (mốc câu), không phải stage 1 —
vì vậy không dựng được short cho tập đã dựng trước khi stage 2 biết ghi mốc câu;
muốn có short cho tập cũ phải chạy lại stage 2 cho tập đó trước.

Sản phẩm cần cho việc đăng tay:

- Video: `output/video/<tên-slug-SEO>.mp4` (stage 6 đã đổi sang tên thân thiện SEO)
- Thumbnail: `output/thumbnails/<slug>-<ts>.png` (1280×720)
- Tiêu đề + mô tả + tag + mốc chương: `output/metadata/<slug>-<ts>.txt`, dán thẳng
  vào YouTube Studio
- Video ngắn (Shorts, ~30 phần mỗi tập): `output/shorts/<slug>-<ts>-part-NN.mp4`
- Tiêu đề + mô tả từng phần: `output/shorts/<slug>-<ts>-part-NN.txt`, dán thẳng
  vào YouTube Studio cho từng phần

Log cả lượt ở `output/daily/<ngày>/run.log`, log riêng từng stage ở
`output/daily/<ngày>/0N-<stage>.log`.

---

## Đặt lịch

```bash
cp launchd/com.lee.audiobook.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lee.audiobook.daily.plist

launchctl list | grep audiobook          # kiểm tra đã nạp chưa
launchctl start com.lee.audiobook.daily  # chạy ngay, không đợi tới giờ
```

Đổi giờ: sửa `StartCalendarInterval` trong plist (mặc định 09:00), rồi `unload` +
`load` lại.

**Máy phải thức vào giờ đó.** Đang ngủ thì launchd chạy bù khi máy thức. Muốn chắc:

```bash
sudo pmset repeat wakeorpower MTWRFSU 08:55:00
```

Gỡ lịch: `launchctl unload ~/Library/LaunchAgents/com.lee.audiobook.daily.plist`

---

## "Bắt trend" ở đây nghĩa là gì

Tất cả nguồn đều là RSS công khai, **không cần API key nào**. Cấu hình ở
`config/trend.yaml`.

**Nguồn chính — mục tâm sự / đời sống / pháp luật của báo Việt.** Tiêu đề ở những mục
này chính là dạng xung đột khán giả truyện audio quan tâm:

> *"Vô tình thấy vợ nhận 50 triệu đồng, tôi cay đắng phát hiện sự thật"*
> *"Phát hiện con trai có nhân tình, tôi chưng hửng trước phản ứng của con dâu"*

Sát thể loại hơn hẳn từ khoá thịnh hành chung. Mặc định đọc 6 feed từ Dân Trí và
VnExpress.

**Nguồn phụ — Google Trends Việt Nam.** Phần lớn là bóng đá và tin quốc tế, gần như
không dùng làm chủ đề truyện được; prompt đã dặn Gemini bỏ qua thay vì cố nhét vào.

**Kênh YouTube đối thủ (tuỳ chọn).** Thêm `channel_id` vào `youtube_channels` trong
`config/trend.yaml` — YouTube có feed công khai cho mỗi kênh, cũng không cần key.
Tìm channel_id: mở một video của kênh, bấm vào tên kênh, id nằm trong URL dạng
`/channel/UCxxxxxxxxxxxxxxxxxxxxxx`. Nếu URL hiện dạng `@tenkenh` thì xem mã nguồn
trang và tìm chuỗi `UC` dài 24 ký tự.

`trend/idea_generator.py` đưa tất cả vào Gemini kèm ràng buộc: truyện **hư cấu hoàn
toàn**, chỉ mượn *dạng* xung đột chứ không mượn tình tiết của vụ việc nào, không người
thật, không thương hiệu thật, và không lặp lại motif của 15 tập gần nhất (đọc từ
`output/ideas/history.json`).

Nguồn nào chết thì bỏ qua nguồn đó. Chết hết thì `trend.cli` thoát với lỗi rõ ràng
thay vì bịa bừa — lúc đó chạy `./run_daily.sh --trope <trope_id>`.

---

## Thông báo

Mặc định `auto`: có cấu hình Telegram thì dùng Telegram, không thì hiện thông báo
macOS. Ép cứng bằng `NOTIFY_CHANNEL` trong `.env` (`auto` | `macos` | `telegram` |
`none`).

Thông báo macOS không cần cài gì, nhưng chỉ thấy khi đang ngồi trước máy. Muốn nhận
cả khi đi vắng thì dùng Telegram:

```bash
uv run python -m notify.setup
```

Nhắn `@BotFather` → `/newbot` → lấy token → nhắn cho bot một tin → dán token vào lệnh
trên. Nó tự dò chat id, gửi tin thử và ghi vào `.env`.

---

## Tự động đăng YouTube (tuỳ chọn)

Mặc định pipeline **không** đăng. Muốn bật thì:

1. https://console.cloud.google.com/ → tạo project
2. APIs & Services → Library → bật **YouTube Data API v3**
3. OAuth consent screen → User type **External** → thêm email sở hữu kênh vào Test
   users → bấm **Publish app** (để ở Testing thì token hết hạn sau 7 ngày)
4. Credentials → Create credentials → OAuth client ID → Application type **Desktop app**
5. Tải JSON về `config/youtube_client_secret.json`
6. `uv run python -m upload.auth` (mở trình duyệt, cấp quyền một lần)
7. `./run_daily.sh --upload`

**Cảnh báo:** OAuth project chưa qua audit của Google bị YouTube **ép mọi video upload
qua API về `private`**, kể cả khi đặt `public`. Muốn public tự động phải nộp đơn audit.
Đây chính là lý do mặc định là tự up tay — vào Studio bấm đổi mất 10 giây, còn nhanh
hơn cả quy trình audit.

---

## Sự cố hay gặp

| Triệu chứng | Nguyên nhân |
|---|---|
| `KeyError: 'SECURE_1PSID'` | `.env` thiếu cookie Gemini, hoặc cookie hết hạn — lấy lại từ trình duyệt |
| Stage 0 báo không lấy được tín hiệu nào | Mất mạng, hoặc báo đổi đường dẫn RSS — chạy tạm `--trope <id>` |
| Không thấy thông báo macOS | System Settings → Notifications → bật cho Terminal (hoặc app chạy lệnh) |
| Stage 3 tưởng như treo 10 phút | Bình thường: ~64 ảnh, mflux nạp lại model cho từng ảnh |
| Chạy tay ổn nhưng launchd fail | PATH/locale — `run_daily.sh` đã tự set, xem `output/daily/launchd.err.log` |
| Video lên nhưng ở chế độ private | OAuth project chưa qua audit — hành vi bình thường của YouTube |
| Không rõ hỏng ở đâu | `uv run python -m preflight.cli --deep` chỉ đúng mục thiếu |
