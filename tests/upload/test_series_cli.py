# tests/upload/test_series_cli.py
"""Kiểm thử upload/series_cli.py -- TUYỆT ĐỐI không gọi YouTube API thật.

Mọi test dùng uploader giả (fake_uploader) và credentials giả -- không import
googleapiclient.discovery.build, không network."""

import json
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

from upload import series_cli
from upload.auth import YouTubeAuthError, load_credentials
from upload.uploader import UploadResult

PREFIX_NAME = "vo_doi_tra_trung-20260822T182521Z"
FAKE_CREDENTIALS = "FAKE_CREDENTIALS"


def _write_part(directory: Path, prefix_name: str, number: int, with_thumbnail: bool = True) -> None:
    stem = f"{prefix_name}-part-{number:02d}"
    (directory / f"{stem}.mp4").write_bytes(b"fake mp4")
    (directory / f"{stem}.json").write_text(
        json.dumps(
            {
                "trope": "vo_doi_tra_trung",
                "title": f"Vô Đối Trả Thù — Phần {number}/5",
                "description": f"Mô tả phần {number}.",
                "tags": ["truyện audio", "shorts"],
                "part_number": number,
                "total_parts": 5,
                "video_filename": f"{stem}.mp4",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if with_thumbnail:
        (directory / f"{stem}.png").write_bytes(b"fake png")


def _make_series(tmp_path: Path, numbers: list[int], with_thumbnail: bool = True) -> Path:
    for n in numbers:
        _write_part(tmp_path, PREFIX_NAME, n, with_thumbnail=with_thumbnail)
    return tmp_path / PREFIX_NAME


class FakeUploader:
    """Đứng thay upload_video: không gọi API, chỉ ghi lại lời gọi và trả về
    UploadResult giả, hoặc ném lỗi đã cấu hình sẵn cho một số thứ tự gọi."""

    def __init__(self, fail_on_call: int | None = None, exc: Exception | None = None):
        self.calls = []
        self.fail_on_call = fail_on_call
        self.exc = exc

    def __call__(self, credentials, *, video_path, title, description, tags,
                 category_id, privacy_status, thumbnail_path):
        self.calls.append(
            {
                "credentials": credentials,
                "video_path": video_path,
                "title": title,
                "description": description,
                "tags": tags,
                "category_id": category_id,
                "privacy_status": privacy_status,
                "thumbnail_path": thumbnail_path,
            }
        )
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise self.exc
        video_id = f"vid{len(self.calls)}"
        return UploadResult(
            video_id=video_id,
            url=f"https://youtu.be/{video_id}",
            title=title,
            privacy_status=privacy_status,
            thumbnail_set=thumbnail_path is not None,
        )


def _fake_credentials() -> str:
    return FAKE_CREDENTIALS


def _quota_exceeded_error() -> HttpError:
    class _Resp:
        status = 403
        reason = "Forbidden"

    content = json.dumps(
        {
            "error": {
                "code": 403,
                "message": "The request cannot be completed because you have exceeded your quota.",
                "errors": [
                    {
                        "domain": "youtube.quota",
                        "reason": "quotaExceeded",
                        "message": "The request cannot be completed because you have exceeded your quota.",
                    }
                ],
            }
        }
    ).encode("utf-8")
    return HttpError(_Resp(), content)


def _read_state(prefix: Path) -> dict:
    state_path = prefix.parent / f"{prefix.name}-upload-state.json"
    return json.loads(state_path.read_text(encoding="utf-8"))


def test_dang_dung_thu_tu_tang_dan_du_filesystem_tra_ve_lon_xon(tmp_path):
    # Tạo phần 3 trước, rồi 1, rồi 2 -- filesystem/glob không đảm bảo thứ tự.
    _write_part(tmp_path, PREFIX_NAME, 3)
    _write_part(tmp_path, PREFIX_NAME, 1)
    _write_part(tmp_path, PREFIX_NAME, 2)
    prefix = tmp_path / PREFIX_NAME
    uploader = FakeUploader()

    series_cli.run(
        prefix,
        limit=10,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    uploaded_numbers = [call["title"] for call in uploader.calls]
    assert uploaded_numbers == [
        "Vô Đối Trả Thù — Phần 1/5",
        "Vô Đối Trả Thù — Phần 2/5",
        "Vô Đối Trả Thù — Phần 3/5",
    ]


def test_from_va_limit_phoi_hop_dung(tmp_path):
    prefix = _make_series(tmp_path, [1, 2, 3, 4, 5])
    uploader = FakeUploader()

    series_cli.run(
        prefix,
        from_n=3,
        limit=1,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    assert len(uploader.calls) == 1
    assert uploader.calls[0]["title"] == "Vô Đối Trả Thù — Phần 3/5"


def test_phan_da_co_trong_state_thi_bo_qua(tmp_path):
    prefix = _make_series(tmp_path, [1, 2, 3])
    state_path = tmp_path / f"{PREFIX_NAME}-upload-state.json"
    state_path.write_text(
        json.dumps(
            {
                "uploaded": {
                    "1": {
                        "video_id": "old1",
                        "url": "https://youtu.be/old1",
                        "uploaded_at": "2026-08-20T00:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    uploader = FakeUploader()

    series_cli.run(
        prefix,
        limit=10,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    titles = [call["title"] for call in uploader.calls]
    assert titles == [
        "Vô Đối Trả Thù — Phần 2/5",
        "Vô Đối Trả Thù — Phần 3/5",
    ]
    state = _read_state(prefix)
    assert set(state["uploaded"].keys()) == {"1", "2", "3"}
    # Phần 1 giữ nguyên bản ghi cũ, không bị đăng đè/ghi lại.
    assert state["uploaded"]["1"]["video_id"] == "old1"


def test_state_ghi_sau_moi_phan_khong_dong_den_cuoi_luot(tmp_path):
    # Đây là hành vi cốt lõi của task: mô phỏng chết giữa chừng ở phần thứ hai
    # -- phần đầu phải đã nằm trên đĩa, không chỉ trong bộ nhớ. Một cài đặt
    # "dồn state đến cuối lượt rồi ghi một lần" sẽ làm bài test này FAIL vì
    # không có state nào được ghi ra đĩa trước khi lỗi ném lên.
    prefix = _make_series(tmp_path, [1, 2, 3])
    uploader = FakeUploader(fail_on_call=2, exc=RuntimeError("mất kết nối giữa chừng"))

    with pytest.raises(series_cli.SeriesUploadError):
        series_cli.run(
            prefix,
            limit=10,
            uploader=uploader,
            credentials_loader=_fake_credentials,
        )

    # Đọc thẳng từ đĩa (không dùng lại object Python nào từ lần gọi run() ở
    # trên) để chắc chắn phần 1 đã được ghi bền thật sự.
    state = _read_state(prefix)
    assert set(state["uploaded"].keys()) == {"1"}
    assert state["uploaded"]["1"]["video_id"] == "vid1"


def test_dry_run_khong_goi_uploader_lan_nao(tmp_path, capsys):
    prefix = _make_series(tmp_path, [1, 2, 3])
    uploader = FakeUploader()

    series_cli.run(
        prefix,
        limit=10,
        dry_run=True,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    assert uploader.calls == []
    out = capsys.readouterr().out
    assert "1" in out and "2" in out and "3" in out
    assert not _state_path_exists(prefix)


def _state_path_exists(prefix: Path) -> bool:
    return (prefix.parent / f"{prefix.name}-upload-state.json").exists()


def test_het_han_muc_thi_dung_giu_state_va_nhac_chay_lai_hom_sau(tmp_path, capsys):
    prefix = _make_series(tmp_path, [1, 2, 3])
    uploader = FakeUploader(fail_on_call=2, exc=_quota_exceeded_error())

    series_cli.run(
        prefix,
        limit=10,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    state = _read_state(prefix)
    assert set(state["uploaded"].keys()) == {"1"}
    # Không thử lại phần 2 trong cùng lượt -- uploader chỉ được gọi đúng 2 lần
    # (phần 1 thành công, phần 2 gặp quotaExceeded rồi dừng ngay).
    assert len(uploader.calls) == 2

    out = capsys.readouterr().out
    assert "1" in out  # đã đăng được 1 phần trước khi hết hạn mức
    assert "ngày mai" in out or "hôm sau" in out


def test_thieu_file_bao_loi_truoc_khi_dang_bat_cu_gi(tmp_path):
    prefix = _make_series(tmp_path, [1, 2, 3])
    # Xoá .json của phần 2 -- thiếu metadata.
    (tmp_path / f"{PREFIX_NAME}-part-02.json").unlink()
    uploader = FakeUploader()

    with pytest.raises(series_cli.SeriesUploadError, match="part-02"):
        series_cli.run(
            prefix,
            limit=10,
            uploader=uploader,
            credentials_loader=_fake_credentials,
        )

    assert uploader.calls == []
    assert not _state_path_exists(prefix)


def test_thieu_file_mp4_bao_loi_truoc_khi_dang(tmp_path):
    prefix = _make_series(tmp_path, [1, 2])
    (tmp_path / f"{PREFIX_NAME}-part-01.mp4").unlink()
    uploader = FakeUploader()

    with pytest.raises(series_cli.SeriesUploadError, match="part-01"):
        series_cli.run(
            prefix,
            limit=10,
            uploader=uploader,
            credentials_loader=_fake_credentials,
        )

    assert uploader.calls == []


def test_thieu_token_thi_nhac_dung_lenh_upload_auth(tmp_path):
    prefix = _make_series(tmp_path, [1])
    missing_token_path = tmp_path / "khong_ton_tai" / "youtube_token.json"

    with pytest.raises(YouTubeAuthError, match="upload.auth"):
        series_cli.run(
            prefix,
            limit=10,
            uploader=FakeUploader(),
            credentials_loader=lambda: load_credentials(token_path=missing_token_path),
        )


def test_khong_co_thumbnail_van_dang_duoc_voi_thumbnail_path_none(tmp_path):
    prefix = _make_series(tmp_path, [1], with_thumbnail=False)
    uploader = FakeUploader()

    series_cli.run(
        prefix,
        limit=10,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    assert uploader.calls[0]["thumbnail_path"] is None


def test_in_thong_bao_so_phan_tieu_de_url_sau_moi_phan(tmp_path, capsys):
    prefix = _make_series(tmp_path, [1])
    uploader = FakeUploader()

    series_cli.run(
        prefix,
        limit=10,
        uploader=uploader,
        credentials_loader=_fake_credentials,
    )

    out = capsys.readouterr().out
    assert "1" in out
    assert "Vô Đối Trả Thù — Phần 1/5" in out
    assert "https://youtu.be/vid1" in out
