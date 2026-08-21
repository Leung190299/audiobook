#!/bin/bash
# Dựng trọn một tập truyện audio mỗi ngày: bắt trend -> 6 stage -> báo khi xong.
# Mặc định KHÔNG đăng lên YouTube — bạn tự up. Thêm --upload nếu muốn tự động đăng.
#
#   ./run_daily.sh                              # chủ đề bắt trend (mặc định)
#   ./run_daily.sh --trope trong_sinh_bao_thu   # bỏ qua trend, dùng trope có sẵn
#   ./run_daily.sh --upload                     # dựng xong đăng luôn lên YouTube
#
# Mỗi lượt ghi log vào output/daily/<ngày>/. Lỗi ở bất kỳ stage nào cũng dừng ngay
# và bắn Telegram kèm phần cuối log của stage đó.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT" || exit 1

# launchd chạy với PATH tối thiểu và không có locale — nạp lại cả hai, nếu không
# `uv` sẽ không tìm thấy và `sed` sẽ vỡ khi gặp tiếng Việt có dấu.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
export PYTHONIOENCODING=utf-8

# Cách gọi từng stage. Test tích hợp thay biến này bằng stage giả để kiểm tra
# dây chuyền parse stdout mà không phải chạy thật 50 phút.
RUNNER="${AUDIOBOOK_RUNNER:-uv run python -m}"

RUN_DATE="$(date +%Y-%m-%d)"
LOG_DIR="$REPO_ROOT/output/daily/$RUN_DATE"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run.log"
START_TS=$(date +%s)

TROPE_ID=""
# Mặc định chỉ dựng video, không đăng. Đăng lên YouTube cần token OAuth và một
# project đã qua audit của Google mới ra public được — không đáng để bật mặc định.
DO_UPLOAD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --trope) TROPE_ID="${2:-}"; shift 2 ;;
    --upload) DO_UPLOAD=1; shift ;;
    --no-upload) shift ;;  # giữ lại cho tương thích, giờ đã là mặc định
    *) echo "Tham số không hiểu: $1" >&2; exit 2 ;;
  esac
done

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

log "=== Bắt đầu lượt chạy $RUN_DATE ==="

# --- Stage 0: chọn chủ đề -----------------------------------------------------
if [[ -z "$TROPE_ID" ]]; then
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
run_stage "Stage 1: Kịch bản" "$SCRIPT_LOG" $RUNNER scripts.cli "${STAGE1_ARGS[@]}"
SCRIPT_PATH="$(extract 'Đã lưu kịch bản: ([^[:space:]]+\.json).*' "$SCRIPT_LOG")"
require "$SCRIPT_PATH" "Stage 1: Kịch bản" "$SCRIPT_LOG"

# --- Stage 2: TTS -------------------------------------------------------------
TTS_LOG="$LOG_DIR/02-tts.log"
run_stage "Stage 2: TTS" "$TTS_LOG" $RUNNER tts.cli "$SCRIPT_PATH"
AUDIO_JSON="$(extract 'Metadata: ([^[:space:]]+\.json)' "$TTS_LOG")"
require "$AUDIO_JSON" "Stage 2: TTS" "$TTS_LOG"

# --- Stage 3: ảnh nền ---------------------------------------------------------
IMAGES_LOG="$LOG_DIR/03-images.log"
run_stage "Stage 3: Ảnh nền" "$IMAGES_LOG" $RUNNER images.cli "$SCRIPT_PATH"
IMAGES_JSON="$(extract 'Metadata: ([^[:space:]]+\.json)' "$IMAGES_LOG")"
require "$IMAGES_JSON" "Stage 3: Ảnh nền" "$IMAGES_LOG"

# --- Stage 4: render video ----------------------------------------------------
VIDEO_LOG="$LOG_DIR/04-video.log"
run_stage "Stage 4: Render video" "$VIDEO_LOG" \
  $RUNNER video.cli "$SCRIPT_PATH" "$AUDIO_JSON" "$IMAGES_JSON"
VIDEO_PATH="$(extract 'Đã render video vào ([^[:space:]]+\.mp4)' "$VIDEO_LOG")"
require "$VIDEO_PATH" "Stage 4: Render video" "$VIDEO_LOG"

# --- Stage 5: thumbnail -------------------------------------------------------
THUMB_LOG="$LOG_DIR/05-thumbnail.log"
run_stage "Stage 5: Thumbnail" "$THUMB_LOG" $RUNNER thumbnail.cli "$SCRIPT_PATH"
THUMBNAIL_PATH="$(extract 'Đã lưu thumbnail: ([^[:space:]]+\.png)' "$THUMB_LOG")"
require "$THUMBNAIL_PATH" "Stage 5: Thumbnail" "$THUMB_LOG"

# --- Stage 6: SEO metadata ----------------------------------------------------
META_LOG="$LOG_DIR/06-metadata.log"
run_stage "Stage 6: SEO Metadata" "$META_LOG" \
  $RUNNER metadata.cli "$SCRIPT_PATH" "$AUDIO_JSON" "$VIDEO_PATH"
METADATA_JSON="$(extract 'JSON: ([^[:space:]]+\.json)' "$META_LOG")"
require "$METADATA_JSON" "Stage 6: SEO Metadata" "$META_LOG"
# Stage 6 đổi tên file .mp4 tại chỗ — phải dùng tên mới, tên cũ không còn tồn tại.
FINAL_VIDEO="$(extract 'Video đã đổi tên: ([^[:space:]]+\.mp4)' "$META_LOG")"
[[ -z "$FINAL_VIDEO" ]] && FINAL_VIDEO="$VIDEO_PATH"

TITLE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["title"])' "$METADATA_JSON")"

if [[ "$DO_UPLOAD" -eq 0 ]]; then
  DURATION="$(human_duration $(($(date +%s) - START_TS)))"
  log "✔ Đã dựng xong sau $DURATION. Video: $FINAL_VIDEO"
  $RUNNER notify.cli success \
    --title "$TITLE" \
    --video "$FINAL_VIDEO" \
    --slug "$SLUG" \
    --duration "$DURATION" >>"$LOG_FILE" 2>&1 || \
    log "CẢNH BÁO: video đã dựng xong nhưng không gửi được thông báo."
  exit 0
fi

# --- Stage 7: upload YouTube (chỉ khi có --upload) ---------------------------
UPLOAD_LOG="$LOG_DIR/07-upload.log"
run_stage "Stage 7: Upload YouTube" "$UPLOAD_LOG" \
  $RUNNER upload.cli "$FINAL_VIDEO" "$METADATA_JSON" --thumbnail "$THUMBNAIL_PATH"
VIDEO_URL="$(extract 'Đã upload: ([^[:space:]]+)' "$UPLOAD_LOG")"
require "$VIDEO_URL" "Stage 7: Upload YouTube" "$UPLOAD_LOG"

DURATION="$(human_duration $(($(date +%s) - START_TS)))"
log "✔ Hoàn thành: $VIDEO_URL ($DURATION)"

$RUNNER notify.cli success \
  --title "$TITLE" \
  --video "$FINAL_VIDEO" \
  --url "$VIDEO_URL" \
  --slug "$SLUG" \
  --duration "$DURATION" >>"$LOG_FILE" 2>&1 || \
  log "CẢNH BÁO: video đã lên nhưng không gửi được thông báo."
