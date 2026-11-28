#!/bin/bash
# Bọc một phiên Claude Code chạy nền cho giám đốc kênh (xem docs/superpowers/specs/2026-11-28-daily-director-design.md).
#
#   scripts/director.sh sang     08:00  đọc số hai kênh, quyết hôm nay, (đợt 2) gọi nhà máy, báo cáo
#   scripts/director.sh chieu    17:30  soát tranh, chữa, đăng, báo cáo
#
# Prompt của từng phiên nằm ở .claude/skills/channel-director/prompt-<sang|chieu>.md và được nhúng nguyên văn.
# Log: $DIRECTOR_OUT/<ngày>/claude-<sang|chieu>.log (DIRECTOR_OUT mặc định output/director).
# claude thiếu hoặc thoát mã khác 0 -> gửi Telegram (notify.cli text) và thoát 1. Không bao giờ treo: launchd dự phòng lo phần còn lại.
# Phiên chạy không có người nên bỏ hỏi quyền từng lệnh; rào cản nằm trong prompt và trong mã (khóa ngày, bộ chặn 1 video/ngày).
# Biến cho test: DIRECTOR_NO_CAFFEINATE=1 (không caffeinate), DIRECTOR_NOTIFY=<tệp> (ghi tin thay vì gọi Telegram), CLAUDE_BIN.
set -u

MODE="${1:-}"
case "$MODE" in
  sang)  MAX_TURNS=60 ;;
  chieu) MAX_TURNS=120 ;;
  *) echo "Cách dùng: scripts/director.sh sang|chieu" >&2; exit 2 ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
# launchd chạy với PATH tối thiểu: thêm chỗ cài claude, uv, brew.
export PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"   # nối sau để PATH người gọi (và claude giả trong test) được ưu tiên
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

OUT_BASE="${DIRECTOR_OUT:-$REPO_ROOT/output/director}"
# Ngày chốt MỘT lần lúc bắt đầu (giờ Việt Nam) và truyền cho mọi lệnh con qua DIRECTOR_DAY: phiên vắt qua nửa đêm
# vẫn ghi vào đúng thư mục ngày; director.paths.today() ưu tiên biến này.
DAY="${DIRECTOR_DAY:-$(TZ=Asia/Ho_Chi_Minh date +%F)}"
export DIRECTOR_DAY="$DAY"
OUT_DIR="$OUT_BASE/$DAY"
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/claude-$MODE.log"
PROMPT="$REPO_ROOT/.claude/skills/channel-director/prompt-$MODE.md"
SETTINGS="$REPO_ROOT/.claude/skills/channel-director/settings.json"   # chặn đọc .env và tệp token trong phiên nền
SKIP_PERMISSIONS="--dangerously-skip-permissions"
TIMEOUT_S="${DIRECTOR_TIMEOUT:-3600}"                                 # không phiên nào dài quá một giờ (spec)

notify() {
  # $1: nội dung. Test đặt DIRECTOR_NOTIFY để ghi ra tệp; thật thì gửi Telegram, lỗi gửi không làm hỏng mã thoát.
  if [[ -n "${DIRECTOR_NOTIFY:-}" ]]; then
    printf '%s\n' "$1" >> "$DIRECTOR_NOTIFY"
  else
    uv run python -m notify.cli text --text "$1" >>"$LOG" 2>&1 || true
  fi
}

CLAUDE="${CLAUDE_BIN:-}"
if [[ -z "$CLAUDE" ]]; then
  CLAUDE="$(command -v claude 2>/dev/null || true)"
fi
if [[ -z "$CLAUDE" || ! -x "$CLAUDE" ]]; then
  for c in "$HOME/.local/bin/claude" /opt/homebrew/bin/claude /usr/local/bin/claude; do
    [[ -x "$c" ]] && CLAUDE="$c" && break
  done
fi
if [[ -z "$CLAUDE" || ! -x "$CLAUDE" ]]; then
  echo "$(date '+%H:%M:%S') không thấy lệnh claude (CLAUDE_BIN=${CLAUDE_BIN:-trống})" >>"$LOG"
  notify "Giám đốc kênh: phiên $MODE $DAY không chạy được vì không thấy lệnh claude. Xem $LOG"
  exit 1
fi
if [[ ! -f "$PROMPT" ]]; then
  echo "$(date '+%H:%M:%S') thiếu prompt $PROMPT" >>"$LOG"
  notify "Giám đốc kênh: phiên $MODE $DAY thiếu tệp prompt $PROMPT"
  exit 1
fi

RUN=()
if [[ "${DIRECTOR_NO_CAFFEINATE:-0}" != "1" ]]; then
  RUN=(/usr/bin/caffeinate -i)
fi
# Nhúng ngày vào prompt: mọi chỗ "<hôm nay>" thành ngày thật, cộng một dòng đầu nêu ngày và thư mục làm việc.
PROMPT_TEXT="Hôm nay là $DAY (giờ Việt Nam); thư mục làm việc của phiên: $OUT_DIR. Biến DIRECTOR_DAY=$DAY đã đặt cho mọi lệnh.
$(sed "s|<hôm nay>|$DAY|g" "$PROMPT")"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') phiên $MODE bắt đầu ($CLAUDE, max-turns $MAX_TURNS, tối đa ${TIMEOUT_S}s) ===" >>"$LOG"
"${RUN[@]+"${RUN[@]}"}" "$CLAUDE" -p "$PROMPT_TEXT" \
  "$SKIP_PERMISSIONS" \
  --settings "$SETTINGS" \
  --add-dir /Users/lee/Project/Apps/lemo \
  --max-turns "$MAX_TURNS" \
  --output-format text >>"$LOG" 2>&1 &
PID=$!
# Đồng hồ chặn phiên treo (macOS không có `timeout`): quá giờ thì giết tiến trình và báo.
# Tách stdio của đồng hồ khỏi tiến trình cha, nếu không `sleep` mồ côi giữ ống stdout của launchd/test tới khi hết giờ.
( sleep "$TIMEOUT_S"; kill "$PID" 2>/dev/null && echo "$(date '+%H:%M:%S') quá ${TIMEOUT_S}s, đã dừng phiên" >>"$LOG" ) </dev/null >/dev/null 2>&1 &
WATCHDOG=$!
wait "$PID"
CODE=$?
pkill -P "$WATCHDOG" 2>/dev/null; kill "$WATCHDOG" 2>/dev/null; wait "$WATCHDOG" 2>/dev/null
echo "=== $(date '+%Y-%m-%d %H:%M:%S') phiên $MODE kết thúc, mã $CODE ===" >>"$LOG"
if grep -q "quá ${TIMEOUT_S}s, đã dừng phiên" "$LOG"; then
  notify "Giám đốc kênh: phiên $MODE $DAY quá giờ (${TIMEOUT_S}s), đã dừng. Xem $LOG"
  exit 1
fi
if (( CODE != 0 )); then
  notify "Giám đốc kênh: phiên $MODE $DAY hỏng, mã $CODE. Xem $LOG"
  exit 1
fi
exit 0
