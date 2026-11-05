"""OAuth cho YouTube Data API v3.

Chạy một lần để cấp quyền (mở trình duyệt):

    uv run python -m upload.auth

Sau đó refresh token nằm ở config/youtube_token.json và mọi lượt chạy tự động
đều dùng lại được, không cần trình duyệt nữa.
"""

from __future__ import annotations

import json
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

# Đọc tỷ lệ giữ chân (metadata/retention.py). Tách khỏi SCOPES có chủ đích:
# lượt làm mới token gửi kèm danh sách quyền, xin một quyền chưa từng được đồng
# ý là Google trả invalid_scope -- thêm thẳng vào SCOPES thì token cũ chết ngay
# và lượt đăng 09:00 hỏng theo. Nên chỉ lần ĐỒNG Ý mới xin thêm quyền này;
# đăng video vẫn làm mới bằng SCOPES như cũ, đọc số liệu thì hỏi has_scope trước.
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
CONSENT_SCOPES = SCOPES + [ANALYTICS_SCOPE]


class YouTubeAuthError(Exception):
    pass


def load_credentials(
    token_path: Path = TOKEN_PATH,
    client_secret_path: Path = CLIENT_SECRET_PATH,
    interactive: bool = False,
    force: bool = False,
    scopes: list[str] = SCOPES,
) -> Credentials:
    credentials: Credentials | None = None

    # force: bỏ qua token đang có, xin quyền lại từ đầu. Project ở chế độ
    # Testing: refresh token chết 7 ngày sau lần ĐỒNG Ý, làm mới access token
    # không kéo dài hạn đó -- chỉ đồng ý lại mới đặt lại đồng hồ.
    if token_path.exists() and not (force and interactive):
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)

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

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), CONSENT_SCOPES)
    credentials = flow.run_local_server(port=0, prompt="consent")
    _save(credentials, token_path)
    return credentials


def has_scope(scope: str, token_path: Path = TOKEN_PATH) -> bool:
    """Token đã lưu có quyền `scope` chưa (đọc trường "scopes" trong file token)."""
    try:
        granted = json.loads(token_path.read_text(encoding="utf-8")).get("scopes") or []
    except (OSError, json.JSONDecodeError):
        return False
    return scope in granted


def _save(credentials: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(credentials.to_json())
    # Lượt đăng làm mới token chỉ với SCOPES, to_json() ghi lại đúng 3 quyền đó;
    # giữ các quyền đã ghi trước (yt-analytics) để has_scope không quên chúng --
    # refresh token vẫn mang đủ mọi quyền đã đồng ý.
    if token_path.exists():
        try:
            old = json.loads(token_path.read_text(encoding="utf-8")).get("scopes") or []
        except json.JSONDecodeError:
            old = []
        merged = list(dict.fromkeys((data.get("scopes") or []) + old))
        if merged:
            data["scopes"] = merged
    token_path.write_text(json.dumps(data), encoding="utf-8")
    token_path.chmod(0o600)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Cấp quyền YouTube cho pipeline đăng video.")
    p.add_argument("--force", action="store_true", help="Xin quyền lại dù token còn sống (đặt lại hạn 7 ngày)")
    credentials = load_credentials(interactive=True, force=p.parse_args().force)
    if not credentials.refresh_token:
        raise SystemExit(
            "Cấp quyền xong nhưng Google không trả refresh_token — lượt chạy tự động "
            "sẽ hỏng sau 1 giờ. Xoá config/youtube_token.json rồi chạy lại "
            "(flow này đã đặt prompt=consent để luôn xin refresh_token)."
        )
    print(f"Đã lưu token YouTube: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
