#!/bin/bash
# Dẫn qua toàn bộ khâu cài đặt cho lượt dựng video tự động hằng ngày.
# Chạy lại được nhiều lần: bước nào xong rồi thì bỏ qua.
#
#   ./setup.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
GREEN=$'\033[32m'; YELLOW=$'\033[33m'

step()  { printf '\n%s──── %s ────%s\n' "$BOLD" "$1" "$RESET"; }
ok()    { printf '%s✅ %s%s\n' "$GREEN" "$1" "$RESET"; }
skip()  { printf '%s⏭  %s%s\n' "$DIM" "$1" "$RESET"; }
warn()  { printf '%s⚠️  %s%s\n' "$YELLOW" "$1" "$RESET"; }

ask_yes() {
  local answer
  read -r -p "$1 [Y/n] " answer
  [[ -z "$answer" || "$answer" =~ ^[YyCc] ]]
}

ask_no() {
  local answer
  read -r -p "$1 [y/N] " answer
  [[ "$answer" =~ ^[YyCc] ]]
}

printf '%sCài đặt pipeline dựng truyện audio tự động%s\n' "$BOLD" "$RESET"
printf '%sPipeline dựng video xong rồi báo cho bạn; việc đăng lên YouTube bạn tự làm.%s\n' "$DIM" "$RESET"

# --- 1. Dependency ------------------------------------------------------------
step "1/5  Thư viện Python"
if uv sync; then
  ok "Đã đồng bộ dependency"
else
  warn "uv sync thất bại — xử lý xong hãy chạy lại script này"
  exit 1
fi

# --- 2. .env ------------------------------------------------------------------
step "2/5  File .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  ok "Đã tạo .env từ .env.example"
else
  skip ".env đã có"
fi

if grep -qE '^SECURE_1PSID=.+' .env; then
  skip "Cookie Gemini đã có"
else
  warn "Thiếu cookie Gemini — stage 1 và 3 sẽ crash ngay nếu không có"
  echo "   Mở gemini.google.com đã đăng nhập → DevTools → Application → Cookies"
  echo "   → copy giá trị __Secure-1PSID và __Secure-1PSIDTS vào .env"
  echo "   (tự mở .env bằng editor và điền, đừng dán vào cửa sổ này)"
fi

# --- 3. Remotion --------------------------------------------------------------
step "3/5  Remotion (stage 4 render video)"
if [[ -d remotion/node_modules ]]; then
  skip "node_modules đã có"
elif ask_yes "Chạy npm install trong remotion/ bây giờ?"; then
  (cd remotion && npm install) && ok "Đã cài Remotion"
else
  warn "Bỏ qua — stage 4 sẽ hỏng cho tới khi cài"
fi

# --- 4. Thông báo -------------------------------------------------------------
step "4/5  Thông báo khi dựng xong"
if grep -qE '^TELEGRAM_BOT_TOKEN=.+' .env; then
  skip "Đang dùng Telegram"
else
  echo "Mặc định: hiện thông báo trên màn hình macOS khi dựng xong — không cần cài gì."
  echo "Chỉ thấy được khi bạn đang ngồi trước máy."
  if ask_no "Muốn dùng Telegram thay thế để nhận cả khi đi vắng?"; then
    uv run python -m notify.setup || warn "Chưa xong — chạy lại: uv run python -m notify.setup"
  else
    skip "Dùng thông báo macOS"
  fi
fi

# --- 5. Kiểm tra + đặt lịch ---------------------------------------------------
step "5/5  Kiểm tra tổng thể"
uv run python -m preflight.cli --deep
PREFLIGHT_STATUS=$?

if [[ $PREFLIGHT_STATUS -ne 0 ]]; then
  warn "Còn mục chưa đạt ở trên — sửa xong chạy lại ./setup.sh"
  exit 1
fi

PLIST="$HOME/Library/LaunchAgents/com.lee.audiobook.daily.plist"
if [[ -f "$PLIST" ]]; then
  skip "Lịch launchd đã cài"
elif ask_yes "Nạp lịch dựng video 09:00 hằng ngày?"; then
  mkdir -p "$HOME/Library/LaunchAgents"
  cp launchd/com.lee.audiobook.daily.plist "$PLIST"
  launchctl load "$PLIST" && ok "Đã nạp lịch — 09:00 mỗi ngày"
else
  skip "Bỏ qua — chạy tay bằng ./run_daily.sh"
fi

cat <<'EOF'

Xong. Việc còn lại:

  ./run_daily.sh                             dựng một tập ngay bây giờ (~50 phút)
  launchctl start com.lee.audiobook.daily    kích lịch chạy ngay, không đợi 09:00

Video ra ở output/video/, thumbnail ở output/thumbnails/, tiêu đề + mô tả +
tag để dán vào YouTube ở output/metadata/<tên>.txt
Log mỗi lượt: output/daily/<ngày>/run.log

Nếu sau này muốn tự động đăng luôn lên YouTube, xem docs/DAILY_AUTOMATION.md
phần "Tự động đăng YouTube" rồi chạy ./run_daily.sh --upload
EOF
