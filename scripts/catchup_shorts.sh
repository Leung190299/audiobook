#!/bin/bash
# Vỏ bọc cho launchd: launchd chạy với PATH tối thiểu và không có locale, nên
# `uv` sẽ không tìm thấy và tiếng Việt có dấu sẽ vỡ. Bài học từ lượt hẹn giờ
# 04/09: chạy tay thì ổn, launchd thì chết vì thiếu PATH.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
export PYTHONIOENCODING=utf-8

if ! command -v uv >/dev/null 2>&1; then
  echo "Không tìm thấy 'uv' trong PATH: $PATH" >&2
  exit 3
fi

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] catchup_shorts ==="
exec uv run python -m scripts.catchup_shorts "$@"
