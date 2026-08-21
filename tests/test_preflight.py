"""Test cho preflight — chỉ phần thuần logic, không gọi mạng."""

import json
from pathlib import Path

import pytest

from preflight.checks import (
    FAIL,
    OK,
    WARN,
    Check,
    check_env_file,
    check_gemini_cookies,
    check_run_script,
    check_trend_config,
    check_voice_config,
    check_youtube_client_secret,
    check_youtube_token,
    format_report,
    summarize,
)


def test_thieu_env_thi_bao_fail_kem_cach_sua(tmp_path: Path):
    check = check_env_file(tmp_path)
    assert check.status == FAIL
    assert ".env.example" in check.fix


def test_co_env_thi_dat(tmp_path: Path):
    (tmp_path / ".env").write_text("SECURE_1PSID=x", encoding="utf-8")
    assert check_env_file(tmp_path).status == OK


def test_thieu_cookie_gemini_neu_ro_ten_bien(monkeypatch):
    monkeypatch.delenv("SECURE_1PSID", raising=False)
    monkeypatch.setenv("SECURE_1PSIDTS", "abc")
    check = check_gemini_cookies()
    assert check.status == FAIL
    assert "SECURE_1PSID" in check.detail
    assert "SECURE_1PSIDTS" not in check.detail


def test_du_cookie_gemini_thi_dat(monkeypatch):
    monkeypatch.setenv("SECURE_1PSID", "a")
    monkeypatch.setenv("SECURE_1PSIDTS", "b")
    assert check_gemini_cookies().status == OK


def test_oauth_client_sai_loai_bi_bat(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    # Credential loại Web application dùng khoá "web", không dùng được với desktop flow.
    (config / "youtube_client_secret.json").write_text(
        json.dumps({"web": {"client_id": "x"}}), encoding="utf-8"
    )
    check = check_youtube_client_secret(tmp_path)
    assert check.status == FAIL
    assert "Desktop app" in check.fix


def test_oauth_client_dung_loai_thi_dat(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "youtube_client_secret.json").write_text(
        json.dumps({"installed": {"client_id": "x"}}), encoding="utf-8"
    )
    assert check_youtube_client_secret(tmp_path).status == OK


def test_chua_cap_quyen_youtube_thi_chi_ro_lenh_can_chay(tmp_path: Path):
    check = check_youtube_token(tmp_path, deep=False)
    assert check.status == FAIL
    assert "upload.auth" in check.fix


def test_voice_yaml_tro_toi_file_khong_ton_tai_bi_bat(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "voice.yaml").write_text(
        'ref_audio_path: "config/voices/khong_co.mp3"\n', encoding="utf-8"
    )
    check = check_voice_config(tmp_path)
    assert check.status == FAIL
    assert "không tồn tại" in check.detail


def test_voice_yaml_dung_preset_thi_dat(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "voice.yaml").write_text('voice: "Thục Đoan"\n', encoding="utf-8")
    check = check_voice_config(tmp_path)
    assert check.status == OK
    assert "Thục Đoan" in check.detail


def test_khong_bat_nguon_nao_thi_bao_loi(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "trend.yaml").write_text(
        "region: VN\nfeeds: []\nuse_google_trends: false\n", encoding="utf-8"
    )
    check = check_trend_config(tmp_path)
    assert check.status == FAIL
    assert "feeds" in check.fix


def test_co_feed_thi_dat_va_dem_dung_so_nguon(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "trend.yaml").write_text(
        'feeds:\n  - url: "https://a/rss"\n  - url: "https://b/rss"\n', encoding="utf-8"
    )
    check = check_trend_config(tmp_path)
    assert check.status == OK
    assert "2 feed" in check.detail


def test_chi_bat_google_trends_van_chay_duoc(tmp_path: Path):
    # Mất hết feed báo vẫn còn Google Trends — yếu nhưng không phải lỗi chặn.
    config = tmp_path / "config"
    config.mkdir()
    (config / "trend.yaml").write_text("feeds: []\nuse_google_trends: true\n", encoding="utf-8")
    assert check_trend_config(tmp_path).status == OK


def test_trend_yaml_hong_cu_phap_bi_bat(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "trend.yaml").write_text("seed_queries: [chua dong ngoac\n", encoding="utf-8")
    assert check_trend_config(tmp_path).status == FAIL


def test_script_khong_co_quyen_chay_bi_bat(tmp_path: Path):
    script = tmp_path / "run_daily.sh"
    script.write_text("#!/bin/bash\n", encoding="utf-8")
    script.chmod(0o644)
    check = check_run_script(tmp_path)
    assert check.status == FAIL
    assert "chmod +x" in check.fix


def test_script_co_quyen_chay_thi_dat(tmp_path: Path):
    script = tmp_path / "run_daily.sh"
    script.write_text("#!/bin/bash\n", encoding="utf-8")
    script.chmod(0o755)
    assert check_run_script(tmp_path).status == OK


def test_bao_cao_hien_cach_sua_cho_muc_hong_va_giau_o_muc_dat():
    checks = [
        Check("Đạt", OK, "ổn", fix="đừng hiện dòng này"),
        Check("Hỏng", FAIL, "thiếu gì đó", fix="chạy lệnh abc"),
    ]
    report = format_report(checks)
    assert "chạy lệnh abc" in report
    assert "đừng hiện dòng này" not in report


def test_tong_ket_dem_dung_tung_loai():
    checks = [Check("a", OK), Check("b", WARN), Check("c", FAIL), Check("d", FAIL)]
    assert summarize(checks) == (1, 1, 2)
