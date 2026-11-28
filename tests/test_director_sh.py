"""scripts/director.sh: bọc `claude -p` cho launchd. Test chạy với `claude` giả (tests/fake_claude.sh)."""
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAKE = ROOT / "tests" / "fake_claude.sh"


def _env(tmp_path, **extra):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    shutil.copy(FAKE, bin_dir / "claude")
    (bin_dir / "claude").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "CLAUDE_BIN": str(bin_dir / "claude"), "FAKE_CLAUDE_LOG": str(tmp_path / "args"),
           "DIRECTOR_OUT": str(tmp_path / "out"), "DIRECTOR_NO_CAFFEINATE": "1", "DIRECTOR_NOTIFY": str(tmp_path / "notify")}
    env.update(extra)
    return env


def _run(mode, env):
    return subprocess.run(["bash", str(ROOT / "scripts" / "director.sh"), mode], cwd=ROOT, env=env, capture_output=True, text=True)


def test_director_sh_goi_claude_dung_tham_so(tmp_path):
    env = _env(tmp_path)
    r = _run("sang", env)
    args = (tmp_path / "args").read_text(encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "--dangerously-skip-permissions" in args
    assert "--max-turns\n60\n" in args
    assert "--add-dir\n/Users/lee/Project/Apps/lemo\n" in args
    assert "--output-format\ntext\n" in args
    assert "director.report" in args                      # prompt sáng được nhúng nguyên văn
    assert f"Hôm nay là {date.today().isoformat()}" in args  # ngày chốt lúc bắt đầu phiên, nhúng vào prompt
    assert "<hôm nay>" not in args
    assert "--settings\n" in args and "channel-director/settings.json" in args
    log = tmp_path / "out" / date.today().isoformat() / "claude-sang.log"
    assert log.exists() and "fake claude ok" in log.read_text(encoding="utf-8")
    assert not (tmp_path / "notify").exists()


def test_director_sh_chieu_max_turns_120(tmp_path):
    env = _env(tmp_path)
    assert _run("chieu", env).returncode == 0
    args = (tmp_path / "args").read_text(encoding="utf-8")
    assert "--max-turns\n120\n" in args and "quyet-dinh.json" in args


def test_director_sh_claude_loi_thi_bao_telegram(tmp_path):
    env = _env(tmp_path, FAKE_CLAUDE_EXIT="2")
    r = _run("chieu", env)
    assert r.returncode == 1
    assert "mã 2" in (tmp_path / "notify").read_text(encoding="utf-8")


def test_director_sh_khong_co_claude_thi_bao(tmp_path):
    env = _env(tmp_path)
    env["PATH"] = "/usr/bin:/bin"                        # không có claude
    env["CLAUDE_BIN"] = str(tmp_path / "khong-co")
    r = _run("sang", env)
    assert r.returncode == 1 and "claude" in (tmp_path / "notify").read_text(encoding="utf-8")


def test_director_sh_che_do_la_thi_loi(tmp_path):
    assert _run("toi", _env(tmp_path)).returncode == 2


def test_director_sh_qua_gio_thi_giet_va_bao(tmp_path):
    env = _env(tmp_path, FAKE_CLAUDE_SLEEP="5", DIRECTOR_TIMEOUT="1")
    r = _run("sang", env)
    assert r.returncode == 1
    assert "quá giờ" in (tmp_path / "notify").read_text(encoding="utf-8")


def test_settings_cua_giam_doc_chan_doc_tep_bi_mat():
    import json
    s = json.loads((ROOT / ".claude" / "skills" / "channel-director" / "settings.json").read_text(encoding="utf-8"))
    deny = " ".join(s["permissions"]["deny"])
    assert ".env" in deny and "youtube_token" in deny and "youtube_client_secret" in deny and ".youtube_token_" in deny
