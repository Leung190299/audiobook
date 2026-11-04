"""Đăng cả bộ 3 tập hẹn giờ + trích đoạn. Uploader giả, không gọi API."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from metadata.episodes import NEXT_EPISODE_PLACEHOLDER, PLAYLIST_PLACEHOLDER
from upload import episodes_cli
from upload.episodes_cli import LOCAL_TZ, default_first_air, fill_links
from upload.uploader import UploadResult


class FakeUploader:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, credentials, *, video_path, title, description, tags, category_id,
                 privacy_status, thumbnail_path, publish_at=None):
        if self.fail_on and Path(video_path).name == self.fail_on:
            raise RuntimeError("mạng rớt")
        self.calls.append({"video_path": Path(video_path), "title": title, "description": description,
                           "thumbnail_path": thumbnail_path, "publish_at": publish_at})
        vid = f"vid{len(self.calls)}"
        return UploadResult(video_id=vid, url=f"https://youtu.be/{vid}", title=title,
                            privacy_status=privacy_status, thumbnail_set=thumbnail_path is not None)


def _index(tmp_path: Path, with_shorts: bool = True) -> dict:
    eps = []
    for n in (1, 2, 3):
        video = tmp_path / f"truyen-tap-{n}.mp4"; video.write_bytes(b"mp4")
        thumb = tmp_path / f"t-ep-0{n}.png"; thumb.write_bytes(b"png")
        meta = tmp_path / f"t-ep-0{n}.json"
        desc = f"Hook\n\nTập {n}/3. Mô tả.\n\n{PLAYLIST_PLACEHOLDER}" + (f"\n{NEXT_EPISODE_PLACEHOLDER}" if n < 3 else "")
        meta.write_text(json.dumps({"title": f"Truyện | Tập {n}/3", "description": desc, "tags": ["a"],
                                    "pinned_comment": f"❓ Câu hỏi tập {n}"}), encoding="utf-8")
        eps.append({"number": n, "total": 3, "title": f"Truyện | Tập {n}/3", "video_path": str(video),
                    "metadata_path": str(meta), "thumbnail_path": str(thumb)})
    index = tmp_path / "t-episodes.json"
    index.write_text(json.dumps({"episodes": eps}), encoding="utf-8")
    prefix = None
    if with_shorts:
        prefix_name = "t-20260922T000000Z"
        for n in (1, 2):
            stem = f"{prefix_name}-part-{n:02d}"
            (tmp_path / f"{stem}.mp4").write_bytes(b"mp4")
            (tmp_path / f"{stem}.jpg").write_bytes(b"jpg")
            (tmp_path / f"{stem}.json").write_text(json.dumps({
                "title": f"Truyện — Trích đoạn {n}/2",
                "description": f"Truyện — Trích đoạn {n}/2.\nNghe trọn tập trên kênh — link ở phần mô tả kênh.",
                "tags": ["shorts"], "part_number": n, "total_parts": 2, "video_filename": f"{stem}.mp4"}),
                encoding="utf-8")
        prefix = tmp_path / prefix_name
    return {"index": index, "prefix": prefix}


def test_default_first_air():
    early = datetime(2026, 9, 23, 9, 0, tzinfo=LOCAL_TZ)
    assert default_first_air(early) == datetime(2026, 9, 23, 20, 0, tzinfo=LOCAL_TZ)
    late = datetime(2026, 9, 23, 19, 45, tzinfo=LOCAL_TZ)
    assert default_first_air(late) == datetime(2026, 9, 24, 20, 0, tzinfo=LOCAL_TZ)


def test_fill_links():
    d = f"x\n\n{PLAYLIST_PLACEHOLDER}\n{NEXT_EPISODE_PLACEHOLDER}\n\ny"
    assert fill_links(d, "https://youtu.be/n", None) == "x\n\n▶️ Tập tiếp theo: https://youtu.be/n\n\ny"
    assert "📚 Nghe trọn bộ theo thứ tự: https://p" in fill_links(d, None, "https://p")


def test_dang_3_tap_hen_gio_cach_nhau_1_ngay_roi_link_comment_va_short(tmp_path):
    ix = _index(tmp_path)
    up = FakeUploader()
    comments, updates = [], []

    def commenter(creds, vid, text):
        comments.append((vid, text)); return f"c-{vid}"

    def updater(creds, vid, desc):
        updates.append((vid, desc)); return True

    now = datetime(2026, 9, 23, 9, 0, tzinfo=LOCAL_TZ)
    state = episodes_cli.run(ix["index"], shorts_prefix=ix["prefix"], uploader=up, commenter=commenter,
                             description_updater=updater, credentials_loader=lambda: "creds", now=now,
                             playlist_url="https://p")

    names = [c["video_path"].name for c in up.calls]
    assert names[:3] == ["truyen-tap-1.mp4", "truyen-tap-2.mp4", "truyen-tap-3.mp4"]
    assert names[3:] == ["t-20260922T000000Z-part-01.mp4", "t-20260922T000000Z-part-02.mp4"]
    first = datetime(2026, 9, 23, 20, 0, tzinfo=LOCAL_TZ)
    assert [c["publish_at"] for c in up.calls[:3]] == [first, first + timedelta(days=1), first + timedelta(days=2)]
    # Mô tả lúc tải lên: playlist đã điền, chỗ tập sau còn giữ chỗ (chưa có id).
    assert "https://p" in up.calls[0]["description"]
    assert NEXT_EPISODE_PLACEHOLDER in up.calls[0]["description"]
    # Sau khi có id: tập 1 -> link tập 2, tập 2 -> link tập 3, tập 3 không cập nhật.
    assert [u[0] for u in updates] == ["vid1", "vid2"]
    assert "▶️ Tập tiếp theo: https://youtu.be/vid2" in updates[0][1]
    assert NEXT_EPISODE_PLACEHOLDER not in updates[0][1]
    assert [c[0] for c in comments] == ["vid1", "vid2", "vid3"]
    # Short trỏ về tập 1, hẹn giờ ngay lúc đăng: 5 phút sau khi tập 1 lên sóng
    # (trước 05/10 short đăng ngay rồi chờ lịch 20:05 tối chiếu bật công khai).
    tap1 = up.calls[0]["publish_at"]
    for call in up.calls[3:]:
        assert "https://youtu.be/vid1" in call["description"]
        assert call["publish_at"] == tap1 + timedelta(minutes=5)
    assert state["uploaded"]["1"]["next_link_set"] and state["uploaded"]["3"]["comment_posted"]
    assert (tmp_path / "t-episodes-upload-state.json").exists()


def test_loi_giua_chung_thi_chay_lai_khong_dang_trung(tmp_path):
    ix = _index(tmp_path, with_shorts=False)
    up = FakeUploader(fail_on="truyen-tap-2.mp4")
    with pytest.raises(episodes_cli.EpisodesUploadError, match="tập 2"):
        episodes_cli.run(ix["index"], uploader=up, commenter=lambda *a: "c", description_updater=lambda *a: True,
                         credentials_loader=lambda: "creds")
    assert [c["video_path"].name for c in up.calls] == ["truyen-tap-1.mp4"]

    up2 = FakeUploader()
    episodes_cli.run(ix["index"], uploader=up2, commenter=lambda *a: "c", description_updater=lambda *a: True,
                     credentials_loader=lambda: "creds")
    assert [c["video_path"].name for c in up2.calls] == ["truyen-tap-2.mp4", "truyen-tap-3.mp4"]


def test_no_schedule_khong_truyen_publish_at(tmp_path):
    ix = _index(tmp_path, with_shorts=False)
    up = FakeUploader()
    episodes_cli.run(ix["index"], uploader=up, schedule=False, commenter=lambda *a: None,
                     description_updater=lambda *a: False, credentials_loader=lambda: "creds")
    assert all(c["publish_at"] is None for c in up.calls)


# --- bản FULL theo chủ đề (24/09/2026) ----------------------------------------

from metadata.full import TOPIC_PLAYLIST_PLACEHOLDER
from upload.episodes_cli import playlist_ref


def _full_index(tmp_path: Path) -> Path:
    video = tmp_path / "bac-ca.mp4"; video.write_bytes(b"mp4")
    thumb = tmp_path / "x-thumbnail-a.png"; thumb.write_bytes(b"png")
    meta = tmp_path / "x-full-video.json"
    meta.write_text(json.dumps({
        "title": "[Truyện Audio] Bác Cả | Audio Truyện",
        "description": f"Hook\n\n❓ Q\n\n{TOPIC_PLAYLIST_PLACEHOLDER}\n\nCTA",
        "tags": ["a"], "pinned_comment": "❓ Q 1 = a, 2 = b",
    }, ensure_ascii=False), encoding="utf-8")
    index = tmp_path / "x-full.json"
    index.write_text(json.dumps({
        "topic": "ho_hang_viet", "format": "full", "story_title": "Bác Cả",
        "episodes": [{"number": 1, "total": 1, "title": "t", "video_path": str(video),
                      "metadata_path": str(meta), "thumbnail_path": str(thumb)}],
    }, ensure_ascii=False), encoding="utf-8")
    return index


def test_playlist_ref_nhan_link_va_id():
    assert playlist_ref("https://www.youtube.com/playlist?list=PLabc&si=1") == (
        "PLabc", "https://www.youtube.com/playlist?list=PLabc&si=1")
    assert playlist_ref("PLxyz") == ("PLxyz", "https://www.youtube.com/playlist?list=PLxyz")
    assert playlist_ref("") == (None, None)


def test_full_dang_1_video_hen_20h_vao_playlist_chu_de_va_ghi_jsonl(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("YOUTUBE_PLAYLIST_HO_HANG", "https://www.youtube.com/playlist?list=PLhohang")
    jsonl = tmp_path / "index.jsonl"
    up = FakeUploader()
    added = []
    now = datetime(2026, 9, 24, 9, 0, tzinfo=LOCAL_TZ)
    state = episodes_cli.run(
        _full_index(tmp_path), uploader=up, commenter=lambda *a: "c1",
        description_updater=lambda *a: True, credentials_loader=lambda: "cred",
        playlist_adder=lambda cred, pid, vid: added.append((pid, vid)) or True,
        index_jsonl=jsonl, now=now,
    )
    assert len(up.calls) == 1
    call = up.calls[0]
    assert call["publish_at"] == datetime(2026, 9, 24, 20, 0, tzinfo=LOCAL_TZ)
    assert "Nghe thêm truyện cùng chủ đề: https://www.youtube.com/playlist?list=PLhohang" in call["description"]
    assert TOPIC_PLAYLIST_PLACEHOLDER not in call["description"]
    assert added == [("PLhohang", "vid1")]
    assert state["uploaded"]["1"]["playlist_added"] is True
    row = json.loads(jsonl.read_text(encoding="utf-8").strip())
    assert row["topic"] == "ho_hang_viet" and row["format"] == "full"
    assert row["video_id"] == "vid1" and row["publishAt"].startswith("2026-09-24T20:00")
    out = capsys.readouterr().out
    assert "Full: [Truyện Audio] Bác Cả" in out and "Đã upload: https://youtu.be/vid1" in out

    # Chạy lại: không đăng trùng, không thêm playlist lần hai, không ghi jsonl lần hai.
    episodes_cli.run(
        _full_index(tmp_path), uploader=up, commenter=lambda *a: "c1",
        description_updater=lambda *a: True, credentials_loader=lambda: "cred",
        playlist_adder=lambda cred, pid, vid: added.append((pid, vid)) or True,
        index_jsonl=jsonl, now=now,
    )
    assert len(up.calls) == 1 and len(added) == 1
    assert len(jsonl.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_full_chua_dat_playlist_thi_xoa_dong_giu_cho(tmp_path):
    up = FakeUploader()
    episodes_cli.run(
        _full_index(tmp_path), uploader=up, commenter=lambda *a: "c",
        description_updater=lambda *a: True, credentials_loader=lambda: "cred",
        playlist_adder=lambda *a: pytest.fail("không được thêm playlist khi chưa cấu hình"),
        now=datetime(2026, 9, 24, 9, 0, tzinfo=LOCAL_TZ),
    )
    assert "(link playlist)" not in up.calls[0]["description"]


# --- kho truyện: publishAt theo publish_date, ghi story_id (spec kho §6) ---


def test_publish_date_cua_truyen_quyet_dinh_gio_len_song(tmp_path, monkeypatch):
    from datetime import date as _date

    from scripts.story_bank import Story

    story = Story(id=7, topic="ho_hang_viet", series="Truyện lẻ", title="T",
                  premise="p", twist="t", hook="h", comment_question="q",
                  thumb_keywords=(), timing="Quanh năm", priority="A",
                  publish_date=_date(2026, 10, 16))
    monkeypatch.setattr(episodes_cli.story_bank, "get_story", lambda sid: story)

    air = episodes_cli.resolve_first_air(
        story_id=7, now=datetime(2026, 9, 24, 10, 0, tzinfo=episodes_cli.LOCAL_TZ),
        publish_hour=20,
    )

    assert air.date() == _date(2026, 10, 16)
    assert (air.hour, air.minute) == (20, 0)
    assert air.utcoffset().total_seconds() == 7 * 3600


def test_khong_co_publish_date_thi_dung_ngay_trong_ke_tiep(tmp_path, monkeypatch):
    from scripts.story_bank import Story

    story = Story(id=8, topic="ho_hang_viet", series="Truyện lẻ", title="T",
                  premise="p", twist="t", hook="h", comment_question="q",
                  thumb_keywords=(), timing="Quanh năm", priority="A", publish_date=None)
    monkeypatch.setattr(episodes_cli.story_bank, "get_story", lambda sid: story)
    now = datetime(2026, 9, 24, 10, 0, tzinfo=episodes_cli.LOCAL_TZ)

    air = episodes_cli.resolve_first_air(story_id=8, now=now, publish_hour=20)

    assert air == episodes_cli.default_first_air(now, 20)


def test_khong_phai_che_do_kho_thi_giu_nguyen_cach_cu():
    now = datetime(2026, 9, 24, 10, 0, tzinfo=episodes_cli.LOCAL_TZ)

    assert episodes_cli.resolve_first_air(story_id=0, now=now, publish_hour=20) == (
        episodes_cli.default_first_air(now, 20)
    )


# --- playlist chủ đề đặt sai trong .env (24/09/2026) ---------------------------


def test_playlist_ref_gia_tri_khong_phai_link_hay_id_thi_bao_loi():
    """Dán nhầm TÊN playlist thay vì link: phải dừng, không tự bịa ra link.

    Trước đây "Họ Hàng Cực Phẩm | Truyện Audio" bị coi là id, đẻ ra
    youtube.com/playlist?list=Họ Hàng... dán thẳng vào mô tả video công khai.
    """
    from upload.episodes_cli import PlaylistConfigError

    with pytest.raises(PlaylistConfigError) as exc:
        playlist_ref("Họ Hàng Cực Phẩm | Truyện Audio")
    assert "Họ Hàng Cực Phẩm" in str(exc.value)

    with pytest.raises(PlaylistConfigError):
        playlist_ref("<link playlist 3>")

    # Link youtube nhưng không có list= thì cũng không phải playlist.
    with pytest.raises(PlaylistConfigError):
        playlist_ref("https://www.youtube.com/@kenh")


def test_playlist_sai_dinh_dang_thi_khong_upload_gi(tmp_path, monkeypatch):
    """Dừng TRƯỚC khi đăng, đừng để video lên kênh rồi mới biết link hỏng."""
    from upload.episodes_cli import PlaylistConfigError

    monkeypatch.setenv("YOUTUBE_PLAYLIST_HO_HANG", "Họ Hàng Cực Phẩm | Truyện Audio")
    up = FakeUploader()
    with pytest.raises(PlaylistConfigError):
        episodes_cli.run(
            _full_index(tmp_path), uploader=up, commenter=lambda *a: "c",
            description_updater=lambda *a: True, credentials_loader=lambda: "cred",
            now=datetime(2026, 9, 24, 9, 0, tzinfo=LOCAL_TZ),
        )
    assert up.calls == []


# --- ngày hẹn đã trôi qua (02/10/2026) ---------------------------------------


def test_ngay_hen_da_qua_thi_tim_tu_toi_mai(monkeypatch):
    """Biên tập xếp truyện #49 vào 02/10, nhưng lượt đăng chạy lúc 23:30 cùng
    ngày -- 20:00 đã trôi qua. Giữ nguyên là publishAt nằm ở quá khứ: YouTube
    hoặc từ chối, hoặc công khai ngay lập tức. Phải tìm tối trống bắt đầu từ
    TỐI MAI (tối nay đã lỡ), không đâm vào video đã xếp."""
    from datetime import date as _date

    from upload import episodes_cli as ec

    class _Story:
        publish_date = _date(2026, 10, 2)

    monkeypatch.setattr(ec.story_bank, "get_story", lambda sid: _Story())
    goi = {}

    def fake_free(start, **kw):
        goi["start"] = start
        return start  # giả như tối đầu tiên tìm tới là trống

    monkeypatch.setattr(ec.story_bank, "first_free_evening", fake_free)
    now = datetime(2026, 10, 2, 23, 30, tzinfo=LOCAL_TZ)

    assert ec.resolve_first_air(49, now, 20) == datetime(2026, 10, 3, 20, 0, tzinfo=LOCAL_TZ)
    assert goi["start"] == _date(2026, 10, 3)


def test_ngay_hen_con_o_tuong_lai_thi_giu_nguyen(monkeypatch):
    from datetime import date as _date

    from upload import episodes_cli as ec

    class _Story:
        publish_date = _date(2026, 10, 5)

    monkeypatch.setattr(ec.story_bank, "get_story", lambda sid: _Story())
    now = datetime(2026, 10, 2, 23, 30, tzinfo=LOCAL_TZ)

    assert ec.resolve_first_air(49, now, 20) == datetime(2026, 10, 5, 20, 0, tzinfo=LOCAL_TZ)


def test_ngay_hen_qua_nhieu_ngay_van_doi_toi_moc_tuong_lai(monkeypatch):
    """Dựng bù một truyện hẹn từ tuần trước: phải ra mốc sau 'bây giờ'."""
    from datetime import date as _date

    from upload import episodes_cli as ec

    class _Story:
        publish_date = _date(2026, 9, 20)

    monkeypatch.setattr(ec.story_bank, "get_story", lambda sid: _Story())
    now = datetime(2026, 10, 2, 23, 30, tzinfo=LOCAL_TZ)

    ra = ec.resolve_first_air(49, now, 20)
    assert ra > now


# --- truyện không hẹn: tối trống đầu tiên, không phải "tối mai" (05/10) --------


def test_truyen_khong_hen_xep_vao_toi_trong_dau_tien(monkeypatch):
    """Trước đây mặc định tối mai bất kể tối mai đã có video -- phải tự chỉ
    ngày bằng tay cho #6/#75 (28/09) và #9 (05/10)."""
    from datetime import date as _date

    from upload import episodes_cli as ec

    class _Story:
        publish_date = None

    monkeypatch.setattr(ec.story_bank, "get_story", lambda sid: _Story())
    goi = {}

    def fake_free(start, **kw):
        goi["start"] = start
        return _date(2026, 10, 27)

    monkeypatch.setattr(ec.story_bank, "first_free_evening", fake_free)
    now = datetime(2026, 10, 5, 11, 0, tzinfo=LOCAL_TZ)

    assert ec.resolve_first_air(46, now, 20) == datetime(2026, 10, 27, 20, 0, tzinfo=LOCAL_TZ)
    # Tìm từ tối sớm nhất còn kịp (tối nay 20h, còn hơn 30 phút).
    assert goi["start"] == _date(2026, 10, 5)


def test_ngay_hen_da_qua_cung_tim_toi_trong_khong_dam_vao_video_khac(monkeypatch):
    from datetime import date as _date

    from upload import episodes_cli as ec

    class _Story:
        publish_date = _date(2026, 10, 2)

    monkeypatch.setattr(ec.story_bank, "get_story", lambda sid: _Story())
    monkeypatch.setattr(ec.story_bank, "first_free_evening", lambda start, **kw: _date(2026, 10, 27))
    now = datetime(2026, 10, 5, 11, 0, tzinfo=LOCAL_TZ)

    assert ec.resolve_first_air(49, now, 20) == datetime(2026, 10, 27, 20, 0, tzinfo=LOCAL_TZ)


# --- short hẹn giờ cùng lúc đăng video dài (05/10/2026) ------------------------


def _bat_series(monkeypatch):
    goi = {}
    monkeypatch.setattr(episodes_cli.series_cli, "run", lambda prefix, **kw: goi.update(kw))
    return goi


def test_dang_video_dai_thi_hen_gio_short_sau_5_phut(tmp_path, monkeypatch):
    goi = _bat_series(monkeypatch)
    up = FakeUploader()
    now = datetime(2026, 10, 5, 9, 0, tzinfo=LOCAL_TZ)

    episodes_cli.run(
        _full_index(tmp_path), uploader=up, commenter=lambda *a: "c",
        description_updater=lambda *a: True, credentials_loader=lambda: "cred",
        playlist_adder=lambda *a: True, now=now, shorts_prefix=tmp_path / "x",
    )

    assert goi["publish_at"] == datetime(2026, 10, 5, 20, 5, tzinfo=LOCAL_TZ)
    assert goi["story_title"] == "Bác Cả"


def test_video_dai_da_dang_tu_truoc_thi_lay_gio_da_luu_khong_tinh_lai(tmp_path, monkeypatch):
    """#9 đăng với lịch chỉ định tay 26/10. Chạy lại để đăng short mà tính lại
    giờ thì ra ngày khác -- short phải bám đúng giờ video dài ĐÃ hẹn."""
    import json as _json

    goi = _bat_series(monkeypatch)
    index = _full_index(tmp_path)
    state = index.with_name(f"{index.stem}-upload-state.json")
    state.write_text(_json.dumps({"uploaded": {"1": {
        "video_id": "dai", "url": "https://youtu.be/dai",
        "publish_at": "2026-10-26T20:00:00+07:00",
        "playlist_added": True, "comment_posted": True, "next_link_set": True,
    }}}), encoding="utf-8")

    episodes_cli.run(
        index, uploader=FakeUploader(), commenter=lambda *a: "c",
        description_updater=lambda *a: True, credentials_loader=lambda: "cred",
        playlist_adder=lambda *a: True, now=datetime(2026, 10, 5, 15, 0, tzinfo=LOCAL_TZ),
        shorts_prefix=tmp_path / "x",
    )

    assert goi["publish_at"] == datetime(2026, 10, 26, 20, 5, tzinfo=LOCAL_TZ)


def test_video_dai_da_cong_khai_thi_short_cong_khai_ngay(tmp_path, monkeypatch):
    """Giờ chiếu đã qua: publishAt ở quá khứ thì YouTube từ chối -- đăng công
    khai luôn."""
    import json as _json

    goi = _bat_series(monkeypatch)
    index = _full_index(tmp_path)
    index.with_name(f"{index.stem}-upload-state.json").write_text(_json.dumps({"uploaded": {"1": {
        "video_id": "dai", "url": "https://youtu.be/dai",
        "publish_at": "2026-10-01T20:00:00+07:00",
        "playlist_added": True, "comment_posted": True, "next_link_set": True,
    }}}), encoding="utf-8")

    episodes_cli.run(
        index, uploader=FakeUploader(), commenter=lambda *a: "c",
        description_updater=lambda *a: True, credentials_loader=lambda: "cred",
        playlist_adder=lambda *a: True, now=datetime(2026, 10, 5, 15, 0, tzinfo=LOCAL_TZ),
        shorts_prefix=tmp_path / "x",
    )

    assert goi["publish_at"] is None
    assert goi["privacy_status"] == "public"


def test_dang_xong_thi_cap_nhat_caption_tiktok(monkeypatch):
    """Caption TikTok cần link video full: có link ngay khi video dài đăng xong."""
    from upload import episodes_cli as ec

    calls = []
    monkeypatch.setattr(ec, "run", lambda *a, **k: calls.append("run"))
    monkeypatch.setattr("shorts.tiktok.refresh_captions", lambda: calls.append("captions") or 0)
    monkeypatch.setattr("sys.argv", ["episodes_cli", "x.json"])
    ec.main()
    assert calls == ["run", "captions"]


def test_cap_nhat_caption_hong_khong_lam_hong_luot_dang(monkeypatch, capsys):
    from upload import episodes_cli as ec

    def boom():
        raise OSError("đĩa đầy")

    monkeypatch.setattr(ec, "run", lambda *a, **k: None)
    monkeypatch.setattr("shorts.tiktok.refresh_captions", boom)
    monkeypatch.setattr("sys.argv", ["episodes_cli", "x.json"])
    ec.main()
    assert "CẢNH BÁO" in capsys.readouterr().out


def _run(ix, up):
    return episodes_cli.run(ix["index"], shorts_prefix=ix["prefix"], uploader=up, commenter=lambda *a: "c",
                            description_updater=lambda *a: True, credentials_loader=lambda: "creds",
                            now=datetime(2026, 9, 23, 9, 0, tzinfo=LOCAL_TZ))


def test_dang_xong_thi_don_video_vao_thung_rac_va_dang_lai_khong_hong(tmp_path):
    """28/10: đăng xong thì dọn video (ổ đầy). Chỉ dọn .mp4 đã đăng thành công;
    giữ .json/ảnh bìa để lần chạy lại vẫn đọc được state và bỏ qua đúng."""
    ix = _index(tmp_path)
    up = FakeUploader(fail_on="truyen-tap-3.mp4")
    with pytest.raises(episodes_cli.EpisodesUploadError):
        _run(ix, up)
    trashed = []

    def trasher(paths):
        trashed.extend(paths)
        for p in paths:
            p.unlink()

    episodes_cli.trash_uploaded(ix["index"], ix["prefix"], trasher=trasher)
    assert sorted(p.name for p in trashed) == ["truyen-tap-1.mp4", "truyen-tap-2.mp4"], "tập 3 chưa đăng thì giữ"

    up.fail_on = None
    _run(ix, up)
    episodes_cli.trash_uploaded(ix["index"], ix["prefix"], trasher=trasher)
    assert {p.name for p in trashed} == {
        "truyen-tap-1.mp4", "truyen-tap-2.mp4", "truyen-tap-3.mp4",
        "t-20260922T000000Z-part-01.mp4", "t-20260922T000000Z-part-02.mp4",
    }
    assert (tmp_path / "t-20260922T000000Z-part-01.json").exists() and (tmp_path / "t-ep-01.png").exists()

    calls_before = len(up.calls)
    _run(ix, up)  # chạy lại sau khi đã dọn: không đăng trùng, không đòi file đã dọn
    assert len(up.calls) == calls_before


def test_main_don_video_tru_khi_keep_files(monkeypatch, capsys):
    from upload import episodes_cli as ec

    seen = []
    monkeypatch.setattr(ec, "run", lambda *a, **k: None)
    monkeypatch.setattr("shorts.tiktok.refresh_captions", lambda: 0)
    monkeypatch.setattr(ec, "trash_uploaded", lambda *a: seen.append(a) or [Path("a.mp4")])
    monkeypatch.setattr("sys.argv", ["episodes_cli", "x.json", "--shorts-prefix", "s/p"])
    ec.main()
    assert seen == [(Path("x.json"), Path("s/p"))]
    assert "Thùng rác" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["episodes_cli", "x.json", "--keep-files"])
    ec.main()
    assert len(seen) == 1
