#!/bin/bash
# `claude` giả cho test scripts/director.sh: ghi toàn bộ tham số vào $FAKE_CLAUDE_LOG, thoát theo $FAKE_CLAUDE_EXIT (mặc định 0).
printf '%s\n' "$@" > "${FAKE_CLAUDE_LOG:?}"
echo "fake claude ok"
exit "${FAKE_CLAUDE_EXIT:-0}"
