"""OAuth cho YouTube Data API v3.

Chạy một lần để cấp quyền (mở trình duyệt):

    uv run python -m upload.auth

Sau đó refresh token nằm ở config/youtube_token.json và mọi lượt chạy tự động
đều dùng lại được, không cần trình duyệt nữa.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET_PATH = ROOT / "config" / "youtube_client_secret.json"
TOKEN_PATH = ROOT / "config" / "youtube_token.json"

# youtube.upload đủ để đăng video; youtube.readonly để đọc lại thông tin kênh;
# youtube.force-ssl để SỬA video đã đăng (videos.update) -- cần khi video dài
# phải đăng lại và 5 short đang trỏ link cũ (16/09: bản 14/09 kẹt xử lý hai
# ngày, đăng lại ra ID mới, mô tả short phải đổi theo). Đổi danh sách này thì
# phải xoá config/youtube_token.json và cấp quyền lại.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
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

    refresh_failed = None
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _save(credentials, token_path)
            return credentials
        except RefreshError as exc:
            # OAuth project ở chế độ "Testing" bị Google thu hồi refresh token sau
            # 7 ngày (invalid_grant). Đây là lỗi thường gặp nhất: 31/08 cấp quyền,
            # 07/09 chết. Không được ném lỗi thô ở đây -- chạy tay thì đi tiếp
            # xuống bước xin quyền mới, chạy tự động thì nói rõ việc cần làm.
            refresh_failed = exc

    if not interactive:
        if refresh_failed is not None:
            raise YouTubeAuthError(
                f"Token YouTube tại {token_path} đã hết hạn hoặc bị thu hồi "
                f"({refresh_failed}). Project OAuth ở chế độ Testing chỉ giữ token "
                "7 ngày. Chạy `uv run python -m upload.auth` để cấp quyền lại."
            ) from refresh_failed
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
