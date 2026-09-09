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
