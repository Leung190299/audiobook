#!/bin/bash
# Dựng trọn một truyện audio mỗi ngày: chọn chủ đề -> 7 stage -> báo khi xong.
# Mặc định KHÔNG đăng lên YouTube — bạn tự up. Thêm --upload nếu muốn tự động đăng.
#
#   ./run_daily.sh                              # truyện từ kho (--story auto), định dạng full
#   ./run_daily.sh --story 42                   # chỉ định truyện trong data/story_bank.json
#   ./run_daily.sh --dry-run-pick               # chỉ in lịch 7 ngày tới rồi thoát
#   ./run_daily.sh --topic ho_hang_viet         # kiểu cũ: để Gemini tự nghĩ cốt theo chủ đề
#   ./run_daily.sh --format episodes            # chia 3 tập như 22/09 thay vì 1 video full
#   ./run_daily.sh --trend                      # kiểu cũ: bắt trend (stage 0) thay vì chủ đề
#   ./run_daily.sh --trope trong_sinh_bao_thu   # kiểu cũ: trope có sẵn trong config/tropes.yaml
#   ./run_daily.sh --upload                     # dựng xong đăng luôn lên YouTube
#
# Từ 24/09/2026 truyện lấy từ kho biên tập sẵn data/story_bank.json (--story auto,
# chọn theo ngày LÊN SÓNG chứ không phải ngày dựng). Hết truyện phù hợp thì rơi về
# --topic auto kiểu cũ và in cảnh báo. Chủ đề xoay vòng theo thứ trong tuần
# (AUDIOBOOK_TOPIC_ROTATION trong .env) và định dạng FULL (AUDIOBOOK_FORMAT, mặc
# định full): 1 video 35-45 phút có cold open + card kết, 2 thumbnail A/B, 3 Shorts
# từ 3 đoạn hài/sảng nhất. Với --upload: private + hẹn giờ 20h, vào playlist chủ đề.
# --format episodes giữ nguyên dây chuyền 3 tập của 22/09.
#
# Mỗi lượt ghi log vào output/daily/<ngày>/. Lỗi ở bất kỳ stage nào cũng dừng ngay
# và bắn Telegram kèm phần cuối log của stage đó — trừ Stage 7 (short), stage này
# hỏng không được làm cả lượt chạy báo thất bại (xem chú thích ở Stage 7).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT" || exit 1

# launchd chạy với PATH tối thiểu và không có locale — nạp lại cả hai, nếu không
# `uv` sẽ không tìm thấy và `sed` sẽ vỡ khi gặp tiếng Việt có dấu.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
export PYTHONIOENCODING=utf-8

# nvm cài node ngoài mọi thư mục hệ thống, và launchd không nạp shell profile — nên
# `npx` biến mất và Stage 4 chết khi gọi Remotion. Đã xảy ra thật: lượt hẹn giờ đầu
# tiên (09:00 ngày 04/09) chạy hết 61 phút TTS + ảnh rồi mới đổ ở stage 4 vì
# FileNotFoundError: 'npx'. Nạp nvm thay vì ghi cứng số hiệu bản node, để nâng cấp
# node không làm hỏng lịch chạy.
if ! command -v npx >/dev/null 2>&1 && [[ -s "$HOME/.nvm/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  . "$HOME/.nvm/nvm.sh" --no-use >/dev/null 2>&1 || true
  nvm use default >/dev/null 2>&1 || true
fi

# Thiếu lệnh nào thì dừng NGAY, đừng đốt một tiếng đồng hồ rồi mới báo. Đây chính
# là bài học của lượt hỏng nói trên: lỗi nằm ở dòng đầu tiên nhưng lộ ra ở phút 61.
for _cmd in uv npx; do
  if ! command -v "$_cmd" >/dev/null 2>&1; then
    echo "Không tìm thấy lệnh '$_cmd' trong PATH. Lượt chạy dừng trước khi bắt đầu." >&2
    echo "PATH hiện tại: $PATH" >&2
    exit 3
  fi
done

# Cách gọi từng stage. Test tích hợp thay biến này bằng stage giả để kiểm tra
# dây chuyền parse stdout mà không phải chạy thật 50 phút.
RUNNER="${AUDIOBOOK_RUNNER:-uv run python -m}"

RUN_DATE="$(date +%Y-%m-%d)"
LOG_DIR="$REPO_ROOT/output/daily/$RUN_DATE"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run.log"
START_TS=$(date +%s)

# bash không tự nạp .env (python nạp qua load_dotenv): đọc riêng hai biến điều
# khiển dây chuyền. Biến môi trường đã đặt thì ưu tiên hơn .env.
env_get() {
  [[ -f "$REPO_ROOT/.env" ]] || return 0
  sed -n -E "s/^$1=[\"']?([^\"'#]*)[\"']?[[:space:]]*(#.*)?$/\1/p" "$REPO_ROOT/.env" | tail -1 | tr -d '[:space:]'
}
: "${AUDIOBOOK_FORMAT:=$(env_get AUDIOBOOK_FORMAT)}"
: "${AUDIOBOOK_TOPIC:=$(env_get AUDIOBOOK_TOPIC)}"

TROPE_ID=""
TOPIC_ARG=""
STORY_ARG=""
DRY_RUN_PICK=0
# Số ngày in ra khi --dry-run-pick.
DRY_RUN_PICK_DAYS="${AUDIOBOOK_PICK_DAYS:-7}"
USE_TREND=0
FORMAT="${AUDIOBOOK_FORMAT:-full}"
[[ -z "$FORMAT" ]] && FORMAT=full
# Mặc định chỉ dựng video, không đăng. Đăng lên YouTube cần token OAuth và một
# project đã qua audit của Google mới ra public được — không đáng để bật mặc định.
DO_UPLOAD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --trope) TROPE_ID="${2:-}"; shift 2 ;;
    --topic) TOPIC_ARG="${2:-}"; shift 2 ;;
    --story) STORY_ARG="${2:-}"; shift 2 ;;
    --dry-run-pick) DRY_RUN_PICK=1; shift ;;
    --format) FORMAT="${2:-}"; shift 2 ;;
    --trend) USE_TREND=1; shift ;;
    --upload) DO_UPLOAD=1; shift ;;
    --no-upload) shift ;;  # giữ lại cho tương thích, giờ đã là mặc định
    *) echo "Tham số không hiểu: $1" >&2; exit 2 ;;
  esac
done

case "$FORMAT" in
  full|episodes) ;;
  *) echo "--format phải là full hoặc episodes, nhận '$FORMAT'" >&2; exit 2 ;;
esac
SOURCES=0
[[ -n "$TROPE_ID" ]] && SOURCES=$((SOURCES + 1))
[[ -n "$TOPIC_ARG" ]] && SOURCES=$((SOURCES + 1))
[[ -n "$STORY_ARG" ]] && SOURCES=$((SOURCES + 1))
[[ "$USE_TREND" -eq 1 ]] && SOURCES=$((SOURCES + 1))
if (( SOURCES > 1 )); then
  echo "--trope, --topic, --story và --trend loại trừ nhau, chỉ chọn một." >&2
  exit 2
fi
# Mặc định từ 24/09: lấy truyện từ kho. Kho hết truyện phù hợp thì rơi về
# --topic auto ở đoạn chọn nguồn bên dưới.
if (( SOURCES == 0 )); then
  STORY_ARG="${AUDIOBOOK_STORY:-auto}"
fi

# --dry-run-pick: chỉ xem lịch, không dựng gì, không đụng output/daily.
if [[ "$DRY_RUN_PICK" -eq 1 ]]; then
  echo "Lịch truyện $DRY_RUN_PICK_DAYS ngày tới (không dựng gì):"
  $RUNNER scripts.story_bank --upcoming "$DRY_RUN_PICK_DAYS"
  exit $?
fi

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

human_duration() {
  printf '%dh%02dm' $(($1 / 3600)) $((($1 % 3600) / 60))
}

notify_failure() {
  local stage="$1" detail_file="$2"
  $RUNNER notify.cli failure \
    --stage "$stage" --log "$LOG_FILE" --detail-file "$detail_file" \
    >>"$LOG_FILE" 2>&1 || log "CẢNH BÁO: không gửi được thông báo Telegram."
}

# run_stage <tên stage> <file log riêng của stage> <lệnh...>
run_stage() {
  local stage="$1" out_file="$2"; shift 2
  log "▶ $stage"
  if ! "$@" >"$out_file" 2>&1; then
    cat "$out_file" >>"$LOG_FILE"
    log "✖ $stage THẤT BẠI"
    notify_failure "$stage" "$out_file"
    exit 1
  fi
  cat "$out_file" >>"$LOG_FILE"
}

# extract <ERE có đúng 1 nhóm bắt, khớp cả dòng> <file> -> in ra giá trị (có thể rỗng)
# Dùng [^[:space:]] chứ không dùng \S: sed trên macOS là BSD, không hiểu \S.
extract() {
  sed -n -E "s|^$1\$|\1|p" "$2" | tail -1
}

# require <giá trị> <tên stage> <file log> — thoát nếu rỗng.
# Phải gọi ở thân script chứ không lồng trong $( ): `exit` bên trong command
# substitution chỉ thoát subshell, script vẫn chạy tiếp với biến rỗng.
require() {
  if [[ -z "$1" ]]; then
    log "✖ Không đọc được đường dẫn kết quả từ $2"
    notify_failure "$2 (không parse được output)" "$3"
    exit 1
  fi
}

log "=== Bắt đầu lượt chạy $RUN_DATE (định dạng: $FORMAT) ==="

# --- Stage 0: chọn chủ đề -----------------------------------------------------
TOPIC_ID=""
STORY_ID=""
if [[ -n "$STORY_ARG" ]]; then
  # `auto` để scripts.story_bank chọn theo ngày lên sóng; mã thoát 3 nghĩa là
  # kho không còn truyện phù hợp (khác lỗi thật), khi đó rơi về --topic auto.
  if [[ "$STORY_ARG" == "auto" ]]; then
    PICK_LOG="$LOG_DIR/00-pick.log"
    if STORY_ID="$($RUNNER scripts.story_bank --pick 2>"$PICK_LOG")"; then
      STORY_ID="${STORY_ID//[[:space:]]/}"
    else
      PICK_CODE=$?
      STORY_ID=""
      if (( PICK_CODE == 3 )); then
        log "CẢNH BÁO: kho truyện không còn truyện phù hợp, quay về --topic auto."
        TOPIC_ARG="${AUDIOBOOK_TOPIC:-auto}"
        STORY_ARG=""
      else
        log "CẢNH BÁO: không đọc được kho truyện (mã $PICK_CODE), quay về --topic auto."
        cat "$PICK_LOG" >>"$LOG_FILE" 2>/dev/null || true
        TOPIC_ARG="${AUDIOBOOK_TOPIC:-auto}"
        STORY_ARG=""
      fi
    fi
  else
    STORY_ID="$STORY_ARG"
  fi
fi

if [[ -n "$STORY_ID" ]]; then
  STAGE1_ARGS=(--story "$STORY_ID")
  SLUG="story-$STORY_ID"
  log "Truyện từ kho: #$STORY_ID"
elif [[ -n "$TOPIC_ARG" ]]; then
  # Chủ đề trọng tâm: không cần bắt trend. `auto` được scripts.cli giải thành id
  # theo thứ trong tuần; id thật đọc lại từ log stage 1 ("Chủ đề: <id>").
  STAGE1_ARGS=(--topic "$TOPIC_ARG")
  SLUG="$TOPIC_ARG"
  log "Chủ đề: $TOPIC_ARG"
elif [[ "$USE_TREND" -eq 1 ]]; then
  TREND_LOG="$LOG_DIR/00-trend.log"
  run_stage "Stage 0: Bắt trend" "$TREND_LOG" $RUNNER trend.cli
  IDEA_FILE="$(extract 'Đã lưu ý tưởng: (.+\.txt)' "$TREND_LOG")"
  require "$IDEA_FILE" "Stage 0: Bắt trend" "$TREND_LOG"
  SLUG="$(extract 'Slug: (.+)' "$TREND_LOG")"
  require "$SLUG" "Stage 0: Bắt trend" "$TREND_LOG"
  STAGE1_ARGS=(--idea-file "$IDEA_FILE" --label "$SLUG")
  log "Chủ đề hôm nay: $SLUG"
else
  SLUG="$TROPE_ID"
  STAGE1_ARGS=("$TROPE_ID")
  log "Dùng trope chỉ định: $TROPE_ID"
fi

# --- Stage 1: kịch bản --------------------------------------------------------
SCRIPT_LOG="$LOG_DIR/01-script.log"
run_stage "Stage 1: Kịch bản" "$SCRIPT_LOG" $RUNNER scripts.cli "${STAGE1_ARGS[@]}" --format "$FORMAT"
SCRIPT_PATH="$(extract 'Đã lưu kịch bản: ([^[:space:]]+\.json).*' "$SCRIPT_LOG")"
require "$SCRIPT_PATH" "Stage 1: Kịch bản" "$SCRIPT_LOG"
# Chế độ kho cũng cần chủ đề thật (playlist theo chủ đề ở stage 8, --slug cho
# notify): truyện trong kho có sẵn trường topic, stage 1 in ra như chế độ --topic.
if [[ -n "$TOPIC_ARG" || -n "$STORY_ID" ]]; then
  TOPIC_ID="$(extract 'Chủ đề: ([a-z_]+)' "$SCRIPT_LOG")"
  require "$TOPIC_ID" "Stage 1: Kịch bản" "$SCRIPT_LOG"
  SLUG="$TOPIC_ID"
  log "Chủ đề hôm nay: $TOPIC_ID"
fi

# --- Stage 2: TTS -------------------------------------------------------------
TTS_LOG="$LOG_DIR/02-tts.log"
run_stage "Stage 2: TTS" "$TTS_LOG" $RUNNER tts.cli "$SCRIPT_PATH"
AUDIO_JSON="$(extract 'Metadata: ([^[:space:]]+\.json)' "$TTS_LOG")"
require "$AUDIO_JSON" "Stage 2: TTS" "$TTS_LOG"

# --- Stage 3: ảnh nền ---------------------------------------------------------
IMAGES_LOG="$LOG_DIR/03-images.log"
# Stage 3 cần mốc câu của stage 2 để chia mỗi chương thành cảnh ~50s.
run_stage "Stage 3: Ảnh nền" "$IMAGES_LOG" $RUNNER images.cli "$SCRIPT_PATH" "$AUDIO_JSON"
IMAGES_JSON="$(extract 'Metadata: ([^[:space:]]+\.json)' "$IMAGES_LOG")"
require "$IMAGES_JSON" "Stage 3: Ảnh nền" "$IMAGES_LOG"

# --- Stage 4: render ----------------------------------------------------------
# full (mặc định từ 24/09): 1 video cả truyện = cold open 20-30s từ đoạn sảng
# nhất + mọi chương + card kết 8s (episodes/full.py). episodes (22/09): cắt 3
# tập theo episodes/plan.py. Cả hai ghi manifest mà stage 5/6/8 đọc (có trường
# "format" và "topic").
VIDEO_LOG="$LOG_DIR/04-episodes.log"
run_stage "Stage 4: Render video" "$VIDEO_LOG" \
  $RUNNER episodes.cli "$SCRIPT_PATH" "$AUDIO_JSON" "$IMAGES_JSON" --format "$FORMAT"
EPISODES_MANIFEST="$(extract 'Manifest: ([^[:space:]]+\.json)' "$VIDEO_LOG")"
require "$EPISODES_MANIFEST" "Stage 4: Render video" "$VIDEO_LOG"
EPISODE_COUNT="$(extract 'Đã render ([0-9]+) [^[:space:]]+ vào .+' "$VIDEO_LOG")"
require "$EPISODE_COUNT" "Stage 4: Render video" "$VIDEO_LOG"

# --- Stage 5: thumbnail -------------------------------------------------------
# Kịch bản chủ đề: layout "linh vật sticker + cả câu tiêu đề", bản A + bản B
# (-thumbnail-b.png cho Test & compare). Chế độ tập: thêm badge "TẬP N/3".
THUMB_LOG="$LOG_DIR/05-thumbnail.log"
run_stage "Stage 5: Thumbnail" "$THUMB_LOG" \
  $RUNNER thumbnail.cli "$SCRIPT_PATH" --episodes "$EPISODES_MANIFEST"
THUMBNAIL_PATH="$(extract 'Đã lưu thumbnail: ([^[:space:]]+\.png)' "$THUMB_LOG")"
require "$THUMBNAIL_PATH" "Stage 5: Thumbnail" "$THUMB_LOG"

# --- Stage 6: SEO metadata ----------------------------------------------------
# Một lần Gemini cho cả truyện, rồi tiêu đề/mô tả/bình luận ghim cho từng tập;
# đổi tên mp4 từng tập sang slug SEO. Danh sách tập nằm trong METADATA_INDEX.
META_LOG="$LOG_DIR/06-metadata.log"
run_stage "Stage 6: SEO Metadata" "$META_LOG" \
  $RUNNER metadata.cli "$SCRIPT_PATH" --episodes "$EPISODES_MANIFEST"
METADATA_INDEX="$(extract 'Danh sách: ([^[:space:]]+\.json)' "$META_LOG")"
require "$METADATA_INDEX" "Stage 6: SEO Metadata" "$META_LOG"
# Video chính của lượt chạy (bản full, hoặc tập 1) sau khi đổi tên: dùng cho thông báo.
if [[ "$FORMAT" == "full" ]]; then
  FINAL_VIDEO="$(extract 'Video full đã đổi tên: ([^[:space:]]+\.mp4)' "$META_LOG")"
else
  FINAL_VIDEO="$(extract 'Video tập 1 đã đổi tên: ([^[:space:]]+\.mp4)' "$META_LOG")"
fi
require "$FINAL_VIDEO" "Stage 6: SEO Metadata" "$META_LOG"

TITLE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["story_title"])' "$METADATA_INDEX")"

# --- Stage 7: series short (không chặn lượt chạy nếu hỏng) --------------------
# Lúc này video dài, thumbnail và metadata SEO đã dựng xong hết. Stage này chỉ
# cắt file audio đã có sẵn theo mốc câu (không gọi Gemini, không TTS lại), nhưng
# vẫn có thể hỏng vì lý do khác (Remotion, props sai...) — một short hỏng không
# được làm một tập đã thành công báo thành lượt chạy thất bại. Vì vậy stage này
# KHÔNG dùng run_stage/require: lỗi chỉ ghi log cảnh báo, không gọi
# notify_failure, không exit.
SHORT_LOG="$LOG_DIR/07-short.log"
SHORT_COUNT=""
log "▶ Stage 7: Short"
# --script: kịch bản chủ đề có 3 đoạn hài/sảng (short_beats) -> 3 Shorts mở bằng
# câu thoại đó; kịch bản cũ không có thì shorts.cli rải 3 trích đoạn như trước.
if $RUNNER shorts.cli "$AUDIO_JSON" "$IMAGES_JSON" --script "$SCRIPT_PATH" >"$SHORT_LOG" 2>&1; then
  cat "$SHORT_LOG" >>"$LOG_FILE"
  SHORT_COUNT="$(extract 'Đã render ([0-9]+) short vào .+' "$SHORT_LOG")"
  if [[ -z "$SHORT_COUNT" ]]; then
    log "CẢNH BÁO: Stage 7: Short chạy xong nhưng không đọc được số phần kết quả. Xem $SHORT_LOG"
  fi
else
  cat "$SHORT_LOG" >>"$LOG_FILE"
  log "CẢNH BÁO: Stage 7: Short THẤT BẠI, nhưng video dài vẫn ổn, không dừng lượt chạy. Xem $SHORT_LOG"
  log "  Dựng lại tay: $RUNNER shorts.cli \"$AUDIO_JSON\" \"$IMAGES_JSON\" --script \"$SCRIPT_PATH\""
fi

if [[ "$DO_UPLOAD" -eq 0 ]]; then
  DURATION="$(human_duration $(($(date +%s) - START_TS)))"
  log "✔ Đã dựng xong sau $DURATION. Video: $FINAL_VIDEO"
  if [[ "$FORMAT" == "full" ]]; then
    log "  Full: $EPISODE_COUNT video trong output/episodes (metadata: $METADATA_INDEX)"
  else
    log "  Tập: $EPISODE_COUNT tập trong output/episodes (metadata: $METADATA_INDEX)"
  fi
  [[ -n "$SHORT_COUNT" ]] && log "  Short: $SHORT_COUNT trích đoạn trong output/shorts"
  $RUNNER notify.cli success \
    --title "$TITLE" \
    --video "$FINAL_VIDEO" \
    --slug "$SLUG" \
    --duration "$DURATION" >>"$LOG_FILE" 2>&1 || \
    log "CẢNH BÁO: video đã dựng xong nhưng không gửi được thông báo."
  exit 0
fi

# --- Stage 8: upload YouTube (chỉ khi có --upload) ---------------------------
# full: 1 video private + publishAt 20h, thêm vào playlist CHỦ ĐỀ, bình luận câu
# hỏi chọn phe, 3 Shorts trỏ về video full; ghi video_id/publishAt vào
# output/metadata/index.jsonl. episodes: 3 tập hẹn giờ 20h mỗi ngày một tập như
# 22/09. Ghim bình luận vẫn làm tay trong Studio.
UPLOAD_LOG="$LOG_DIR/08-upload.log"
SHORTS_PREFIX="$(extract 'Đã render short: (.+)-part-01\.mp4' "$SHORT_LOG")"
UPLOAD_ARGS=("$METADATA_INDEX")
[[ -n "$SHORTS_PREFIX" ]] && UPLOAD_ARGS+=(--shorts-prefix "$SHORTS_PREFIX")
run_stage "Stage 8: Upload YouTube" "$UPLOAD_LOG" \
  $RUNNER upload.episodes_cli "${UPLOAD_ARGS[@]}"
VIDEO_URL="$(extract 'Đã upload: ([^[:space:]]+)' "$UPLOAD_LOG")"
require "$VIDEO_URL" "Stage 8: Upload YouTube" "$UPLOAD_LOG"

DURATION="$(human_duration $(($(date +%s) - START_TS)))"
log "✔ Hoàn thành: $VIDEO_URL ($DURATION)"

$RUNNER notify.cli success \
  --title "$TITLE" \
  --video "$FINAL_VIDEO" \
  --url "$VIDEO_URL" \
  --slug "$SLUG" \
  --duration "$DURATION" >>"$LOG_FILE" 2>&1 || \
  log "CẢNH BÁO: video đã lên nhưng không gửi được thông báo."
