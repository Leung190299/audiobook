# tests/upload/test_auth.py
from pathlib import Path

import pytest
from google.auth.exceptions import RefreshError

from upload import auth


class _ExpiredCreds:
    valid = False
    expired = True
    refresh_token = "cu"

    def refresh(self, _request):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")


class _FreshCreds:
    valid = True
    expired = False
    refresh_token = "moi"

    def to_json(self):
        return '{"refresh_token": "moi"}'


@pytest.fixture
def expired_token(tmp_path, monkeypatch):
    token = tmp_path / "youtube_token.json"
    token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        auth.Credentials, "from_authorized_user_file", lambda *_a, **_k: _ExpiredCreds()
    )
    return token


def test_token_bi_thu_hoi_khong_tuong_tac_thi_bao_chay_upload_auth(expired_token):
    # Chạy tự động (run_daily) gặp refresh token chết: không được ném RefreshError
    # thô, phải nói rõ việc cần làm.
    with pytest.raises(auth.YouTubeAuthError, match="upload.auth"):
        auth.load_credentials(token_path=expired_token, interactive=False)


def test_token_bi_thu_hoi_tuong_tac_thi_mo_lai_luong_cap_quyen(expired_token, tmp_path, monkeypatch):
    # Đúng lỗi 09/09: `upload.auth` chết ở refresh() nên không bao giờ mở trình
    # duyệt. Có token hỏng phải xin quyền mới như chưa từng có token.
    calls = []

    class _Flow:
        def run_local_server(self, **kwargs):
            calls.append(kwargs)
            return _FreshCreds()

    monkeypatch.setattr(
        auth.InstalledAppFlow, "from_client_secrets_file", lambda *_a, **_k: _Flow()
    )
    secret = tmp_path / "secret.json"
    secret.write_text("{}", encoding="utf-8")

    creds = auth.load_credentials(
        token_path=expired_token, client_secret_path=secret, interactive=True
    )

    assert creds.refresh_token == "moi"
    assert calls == [{"port": 0, "prompt": "consent"}]
    assert expired_token.read_text(encoding="utf-8") == '{"refresh_token": "moi"}'


def test_scopes_co_quyen_sua_video_da_dang():
    # Thiếu force-ssl thì videos.update trả 403 "insufficient authentication
    # scopes" -- gặp thật 16/09 khi phải đổi link trong mô tả 5 short.
    assert "https://www.googleapis.com/auth/youtube.force-ssl" in auth.SCOPES


def test_force_xin_quyen_lai_du_token_con_song(tmp_path, monkeypatch):
    """Project Testing: refresh token chết 7 ngày sau lần ĐỒNG Ý, làm mới access
    token không kéo dài hạn đó. --force xin quyền lại để đặt lại đồng hồ 7 ngày."""
    calls = []

    class _Flow:
        def run_local_server(self, **kwargs):
            calls.append(kwargs)
            return _FreshCreds()

    class _Valid:
        valid = True

    monkeypatch.setattr(auth.Credentials, "from_authorized_user_file", lambda *_a, **_k: _Valid())
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_secrets_file", lambda *_a, **_k: _Flow())
    token = tmp_path / "token.json"; token.write_text("{}", encoding="utf-8")
    secret = tmp_path / "secret.json"; secret.write_text("{}", encoding="utf-8")

    creds = auth.load_credentials(token_path=token, client_secret_path=secret, interactive=True, force=True)

    assert creds.refresh_token == "moi" and calls == [{"port": 0, "prompt": "consent"}]


def test_cap_quyen_xin_them_analytics_nhung_lam_moi_khong_xin():
    # Làm mới token kèm quyền chưa từng đồng ý -> invalid_scope, lượt đăng 09:00
    # hỏng. Nên yt-analytics chỉ được xin ở bước đồng ý.
    assert auth.ANALYTICS_SCOPE in auth.CONSENT_SCOPES
    assert auth.ANALYTICS_SCOPE not in auth.SCOPES


def test_luu_token_sau_khi_lam_moi_khong_lam_mat_quyen_analytics(tmp_path):
    import json

    token = tmp_path / "token.json"
    token.write_text(json.dumps({"scopes": auth.CONSENT_SCOPES}), encoding="utf-8")

    class _Refreshed:
        def to_json(self):
            return json.dumps({"refresh_token": "r", "scopes": auth.SCOPES})

    auth._save(_Refreshed(), token)

    assert auth.has_scope(auth.ANALYTICS_SCOPE, token)
    assert json.loads(token.read_text())["refresh_token"] == "r"


def test_has_scope_token_cu_hoac_thieu_file(tmp_path):
    import json

    token = tmp_path / "token.json"
    assert not auth.has_scope(auth.ANALYTICS_SCOPE, token)
    token.write_text(json.dumps({"scopes": auth.SCOPES}), encoding="utf-8")
    assert not auth.has_scope(auth.ANALYTICS_SCOPE, token)
