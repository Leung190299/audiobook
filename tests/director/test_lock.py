from datetime import date, datetime, timezone

from director import lock
from director.lock import acquire, is_locked
from director.paths import today


def test_today_theo_gio_viet_nam():
    # 23:30 UTC ngày 27 là 06:30 ngày 28 giờ Việt Nam
    assert today(datetime(2026, 11, 27, 23, 30, tzinfo=timezone.utc)) == date(2026, 11, 28)


def test_acquire_chi_mot_lan(tmp_path):
    assert acquire(date(2026, 11, 28), tmp_path) is True
    assert acquire(date(2026, 11, 28), tmp_path) is False
    assert is_locked(date(2026, 11, 28), tmp_path)
    assert not is_locked(date(2026, 11, 29), tmp_path)


def test_cli_check(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "DIRECTOR_DIR", tmp_path)
    assert lock.main(["--check", "--date", "2026-11-28"]) == 3
    assert lock.main(["--date", "2026-11-28"]) == 0
    assert lock.main(["--check", "--date", "2026-11-28"]) == 0


def test_today_uu_tien_bien_DIRECTOR_DAY(monkeypatch):
    monkeypatch.setenv("DIRECTOR_DAY", "2026-11-28")
    assert today(datetime(2026, 11, 29, 1, 0, tzinfo=timezone.utc)) == date(2026, 11, 28)


def test_acquire_ghi_nguon(tmp_path):
    assert acquire(date(2026, 11, 28), tmp_path, by="du-phong") is True
    assert "du-phong" in lock.lock_path(date(2026, 11, 28), tmp_path).read_text(encoding="utf-8")
