"""OAuth cho YouTube Data API v3.

Chạy một lần để cấp quyền (mở trình duyệt):

    uv run python -m upload.auth

Sau đó refresh token nằm ở config/youtube_token.json và mọi lượt chạy tự động
đều dùng lại được, không cần trình duyệt nữa.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET_PATH = ROOT / "config" / "youtube_client_secret.json"
TOKEN_PATH = ROOT / "config" / "youtube_token.json"

# youtube.upload đủ để đăng video; youtube.readonly cần cho trend/sources.py
# (search.list) và để đọc lại thông tin kênh.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YouTubeAuthError(Exception):
    pass


def load_credentials(
    token_path: Path = TOKEN_PATH,
    client_secret_path: Path = CLIENT_SECRET_PATH,
    interactive: bool = False,
) -> Credentials:
    credentials: Credentials | None = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _save(credentials, token_path)
        return credentials

    if not interactive:
        raise YouTubeAuthError(
            f"Chưa có token YouTube hợp lệ tại {token_path}. "
            "Chạy `uv run python -m upload.auth` một lần trên máy có trình duyệt "
            "để cấp quyền trước khi đặt lịch tự động."
        )

    if not client_secret_path.exists():
        raise YouTubeAuthError(
            f"Không tìm thấy {client_secret_path}. Tạo OAuth client "
            '(loại "Desktop app") trong Google Cloud Console, bật YouTube Data API v3, '
            "rồi tải file JSON về đúng đường dẫn này."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    credentials = flow.run_local_server(port=0, prompt="consent")
    _save(credentials, token_path)
    return credentials


def _save(credentials: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)


def main() -> None:
    credentials = load_credentials(interactive=True)
    if not credentials.refresh_token:
        raise SystemExit(
            "Cấp quyền xong nhưng Google không trả refresh_token — lượt chạy tự động "
            "sẽ hỏng sau 1 giờ. Xoá config/youtube_token.json rồi chạy lại "
            "(flow này đã đặt prompt=consent để luôn xin refresh_token)."
        )
    print(f"Đã lưu token YouTube: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
