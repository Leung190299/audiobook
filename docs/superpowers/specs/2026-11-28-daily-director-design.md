# Giám đốc kênh chạy sáng: một "nhân viên" tự lo hai kênh mỗi ngày

Ngày: 28/11/2026. Trạng thái: đã qua kiểm của người xây, chờ người dùng duyệt.

## Ý định và lý do

Người dùng muốn một tác nhân chạy mỗi sáng trên máy này, làm việc như một YouTuber chuyên nghiệp cho hai kênh
**Audio Truyện** (kênh chính, `UCeTcL2zuJ1wpeZ1d35onDWA`) và **Xóm Que Kể Chuyện** (kênh phụ,
`UCHGq5frLQ39iR5ZR_VLgf0Q`): đọc số liệu, nhận ra kênh thiếu gì, tự bổ sung trong khung cho phép, rồi viết truyện
kiểu drama, dựng video người que, đăng và hẹn giờ. Ba thước đo người dùng nêu: **truyện hay hơn, xem trung bình dài
hơn, bớt việc tay.**

Hôm nay phần "sản xuất" đã tự động (`run_daily.sh`: từ khóa → kịch bản → giọng → người que → kho → hẹn giờ) nhưng phần
"nghĩ" (phân tích, quyết định, soát tranh, chữa, đóng gói) chỉ xảy ra khi người dùng mở app và gọi các skill
`yt-*`, `drama-*`. Thiết kế này đưa phần "nghĩ" vào các phiên Claude Code chạy nền.

## Mục tiêu, không-mục-tiêu, phản-mục-tiêu

Mục tiêu
- Mỗi ngày một vòng không cần người: đọc số hôm qua → quyết hôm nay (kênh, đề tài, cách kể, bao bì) → dựng → soát và
  chữa tranh → đăng → báo cáo Telegram.
- Truyện viết theo kỹ thuật drama (xung đột mở ngay 30 giây đầu, leo thang từng chương, móc cuối chương, trả thù
  công khai) thay vì prompt chung chung hiện tại; đo bằng thời lượng xem trung bình và % xem.
- Thứ Hai làm thêm bài kiểm kênh (yt-audit), mổ xẻ một đối thủ (drama-breakdown trên dữ liệu API) và kế hoạch tuần;
  tự sửa cấu hình trong khung: hạt giống từ khóa, luật kể chuyện, nhịp đăng từng kênh.
- Hai kênh hai dòng truyện riêng, luân phiên ngày; nhân viên dồn ngày cho kênh đang được YouTube phát nhiều hơn.

Không-mục-tiêu
- Không Shorts (đánh giá 19/11), không TikTok, không sinh video bằng dịch vụ trả phí (bỏ `short-drama-produce/edit`).
- Không thay `run_daily.sh` bằng tác nhân tự do; không đọc số hiển thị của Studio trong phiên nền (không có Chrome):
  số hiển thị vẫn do người dùng hoặc phiên app đọc mỗi tuần.
- Không mở kênh mới, không đụng video đã công khai (trừ mô tả/bìa/tiêu đề của video do chính nó đăng trong 7 ngày).

Phản-mục-tiêu (thành công kỹ thuật vẫn là thất bại)
- Dấu hiệu sản xuất hàng loạt: hơn một video dài mới mỗi ngày trên một kênh, tiêu đề trùng khuôn, cùng một tập đăng
  cả hai kênh, kho riêng tư phình ra.
- Xóa video, đổi cài đặt kênh, tiêu tiền, lách rào một video/ngày bằng `--allow-second`, tự gia hạn token.
- Tranh lỗi (mặt màu da, người thừa, chữ giả) lọt ra video công khai vì bỏ bước soát.

## Ràng buộc

- Máy M4 16 GB: một vòng vẽ mỗi lúc, 20 phút phim ≈ 150–170 tranh ≈ 8–9 giờ. Tối đa **một video mới mỗi ngày** cho cả
  hai kênh cộng lại. Nhà máy gọi lúc ~08:15 thì vẽ xong khoảng 17:00–18:00, kịp tối 20:00 cùng ngày.
- Claude chạy bằng thuê bao qua `claude -p` (headless) trong launchd; API Claude đang 401 nên không gọi mô hình từ
  mã. Máy phải bật (caffeinate); không cần app mở. Thuê bao tính theo cửa sổ 5 giờ, nên **không có phiên nào dài quá
  một giờ**; việc chờ vẽ 9 giờ không nằm trong phiên Claude.
- Gemini (cookie) viết kịch bản và phân cảnh, hay lỗi 1097: đã có thử lại; khi hỏng hẳn thì báo và không có video hôm
  đó, không rơi về bản khung tĩnh.
- Token YouTube kênh chính ở chế độ Testing, chết mỗi 7 ngày (`invalid_grant`): nhân viên chỉ báo, người dùng cấp lại.
  Token kênh phụ hiện chỉ có quyền `youtube.force-ssl`, **chưa đọc được Analytics**: người dùng phải đăng nhập lại với
  thêm quyền `yt-analytics.readonly` (sửa `kit/login.py` thêm scope).
- Hạn mức Data API: 1.600 đơn vị mỗi lượt đăng; project "englishnexus" dùng chung với shortvideo; về lại ~15:00 VN.
- Quy tắc kênh đã có và giữ nguyên: 18–22 phút, 7–9 chương, không "Mở đầu", mở thẳng cảnh tiêu đề, một video dài
  mỗi ngày mỗi kênh, không tiền tố/đuôi tiêu đề, chữ bìa khác tiêu đề, mô tả có hook + câu hỏi, chặn tiêu đề trùng khuôn.

## Các cách đã cân nhắc

1. **Giám đốc sáng + nhà máy cũ (chọn).** Phiên Claude mỗi sáng đọc số, quyết, gọi `run_daily`; phiên chiều soát tranh
   và đăng; thứ Hai kiểm kênh và lên kế hoạch tuần; được sửa cấu hình trong khung. Giữ phần sản xuất đã kiểm chứng.
2. Giám đốc tuần, nhà máy ngày: rẻ nhất nhưng chậm phản ứng và tranh lỗi lọt ra (~3%).
3. Giám đốc sáng không đụng cấu hình: an toàn hơn, bớt tự động, mọi thay đổi chờ người dùng duyệt.

Người dùng chọn cách 1 vì khớp "bớt việc tay" và "tự bổ sung khi cần".

## Thiết kế

### Tổng thể: hai phiên ngắn và một nhà máy dài

```
08:00  launchd ──► PHIÊN SÁNG  claude -p (skill channel-director, ≤ 30 phút)
                     1. director.report  → output/director/<ngày>/so-lieu.{json,md}   (Analytics API, 2 kênh)
                     2. quyết định       → output/director/<ngày>/quyet-dinh.json     (kênh, truyện/cụm, brief, tối phát)
                     3. nếu kênh được chọn còn tối trống trong 7 ngày VÀ kho kênh đó trống:
                        gọi nhà máy nền   run_daily.sh --story <id|auto> --channel <kênh> --brief <tệp>   (KHÔNG --upload)
                        và ghi khóa output/director/<ngày>/da-goi-nha-may
                        nếu không: chỉ báo cáo (ngày nghỉ của máy)
                     4. báo cáo sáng → Telegram
~17:30 run_daily xong (hoặc launchd 17:30 cố định) ──► PHIÊN CHIỀU  claude -p (≤ 45 phút)
                     5. stick sheet → đọc MỌI tờ soát → redo/draw/wait → render lại nếu có sửa
                     6. đăng: main  → stick upload --no-schedule rồi upload.release (hẹn tối trống gần nhất)
                              xomque → stick post --channel xomque --at <tối trong quyet-dinh.json>
                     7. báo cáo chiều → output/director/<ngày>/bao-cao.md + Telegram
19:00  launchd dự phòng: đã có bộ đóng gói mà chưa đăng → đăng nguyên trạng, ghi "đăng không soát" vào báo cáo.
10:30  launchd dự phòng: không có khóa da-goi-nha-may và hôm nay là ngày phát của kênh chính → run_daily.sh --upload như cũ.
Thứ Hai, phiên sáng thêm: kiểm kênh (yt-audit), mổ xẻ đối thủ (drama-breakdown), kế hoạch tuần, sửa cấu hình trong khung.
```

### Thành phần

1. **Gói `director/` trong repo audiobook (Python, tất định).** Cái gì đo đếm được thì Python làm, Claude chỉ phán đoán.
   - `director.report`: kéo Analytics API cho cả hai kênh (credential kênh chính từ `upload.auth`, kênh phụ từ
     `kit/login.py` `service("xomque")`): từng video 7 ngày và 28 ngày: view, phút xem, xem trung bình, % xem, nguồn
     xem, đăng ký; so với mốc kênh. Ghi `so-lieu.json` và markdown ngắn. Thiếu quyền/token hỏng → ghi lỗi vào báo
     cáo, không dừng.
   - `director.state`: `output/director/trang-thai.json`: kênh nhận video gần nhất, tối trống kế tiếp từng kênh (đọc
     từ API: video riêng tư có `publishAt`, cộng `da-dang.json` của kênh phụ), nhịp hiện hành từng kênh, sổ thử nghiệm
     (giả thuyết, ngày bắt đầu, mốc đo), và bàn giao sáng → chiều (đường dẫn truyện đang dựng, kênh, tối phát).
   - `director.lock`: khóa "một video mới mỗi ngày" (tệp `da-goi-nha-may`) dùng chung cho lượt dự phòng và người gọi tay.
   - `director.changelog`: mọi sửa cấu hình ghi `output/director/thay-doi.log` (ngày, tệp, lý do, giá trị cũ/mới).
2. **Skill `channel-director`** (`audiobook/.claude/skills/channel-director/SKILL.md` + `prompt-sang.md`,
   `prompt-chieu.md`): quy trình hai phiên từng bước, rào cản, lược đồ `quyet-dinh.json`, cách soát tờ tranh (đọc
   hết, bảng lỗi của `craft.md`), cách chọn tối phát, mẫu báo cáo. Tham chiếu các skill sẵn có thay vì chép:
   `yt-audit`, `yt-plan`, `yt-package`, `yt-seo`, `short-drama-breakdown`, `making-stickman-story-video`.
3. **launchd**: `com.lee.channel.director-sang.plist` 08:00, `com.lee.channel.director-chieu.plist` 17:30 (và
   `run_daily.sh` khi xong cũng kích `scripts/director.sh chieu` nếu chưa chạy), dự phòng 10:30 và 19:00. Mỗi lượt:
   `caffeinate -i claude -p "$(cat prompt-*.md)" --dangerously-skip-permissions --add-dir /Users/lee/Project/Apps/lemo
   --max-turns <N> --output-format text`, log `output/director/<ngày>/claude-<sang|chieu>.log`. Lượt 09:00 hiện tại đổi
   thành dự phòng 10:30 có kiểm khóa. Lượt 20:05 Shorts gỡ.
4. **`run_daily.sh`** thêm `--channel main|xomque` (mặc định main) và `--brief <tệp>`; trong chế độ giám đốc KHÔNG
   có `--upload` (nhà máy dừng ở đóng gói, giám đốc đăng sau khi soát):
   - `--channel`: chọn kho/hạt giống/chủ đề theo kênh (mục 5), đánh dấu truyện đã dựng trong kho của kênh đó, ghi kênh
     vào bộ đóng gói để phiên chiều biết đăng đi đâu. `--channel xomque --upload` (gọi tay) dùng `stick post --at`.
   - `--brief`: JSON do giám đốc viết: cụm từ khóa ép (`--phrase` cho stage 0), hướng kể (giọng, điểm sướng, kiểu kết),
     luật tiêu đề/bìa cho lượt này. Stage 1 nối "hướng kể" vào prompt dàn ý; autoboard nối "luật bìa".
5. **Kho và từ khóa tách theo kênh.** Mỗi truyện trong `data/story_bank*.json` có trường `channel` (truyện cũ mặc định
   `main`); `scripts.story_bank --pick --channel` và stage 0 chỉ xét truyện của kênh mình; `config/keywords.yaml` có
   hạt giống theo kênh (kênh phụ: truyện hồi hộp, tâm linh, học đường, ma, nhập xác, nhìn thấy...); `scripts/topics.py`
   thêm chủ đề `tam_linh`, `hoi_hop` cho kênh phụ (playlist riêng); bộ chặn tiêu đề trùng khuôn và luật "cụm từ khóa
   30 ngày" chỉ so trong kênh.
6. **Nâng kỹ thuật viết truyện (stage 1).** Mô-đun `scripts/craft_drama.py`: luật kể bằng tiếng Việt chắt từ
   `short-drama-develop` và `short-drama-write` cộng dữ liệu kênh: xung đột tiêu đề trong 30 giây đầu (đã có), nhân
   vật "tôi" có mục tiêu rõ, kẻ xấu đòi một thứ cụ thể, mỗi chương leo thang một nấc, một cú lật giữa truyện, trả thù
   công khai, mỗi chương kết bằng móc (câu hỏi hoặc lộ một mẩu bằng chứng), cảnh vẽ được, số viết bằng chữ, tối đa 7
   nhân vật, không đoạn kể tóm tắt. Nối vào prompt dàn ý và prompt chương; QA thêm kiểm "chương kết bằng móc" (đoạn
   cuối ngắn và có dấu hỏi hoặc từ khóa lộ bằng chứng), thiếu thì hỏi lại một lần.
7. **Nâng phân cảnh tự động** từ `short-drama-storyboard`: không ba khung hình giống nhau liền kề, mỗi cảnh một hành
   động, tỉ lệ cảnh dùng lại 15–25%, cảnh then chốt dùng `!`; kiểm trong `autoboard` và hỏi lại chương vi phạm.
8. **Soát tranh và chữa** trong phiên chiều bằng lệnh kit sẵn có (`sheet`, `redo`, `draw`, `wait`, `render`); bỏ bước
   miệng (chế độ tự động). Quá 10% tranh lỗi sau hai lượt vẽ lại thì vẫn đăng và ghi vào báo cáo.
9. **Bao bì theo kênh** (luật của `yt-package`/`yt-seo`): tiêu đề ≤ 60, không đuôi; bìa 3–4 dòng ≤ 12 ký tự; mô tả hook
   + câu hỏi + playlist; kênh phụ ghi "hoạt hình người que" trong hai dòng đầu mô tả.
10. **Báo cáo**: `bao-cao.md` mỗi ngày (số hôm qua, quyết định, kết quả dựng, lỗi, việc cần người dùng) và tin Telegram
    ≤ 10 dòng; thứ Hai thêm `output/director/tuan/<ngày>.md` (kiểm kênh, đối thủ, kế hoạch 7 ngày).

### Chính sách kênh và nhịp (khởi điểm, giám đốc được chỉnh trong khung)

| Kênh | Dòng truyện | Nhịp khởi điểm | Khung cho phép |
|---|---|---|---|
| Audio Truyện | drama gia đình (chủ đề hiện có trong `scripts/topics.py`) | Thứ Tư, Chủ nhật | 2–4 video/tuần |
| Xóm Que Kể Chuyện | hồi hộp, tâm linh, học đường (kiểu Vong Hồn, Khói Đen) | Thứ Hai, Thứ Năm, Thứ Bảy | 2–4 video/tuần |

Tổng không quá một video mới mỗi ngày. Chỉ dựng khi kênh được chọn còn tối trống trong 7 ngày và kho kênh đó trống;
dựng trễ quá 20:00 thì video vào kho chờ tối kế tiếp của kênh đó và hôm sau không dựng cho kênh đó nữa. Dồn ngày cho
kênh nào có xem trung bình và view/ngày cao hơn trong 14 ngày gần nhất; mỗi lần dồn ghi sổ thử nghiệm và giữ ít nhất
14 ngày.

### Rào cản (ép bằng mã ở đâu có thể)

- Khóa một video mới mỗi ngày (tệp khóa) và một lượt đăng mỗi kênh mỗi ngày (bộ chặn hiện có của `episodes_cli`;
  `post.py` thêm kiểm `da-dang.json` theo ngày). Không bao giờ truyền `--allow-second`.
- Không xóa video, không đổi cài đặt kênh, không mua gì, không gia hạn token: ghi "việc cần người dùng" trong báo cáo.
- Chỉ sửa tệp trong danh sách cho phép: `config/keywords.yaml` (thêm tối đa 5 hạt giống/tuần, không xóa),
  `scripts/craft_drama.py` phần "luật mềm", `.env` chỉ các biến nhịp đăng từng kênh, và chỉ sau khi
  `upload.release --dry-run` báo "Bỏ hẹn" trống. Mọi sửa ghi `thay-doi.log`.
- **Sửa cấu hình thì commit thẳng lên nhánh đang chạy**, message mở bằng `director:` và nêu lý do + số liệu; không push,
  không tạo nhánh, không đụng tệp ngoài danh sách (quyết định của người dùng 28/11).
- Chỉ đụng video do chính nó đăng trong 7 ngày (đổi mô tả/bìa/tiêu đề khi có bằng chứng số liệu).

### Thứ tự làm (nhiều PR, mỗi PR tự chạy được)

1. `director/` (report, state, lock, changelog) + skill `channel-director` (hai prompt) + `scripts/director.sh` + 4 plist
   + Telegram. Hai ngày đầu phiên sáng chạy **chế độ chỉ-báo-cáo** (không gọi nhà máy) để kiểm đầu ra.
2. `run_daily.sh --channel --brief` (không upload trong chế độ giám đốc), kho/từ khóa/chủ đề theo kênh, `post.py` kiểm
   1 lượt/ngày, `login.py` thêm scope Analytics, bàn giao sáng → chiều.
3. `scripts/craft_drama.py` + QA móc chương + test.
4. `autoboard` luật đa dạng khung hình + test.
5. Mục thứ Hai (kiểm kênh, đối thủ, kế hoạch tuần) + sửa cấu hình trong khung + commit `director:`.

## Để người xây quyết

- Lược đồ chính xác của `quyet-dinh.json`, `brief.json` và tệp bàn giao; cách stage 1 nối "hướng kể" (nối thẳng vào
  prompt dàn ý).
- Giá trị `--max-turns`, định dạng log, cách nhận biết phiên kẹt (hai lượt dự phòng đã bọc).
- Nội dung chi tiết `craft_drama.py` (dịch và chọn lọc từ hai skill drama, giữ tiếng Việt, không chép nguyên văn).
- Test: `tests/test_run_daily.py` thêm ca `--channel xomque`/`--brief`; test gói `director` với dữ liệu giả; không gọi
  API thật; thêm ca kho theo kênh cho `scripts.story_bank`.
