"""scripts/daily_fallback.sh (launchd 10:30): chỉ chạy run_daily.sh --upload khi chưa có khóa ngày và hôm nay là ngày phát kênh chính."""
import os
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fake_run_daily(tmp_path):
    f = tmp_path / "run_daily_gia.sh"
    f.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$FAKE_RUN_LOG"\n', encoding="utf-8")
    f.chmod(0o755)
    return f


def _env(tmp_path, weekdays):
    return {**os.environ, "RUN_DAILY": str(_fake_run_daily(tmp_path)), "FAKE_RUN_LOG": str(tmp_path / "run.log"),
            "DIRECTOR_OUT": str(tmp_path / "out"), "AUDIOBOOK_RELEASE_WEEKDAYS": weekdays}


def _run(env):
    return subprocess.run(["bash", str(ROOT / "scripts" / "daily_fallback.sh")], cwd=ROOT, env=env, capture_output=True, text=True)


def test_khong_khoa_dung_thu_thi_chay_va_khoa(tmp_path):
    env = _env(tmp_path, ",".join(str(i) for i in range(7)))
    r = _run(env)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "run.log").read_text(encoding="utf-8").strip() == "--upload"
    lock = tmp_path / "out" / date.today().isoformat() / "da-goi-nha-may"
    assert lock.exists() and "du-phong" in lock.read_text(encoding="utf-8")


def test_da_co_khoa_thi_khong_chay(tmp_path):
    env = _env(tmp_path, ",".join(str(i) for i in range(7)))
    lock = tmp_path / "out" / date.today().isoformat() / "da-goi-nha-may"
    lock.parent.mkdir(parents=True)
    lock.write_text("x")
    r = _run(env)
    assert r.returncode == 0 and not (tmp_path / "run.log").exists()
    assert "đã" in r.stdout


def test_sai_thu_thi_khong_chay(tmp_path):
    khac = str((date.today().weekday() + 1) % 7)
    r = _run(_env(tmp_path, khac))
    assert r.returncode == 0 and not (tmp_path / "run.log").exists()
    assert not (tmp_path / "out" / date.today().isoformat() / "da-goi-nha-may").exists()
