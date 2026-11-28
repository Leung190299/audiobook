#!/bin/bash
# Lượt dự phòng 10:30 (launchd com.lee.audiobook.daily): chỉ chạy run_daily.sh --upload như trước đây KHI
#   - chưa có khóa "da-goi-nha-may" của hôm nay (phiên giám đốc sáng chưa gọi nhà máy, hoặc phiên đó hỏng), và
#   - hôm nay là ngày phát của kênh chính (AUDIOBOOK_RELEASE_WEEKDAYS, 0 = Thứ Hai).
# Chạy xong thì tự ghi khóa để không bao giờ có hai lượt dựng trong một ngày.
# Biến cho test: RUN_DAILY (script thay run_daily.sh), DIRECTOR_OUT (thư mục output/director).
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
export PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

OUT_BASE="${DIRECTOR_OUT:-$REPO_ROOT/output/director}"
DAY="$(date +%F)"
LOCK="$OUT_BASE/$DAY/da-goi-nha-may"
RUN_DAILY="${RUN_DAILY:-$REPO_ROOT/run_daily.sh}"

if [[ -e "$LOCK" ]]; then
  echo "$(date '+%H:%M:%S') Hôm nay đã gọi nhà máy ($LOCK). Lượt dự phòng không làm gì."
  exit 0
fi

# Đọc ngày phát của kênh chính: biến môi trường ưu tiên, rồi .env (bash không tự nạp .env).
WEEKDAYS="${AUDIOBOOK_RELEASE_WEEKDAYS:-}"
if [[ -z "$WEEKDAYS" && -f "$REPO_ROOT/.env" ]]; then
  WEEKDAYS="$(grep -E '^AUDIOBOOK_RELEASE_WEEKDAYS=' "$REPO_ROOT/.env" | tail -1 | cut -d= -f2- | tr -d '"'"'"' ')"
fi
if [[ -n "$WEEKDAYS" ]]; then
  DOW=$(( $(date +%u) - 1 ))
  if [[ ",$WEEKDAYS," != *",$DOW,"* ]]; then
    echo "$(date '+%H:%M:%S') Hôm nay không phải ngày phát của kênh chính (thứ $(date +%u); AUDIOBOOK_RELEASE_WEEKDAYS=$WEEKDAYS). Không dựng."
    exit 0
  fi
fi

mkdir -p "$(dirname "$LOCK")"
date '+%Y-%m-%dT%H:%M:%S%z' > "$LOCK"
echo "$(date '+%H:%M:%S') Chưa có phiên giám đốc gọi nhà máy: chạy dự phòng $RUN_DAILY --upload"
exec /bin/bash "$RUN_DAILY" --upload
