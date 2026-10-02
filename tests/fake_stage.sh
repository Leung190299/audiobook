#!/bin/bash
# Stage giả dùng cho tests/test_run_daily.py.
#
# Đóng vai `uv run python -m <module>`: in ra đúng định dạng stdout mà stage thật
# in, để test kiểm tra được dây chuyền parse trong run_daily.sh mà không phải
# chạy thật 50 phút.
#
# Điều khiển bằng biến môi trường:
#   FAKE_LOG            file ghi lại mọi lệnh đã gọi (để test assert)
#   FAKE_FAIL_MODULE    module này sẽ exit 1
#   FAKE_GARBAGE_MODULE module này exit 0 nhưng in output không parse được
#   FAKE_NO_RENAME      metadata.cli không in dòng "Video tập N đã đổi tên"
#   FAKE_NO_THUMB       upload.cli báo thumbnail chưa đặt
#   FAKE_NO_STORY       scripts.story_bank --pick thoát 3 (kho hết truyện)
#   FAKE_STORY_ID       id mà scripts.story_bank --pick in ra (mặc định 42)

set -u

module="$1"; shift
# Gộp về một dòng: tham số --text của notify.cli có chứa xuống dòng.
[[ -n "${FAKE_LOG:-}" ]] && echo "$module $*" | tr '\n' ' ' >>"$FAKE_LOG" && echo >>"$FAKE_LOG"

[[ "$module" == "${FAKE_FAIL_MODULE:-}" ]] && { echo "Traceback giả: $module hỏng" >&2; exit 1; }
[[ "$module" == "${FAKE_GARBAGE_MODULE:-}" ]] && { echo "xong rồi nhé"; exit 0; }

all_args="$*"
is_full=0
[[ "$all_args" == *"--format full"* || "$all_args" == *"-full.json"* ]] && is_full=1

case "$module" in
  scripts.story_bank)
    # --mark-used đánh dấu truyện đã dựng xong; --pick in đúng một id (hoặc
    # thoát 3 khi kho hết); --upcoming in lịch.
    if [[ " $* " == *" --mark-used "* ]]; then
      echo "Đã đánh dấu truyện là đã dựng."
      exit 0
    fi
    if [[ " $* " == *" --pick "* ]]; then
      [[ -n "${FAKE_NO_STORY:-}" ]] && exit 3
      echo "${FAKE_STORY_ID:-42}"
      exit 0
    fi
    days=7
    for ((i = 1; i <= $#; i++)); do
      [[ "${!i}" == "--upcoming" ]] && { j=$((i + 1)); days="${!j}"; }
    done
    for ((d = 1; d <= days; d++)); do
      echo "2026-09-2$d      #$((40 + d))   A  ho_hang_viet       Truyện giả số $d"
    done
    exit 0
    ;;
  trend.cli)
    echo "Đã lưu ý tưởng: output/ideas/me_chong_giau_cua-20260813T010000Z.txt"
    echo "JSON: output/ideas/me_chong_giau_cua-20260813T010000Z.json"
    echo "Slug: me_chong_giau_cua"
    echo "Tiêu đề gợi ý: Mẹ chồng giấu sổ đỏ"
    echo "Bám trend: chủ đề tranh chấp tài sản đang lên"
    ;;
  scripts.cli)
    if [[ "$all_args" == *"--topic"* || "$all_args" == *"--story"* ]]; then
      echo "Chủ đề: ${FAKE_TOPIC:-ho_hang_viet}"
      echo "Bối cảnh: Tết về quê, cả họ tra hỏi lương thưởng"
    fi
    echo "Định dạng: x"
    echo "Đã lưu kịch bản: output/scripts/me_chong_giau_cua-20260813T011000Z.json (11500 từ, 16 chương)"
    ;;
  tts.cli)
    echo "Đã lưu audio: output/audio/me_chong_giau_cua-20260813T012500Z.wav (3100 giây)"
    echo "Metadata: output/audio/me_chong_giau_cua-20260813T012500Z.json"
    ;;
  images.cli)
    echo "Đã lưu 64 ảnh vào output/images"
    echo "Metadata: output/images/me_chong_giau_cua-20260813T013500Z.json"
    ;;
  episodes.cli)
    if [[ $is_full -eq 1 ]]; then
      echo "Đã render video full: output/episodes/me_chong_giau_cua-20260813T015000Z-full.mp4"
      echo "Manifest: output/episodes/me_chong_giau_cua-20260813T015000Z-full.json"
      echo "Đã render 1 video vào output/episodes"
      exit 0
    fi
    echo "Đã render tập 1/3: output/episodes/me_chong_giau_cua-20260813T015000Z-ep-01.mp4"
    echo "Đã render tập 2/3: output/episodes/me_chong_giau_cua-20260813T015000Z-ep-02.mp4"
    echo "Đã render tập 3/3: output/episodes/me_chong_giau_cua-20260813T015000Z-ep-03.mp4"
    echo "Manifest: output/episodes/me_chong_giau_cua-20260813T015000Z-episodes.json"
    echo "Đã render 3 tập vào output/episodes"
    ;;
  thumbnail.cli)
    if [[ $is_full -eq 1 ]]; then
      echo "Đã lưu thumbnail: output/thumbnails/me_chong_giau_cua-20260813T015100Z-thumbnail-a.png"
      echo "Thumbnail B: output/thumbnails/me_chong_giau_cua-20260813T015100Z-thumbnail-b.png"
      exit 0
    fi
    echo "Đã lưu thumbnail: output/thumbnails/me_chong_giau_cua-20260813T015100Z.png"
    echo "Thumbnail tập 1/3: output/thumbnails/me_chong_giau_cua-20260813T015100Z-ep-01.png"
    echo "Thumbnail tập 2/3: output/thumbnails/me_chong_giau_cua-20260813T015100Z-ep-02.png"
    echo "Thumbnail tập 3/3: output/thumbnails/me_chong_giau_cua-20260813T015100Z-ep-03.png"
    ;;
  metadata.cli)
    if [[ $is_full -eq 1 ]]; then
      echo "Đã lưu metadata full: output/metadata/me_chong_giau_cua-20260813T015000Z-full.txt"
      [[ -z "${FAKE_NO_RENAME:-}" ]] && \
        echo "Video full đã đổi tên: output/episodes/me-chong-giau-so-do.mp4"
      echo "Danh sách: output/metadata/me_chong_giau_cua-20260813T015000Z-full.json"
      exit 0
    fi
    for n in 1 2 3; do
      echo "Đã lưu metadata tập $n/3: output/metadata/me_chong_giau_cua-20260813T015000Z-ep-0$n.txt"
      [[ -z "${FAKE_NO_RENAME:-}" ]] && \
        echo "Video tập $n đã đổi tên: output/episodes/me-chong-giau-so-do-tap-$n.mp4"
    done
    echo "Danh sách: output/metadata/me_chong_giau_cua-20260813T015000Z-episodes.json"
    ;;
  scripts.post_shorts)
    # --record chỉ ghi shorts_prefix vào chỉ mục; chỉ mục trong test là đường
    # dẫn giả nên không làm gì, chỉ cần FAKE_LOG ở trên đã ghi lại lệnh gọi.
    exit 0
    ;;
  shorts.cli)
    echo "Đã render short: output/shorts/me_chong_giau_cua-20260813T015300Z-part-01.mp4"
    echo "Metadata short: output/shorts/me_chong_giau_cua-20260813T015300Z-part-01.txt"
    echo "Đã render short: output/shorts/me_chong_giau_cua-20260813T015300Z-part-02.mp4"
    echo "Metadata short: output/shorts/me_chong_giau_cua-20260813T015300Z-part-02.txt"
    echo "Đã render 2 short vào output/shorts"
    ;;
  upload.episodes_cli)
    if [[ $is_full -eq 1 ]]; then
      echo "Full: Mẹ chồng giấu sổ đỏ — https://youtu.be/FAKEFULL1 (lên sóng 2026-08-13 20:00)"
      echo "Đã upload: https://youtu.be/FAKEFULL1"
      exit 0
    fi
    echo "Tập 1/3: Mẹ chồng giấu sổ đỏ | Tập 1/3 — https://youtu.be/FAKE12345 (lên sóng 2026-08-13 20:00)"
    echo "Tập 2/3: Mẹ chồng giấu sổ đỏ | Tập 2/3 — https://youtu.be/FAKE22345 (lên sóng 2026-08-14 20:00)"
    echo "Tập 3/3: Mẹ chồng giấu sổ đỏ | Tập 3/3 — https://youtu.be/FAKE32345 (lên sóng 2026-08-15 20:00)"
    echo "Đã upload: https://youtu.be/FAKE12345"
    ;;
  notify.cli)
    echo "Đã gửi thông báo Telegram."
    ;;
  *)
    echo "Stage giả không biết module: $module" >&2
    exit 2
    ;;
esac
exit 0
