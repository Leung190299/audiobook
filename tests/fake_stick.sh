#!/bin/bash
# Bộ lệnh người que giả (lemo/stickman/kit/stick) cho tests/test_run_daily.py.
#
# Đóng vai `kit/stick <lệnh> <truyện> ...` ở Stage 4s: ghi lệnh vào FAKE_LOG như
# fake_stage.sh, và với `auto` in đúng các dòng mà run_daily.sh đọc, kèm tệp chỉ
# mục thật (run_daily đọc story_title từ đó). Thư mục truyện giả nằm cạnh kit.
#   FAKE_STICK_FAIL   lệnh này (import | auto) sẽ exit 1
set -u
cmd="$1"; shift
[[ -n "${FAKE_LOG:-}" ]] && echo "stick $cmd $*" | tr '\n' ' ' >>"$FAKE_LOG" && echo >>"$FAKE_LOG"
[[ "$cmd" == "${FAKE_STICK_FAIL:-}" ]] && { echo "lỗi giả: stick $cmd hỏng" >&2; exit 1; }
slug="${1:-}"
root="$(cd "$(dirname "$0")/.." && pwd)/stories/$slug"
case "$cmd" in
  import)
    mkdir -p "$root"
    echo "Đã tạo $root: 8 chương, giọng đọc 19.6 phút, story_id 1011"
    ;;
  auto)
    mkdir -p "$root/out" "$root/upload"
    printf '{"story_title": "Chị họ đòi chia quà", "story_id": 1011, "format": "full", "episodes": []}' >"$root/upload/$slug-full.json"
    echo "▶ autoboard"
    echo "Đã render 1 video vào $root/out"
    echo "Video full đã đổi tên: $root/out/$slug.mp4"
    echo "Đã lưu thumbnail: $root/upload/thumbnail.png"
    echo "Danh sách: $root/upload/$slug-full.json"
    ;;
  *)
    echo "stick giả không biết lệnh: $cmd" >&2
    exit 2
    ;;
esac
exit 0
