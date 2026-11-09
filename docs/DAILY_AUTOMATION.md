# Dựng video truyện tự động mỗi ngày

Pipeline gốc có 6 stage và dừng ở chỗ sinh metadata SEO. Bản này thêm:

| Stage | Module | Việc |
|---|---|---|
| 0 | `trend/` | Đọc tín hiệu xu hướng từ RSS công khai, sinh ý tưởng truyện gốc cho hôm nay |
| 1–3 | (như cũ) | Kịch bản (từ 22/09: cấu trúc 3 tập, cliffhanger ở chương 5 và 11, kèm `hook` + `comment_question`) → TTS → ảnh |
| 4 | `episodes/` | **Từ 22/09/2026:** chia truyện thành **3 tập 15–20 phút** (5/6/5 chương, `episodes/plan.py`), mỗi tập mở bằng cold open (đoạn cao trào cắt từ chương cuối tập) và kết bằng card "Tập N+1 lên sóng 20h mai". Ghi manifest `<stem>-episodes.json` cho stage 5/6/8. `video.cli` (bản full 50 phút) vẫn chạy tay được nhưng không còn trong lịch. Xem `docs/superpowers/specs/2026-09-22-episodes-design.md` |
| 5 | `thumbnail/` | 1 ảnh nền → ảnh truyện + 1 ảnh/tập có badge "TẬP N/3"; hook 2–4 từ, chữ to neo đáy trên dải tối |
| 6 | `metadata/` | 1 lần Gemini cho truyện → tiêu đề/mô tả/bình luận ghim cho từng tập (mốc chương theo trục tập, câu hỏi bình luận, chỗ trống link tập sau/playlist); đổi tên mp4 thành `<slug>-tap-N.mp4`; ghi danh sách `output/metadata/<stem>-episodes.json` |
| 7 | `shorts/` | Dựng **3 trích đoạn** ngắn (Shorts) dọc 1080×1920 rải đều cả truyện, mỗi cái mời nghe tập 1 trên kênh. Gói theo mốc câu từ stage 2, không bắc cầu qua chương, không lấy đoạn kết. Cần output stage 2+3 — **không chạy được cho tập dựng trước khi stage 2 biết ghi mốc câu** (chỉ có mốc chương). Hỏng không làm dừng lượt chạy |
| 8 | `upload/` | **Tuỳ chọn.** `upload.episodes_cli`: tải cả 3 tập lên hẹn giờ 20h mỗi ngày một tập (private + publishAt; tập 1 tối nay nếu chạy trước 19h30), gắn link tập sau vào mô tả tập trước, đăng bình luận câu hỏi dưới mỗi tập (ghim làm tay), rồi 3 trích đoạn trỏ về tập 1. 3 + 3 = 9.600/10.000 đơn vị hạn mức/ngày. Mặc định tắt |
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
├─ Stage 0  keywords.cli       ~1–2m  → "Truyện: <id>" (từ 10/11, mặc định với --story auto: gợi ý tìm kiếm YouTube VN + video đối thủ → chấm Cầu/View/Giọng/Mới → dò kho theo tên, không có thì mô hình viết truyện mới vào data/story_bank.auto.json; thoát 3 = rơi về --pick; tắt: --no-keywords)
├─ Stage 0  trend.cli          ~30s   → output/ideas/<slug>-<ts>.txt (kiểu cũ, chỉ với --trend)
├─ Stage 1  scripts.cli        ~5m    → output/scripts/<slug>-<ts>.json
├─ Stage 2  tts.cli            ~14m   → output/audio/<slug>-<ts>.wav + .json (từ 06/11: đọc xong tăng tốc bằng ffmpeg atempo, x1.25 tới 09/11, x1.15 từ 10/11, `speed` trong config/voice.yaml; mốc câu/chương đã chia theo tốc độ)
├─ Stage 3  images.cli         ~46m (đo 05/09: 66 ảnh)   → output/images/<slug>-<ts>.json + ~64 png
├─ Stage 4  episodes.cli       ~25m   → output/episodes/<slug>-<ts>-ep-0N.mp4 (3 tập) + <slug>-<ts>-episodes.json
├─ Stage 5  thumbnail.cli      ~1m    → output/thumbnails/<slug>-<ts>.png + -ep-0N.png
├─ Stage 6  metadata.cli       ~30s   → output/metadata/<slug>-<ts>-ep-0N.txt/.json + <slug>-<ts>-episodes.json
└─ Stage 7  shorts.cli         ~4m    → output/shorts/<slug>-<ts>-part-NN.mp4 + .txt (2 trích đoạn, từ 05/11)
```

Tổng khoảng **81–89 phút (đo 05/09: stage 3 46 phút, stage 4 25,5 phút cho bản full — 3 tập cộng lại xấp xỉ)** cộng ~4 phút Stage 7 (3 trích đoạn),
mỗi phần vẫn cần một lượt render Remotion riêng nên thời gian tăng theo số phần;
chưa đo thực tế cho bản mới, xem `output/daily/<ngày>/07-short.log` để biết thời
gian lượt chạy gần nhất. Xong thì hiện thông báo trên màn hình. Stage 7 (short)
hỏng không làm lượt chạy báo thất bại — video dài, thumbnail, metadata đã xong hết
trước đó rồi. Stage 7 nay phụ thuộc **stage 2** (mốc câu), không phải stage 1 —
vì vậy không dựng được short cho tập đã dựng trước khi stage 2 biết ghi mốc câu;
muốn có short cho tập cũ phải chạy lại stage 2 cho tập đó trước.

Stage 3 nay cũng phụ thuộc **stage 2** (cần `sentences` để chia mỗi chương thành
cảnh ~50s), không chỉ nhận mình script như bản cũ. Dựng lại một tập cũ thì thứ
tự bắt buộc là: chạy lại stage 2 nếu metadata TTS chưa có mốc câu → chạy lại
stage 3 với đúng JSON đó → chạy lại stage 4/6/7 với cặp JSON (TTS + ảnh) mới:

```bash
uv run python -m tts.cli output/scripts/<trope>-<ts>.json
uv run python -m images.cli output/scripts/<trope>-<ts>.json output/audio/<trope>-<ts-moi>.json
uv run python -m episodes.cli output/scripts/<trope>-<ts>.json output/audio/<trope>-<ts-moi>.json output/images/<trope>-<ts-moi>.json
```

Sản phẩm cần cho việc đăng tay:

- Video từng tập: `output/episodes/<slug-SEO>-tap-N.mp4` (stage 6 đã đổi tên)
- Thumbnail từng tập: `output/thumbnails/<slug>-<ts>-ep-0N.png` (1280×720)
- Tiêu đề + mô tả + tag + mốc chương + **bình luận ghim** từng tập:
  `output/metadata/<slug>-<ts>-ep-0N.txt`, dán thẳng vào YouTube Studio. Đăng
  tay thì: hẹn giờ 20h mỗi ngày một tập, dán bình luận ghim rồi bấm Ghim, sau khi
  tập N+1 có link thì sửa dòng "▶️ Tập tiếp theo" trong mô tả tập N.
- Video ngắn (Shorts, 2 trích đoạn mỗi truyện từ 05/11): `output/shorts/<slug>-<ts>-part-NN.mp4`
- Tiêu đề + mô tả từng phần: `output/shorts/<slug>-<ts>-part-NN.txt`, dán thẳng
  vào YouTube Studio cho từng phần

Log cả lượt ở `output/daily/<ngày>/run.log`, log riêng từng stage ở
`output/daily/<ngày>/0N-<stage>.log`.

---

## Kho video và lịch 7 ngày (từ 05/11/2026)

Đánh giá kênh 05/11: phân phối về ≈0 sau khi tải lên 9+ video một lúc (27/10) và
hẹn sẵn 30 ngày × 4 video/ngày. Từ 05/11 lịch chỉ giữ **7 ngày tới**, 1 truyện +
2 Shorts hẹn giờ mỗi ngày (từ 08/11 stage 1 ép đủ 3 `short_beats` và stage 7 dựng
3 Short/truyện; Short thứ 3 chỉ nằm kho):

- Mọi video đăng lên đều vào **kho**: riêng tư, không hẹn giờ (`upload.episodes_cli
  --no-schedule`). Kho là trạng thái thật trên YouTube (`videos.list`), sửa tay trong
  Studio cũng không lệch.
- Mỗi sáng `run_daily.sh --upload` gọi `upload.release` TRƯỚC khi dựng gì: bỏ hẹn
  video hẹn quá 7 ngày (về kho), rồi hẹn đúng **một** video trong kho cho tối trống
  gần nhất (20h, 2 short đầu 20h05; short thứ 3 nằm im trong kho). Ưu tiên hai
  chủ đề đang thắng (bố mẹ/mẹ chồng trọng sinh, nghề lạ) xen kẽ, rồi họ hàng,
  cuối cùng học đường — xếp theo tỷ lệ short "nổ" (`metadata.topic_views`, 06/11). Hẹn được hoặc lịch đã kín → thoát, **không dựng mới**.
  Kho trống (mã 3) → dựng truyện mới như cũ, đăng vào kho, rồi Stage 9 hẹn giờ.

```bash
uv run python -m upload.release --dry-run        # xem kế hoạch, không đổi gì
uv run python -m upload.release                  # bỏ hẹn quá 7 ngày + hẹn 1 video
uv run python -m upload.release --unschedule-only
```

Mô tả video dài quay lại bản đầy đủ (hook, cảnh báo AI, câu hỏi, playlist, chương,
hashtag; bỏ "Keywords:"); short dùng câu hỏi chọn phe của truyện. Video đã đăng
trước đó sửa bằng:

```bash
uv run python -m metadata.redescribe --dry-run   # video riêng tư/đã hẹn
uv run python -m metadata.redescribe --shorts    # kèm short (51 đơn vị hạn mức/video)
uv run python -m metadata.redescribe --all --shorts
```

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

Feed kênh có sẵn lượt xem từng video, nên `trend/outliers.py` chấm thêm **bội số so
với trung vị của chính kênh đó** (bỏ video dưới 3 ngày tuổi vì view còn đang lên).
Video từ 2x trở lên được đưa vào prompt thành mục "VƯỢT TRỘI" — khuôn đã được khán
giả kiểm chứng, mạnh hơn "tiêu đề mới nhất". Xem bảng xếp hạng, và soát luôn kênh
nào có feed chết:

```bash
uv run python -m trend.outliers            # --min 3 để chỉ xem cú nổ lớn
```

`trend/idea_generator.py` đưa tất cả vào Gemini kèm ràng buộc: truyện **hư cấu hoàn
toàn**, chỉ mượn *dạng* xung đột chứ không mượn tình tiết của vụ việc nào, không người
thật, không thương hiệu thật, và không lặp lại motif của 15 tập gần nhất (đọc từ
`output/ideas/history.json`).

Nguồn nào chết thì bỏ qua nguồn đó. Chết hết thì `trend.cli` thoát với lỗi rõ ràng
thay vì bịa bừa — lúc đó chạy `./run_daily.sh --trope <trope_id>`.

---

## Đọc tỷ lệ giữ chân

Data API (`metadata.report`) không có số giữ chân; lấy qua **YouTube Analytics API**:

```bash
uv run python -m metadata.retention --days 14           # bảng tổng hợp mọi video 14 ngày qua
uv run python -m metadata.retention --video <video_id>  # một video
```

Cần làm một lần: bật "YouTube Analytics API" trong Google Cloud Console (APIs &
Services → Library) cho đúng project OAuth đang dùng, rồi `uv run python -m
upload.auth --force` và đồng ý cả quyền xem báo cáo Analytics. Quyền này chỉ xin
ở bước đồng ý, không xin khi làm mới token — token cũ chưa có nó vẫn đăng video
bình thường. Analytics trễ 1-2 ngày nên `--days` bỏ video lên sóng chưa tới 2 ngày.

Không dùng API thì tải CSV từ Studio (video → Số liệu phân tích → Mức độ tương tác
→ biểu đồ tỷ lệ giữ chân → nút tải xuống) rồi `metadata.retention <file.csv> --video <id>`.

Báo ba thứ: **rơi đầu** (mất bao nhiêu trong 30s đầu — lỗi cold open/tiêu đề),
**vực** (đoạn tụt dốc hẳn, in luôn chương và câu đang đọc ở đó) và **trượt** (mất
đều mỗi phút — lỗi nhịp, sửa bằng cắt). Mốc câu lấy từ
`output/episodes/<stem>-props.json`, nối qua `output/metadata/index.jsonl`. Báo cáo
lưu ở `output/metadata/retention-<video_id>.md` và `retention-<ngày>.md` (bảng tổng hợp).

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
| Stage 3 tưởng như treo ~50 phút | Bình thường: ~64 ảnh, mflux nạp lại model cho từng ảnh |
| Chạy tay ổn nhưng launchd fail | PATH/locale — `run_daily.sh` đã tự set, xem `output/daily/launchd.err.log` |
| Video lên nhưng ở chế độ private | OAuth project chưa qua audit — hành vi bình thường của YouTube |
| Không rõ hỏng ở đâu | `uv run python -m preflight.cli --deep` chỉ đúng mục thiếu |
