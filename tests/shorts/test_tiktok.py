import json
from pathlib import Path

import pytest

from shorts import tiktok


def _sentences(n=200, seconds=4.0, per_chapter=40):
    """n câu, mỗi câu `seconds` giây, liền nhau; 40 câu một chương."""
    return [
        {
            "chapter_index": i // per_chapter + 1,
            "index": i % per_chapter + 1,
            "text": f"Câu số {i}.",
            "start_seconds": i * seconds,
            "end_seconds": (i + 1) * seconds,
        }
        for i in range(n)
    ]


def _dur(s, i, j):
    return s[j]["end_seconds"] - s[i]["start_seconds"]


def test_danh_so_cau_cho_claude_chon():
    text = tiktok.numbered_sentences(_sentences(3))
    assert text.splitlines()[0] == "[0] (chương 1) Câu số 0."
    assert "[2]" in text


def test_doc_ket_qua_chon_doan():
    raw = 'Đây:\n```json\n{"start": 10, "end": 70, "hook": "Cô ta dọn đi", "caption": "Lòng tốt có giới hạn"}\n```'
    pick = tiktok.parse_pick(raw, 200)
    assert (pick.start, pick.end, pick.hook) == (10, 70, "Cô ta dọn đi")


@pytest.mark.parametrize("raw", ['{"start": 50, "end": 10}', '{"start": -1, "end": 10}', '{"start": 5, "end": 999}', "không phải json"])
def test_ket_qua_vo_ly_thi_bao_loi(raw):
    with pytest.raises(tiktok.TikTokPickError):
        tiktok.parse_pick(raw, 200)


def test_doan_qua_ngan_thi_keo_dai_toi_3_phut():
    s = _sentences()
    i, j = tiktok.fit_span(s, 100, 110)  # 44 giây
    assert 180 <= _dur(s, i, j) <= 300
    assert i <= 100 and j >= 110


def test_doan_qua_dai_thi_cat_dau_giu_cau_chot():
    s = _sentences()
    i, j = tiktok.fit_span(s, 0, 150)  # 604 giây
    assert j == 150, "giữ nguyên câu chốt ở cuối"
    assert 180 <= _dur(s, i, j) <= 300


def test_doan_vua_thi_giu_nguyen():
    s = _sentences()
    assert tiktok.fit_span(s, 20, 80) == (20, 80)  # 244 giây


def test_doan_du_phong_nam_cuoi_chuong_co_cu_lat():
    s = _sentences()  # 5 chương; cú lật ở chương áp chót = chương 4
    i, j = tiktok.fallback_span(s)
    assert s[j]["chapter_index"] == 4 and s[j + 1]["chapter_index"] == 5
    assert 180 <= _dur(s, i, j) <= 300


def test_phu_de_quy_ve_goc_0():
    s = _sentences()
    part = tiktok.make_part(s, 10, 60, "Mở đầu")
    assert part.source_start_seconds == 40.0
    assert part.captions[0].start_seconds == 0.0
    assert part.hook_line == "Mở đầu"
    assert len(part.captions) == 51


def test_caption_tiktok_chua_dang_youtube_thi_chua_co_link():
    text = tiktok.caption_text("Tiêu Đề", "Lòng tốt cần ranh giới", ("#hohangcucpham", "#truyenhai"))
    assert "Tiêu Đề" in text and "#truyenaudio" in text and "#hohangcucpham" in text
    assert "youtu" not in text.lower()
    # Chữ TRÊN VIDEO vẫn không nhắc YouTube (TikTok hạn chế hiển thị); link chỉ ở caption.
    assert "youtube" not in tiktok.TIKTOK_CTA.lower()


def test_caption_tiktok_co_link_full_gio_len_song_va_tu_khoa():
    from datetime import datetime

    text = tiktok.caption_text(
        "Tiêu Đề", "Câu mồi", ("#truyenhai",),
        url="https://youtu.be/ABC", air=datetime.fromisoformat("2026-10-23T20:00:00+07:00"),
        keywords=["truyện audio", "drama phụ huynh", "truyện audio"], yt_hashtags=["#truyenhocduong"],
        now=datetime.fromisoformat("2026-10-21T09:00:00+07:00"),
    )
    assert "https://youtu.be/ABC" in text
    assert "20:00 23/10" in text
    assert "truyện audio | drama phụ huynh" in text
    assert "#truyenhocduong" in text
    tags = text.strip().splitlines()[-1].split()
    assert len(tags) == len(set(tags)) <= 10


def test_lam_moi_caption_theo_link_youtube_da_dang(tmp_path):
    out = tmp_path / "tiktok"; out.mkdir()
    video = out / "x-1.mp4"; video.write_bytes(b"")
    video.with_suffix(".txt").write_text("Truyện A\nCâu mồi của Claude\n\n#truyenaudio #fyp\n", encoding="utf-8")
    (out / "done.json").write_text(json.dumps({"Truyện A": str(video)}), encoding="utf-8")
    meta = tmp_path / "a-full.json"
    meta.write_text(json.dumps({"topic": "ho_hang_viet", "tags": ["drama họ hàng"], "hashtags": ["#hohangcucpham"]}), encoding="utf-8")
    index = tmp_path / "index.jsonl"
    index.write_text(json.dumps({"story_title": "Truyện A", "url": "https://youtu.be/A1", "publishAt": "2026-10-23T20:00:00+07:00", "index": str(meta)}) + "\n", encoding="utf-8")

    n = tiktok.refresh_captions(done_index=out / "done.json", index_jsonl=index)

    moved = Path(json.loads((out / "done.json").read_text(encoding="utf-8"))["Truyện A"])
    text = moved.with_suffix(".txt").read_text(encoding="utf-8")
    assert n == 1
    assert "Câu mồi của Claude" in text and "https://youtu.be/A1" in text
    assert "drama họ hàng" in text and "#hohangcucpham" in text
    doc = (out / "SEO_TIKTOK.md").read_text(encoding="utf-8")
    assert "Truyện A" in doc and "https://youtu.be/A1" in doc and "2026-10-23_truyen-a.mp4" in doc


def test_tim_metadata_tts_theo_tieu_de(tmp_path):
    (tmp_path / "a-1.json").write_text(json.dumps({"trope": "a", "title": "Khác"}), encoding="utf-8")
    (tmp_path / "a-2.json").write_text(json.dumps({"trope": "a", "title": "Đúng"}), encoding="utf-8")
    assert tiktok.find_tts_metadata("a", "Đúng", tmp_path).name == "a-2.json"
    assert tiktok.find_tts_metadata("a", "Không có", tmp_path) is None


class _Chat:
    def __init__(self, reply=None, exc=None):
        self.reply, self.exc, self.prompts = reply, exc, []

    async def send_message(self, text):
        self.prompts.append(text)
        if self.exc:
            raise self.exc
        from types import SimpleNamespace

        return SimpleNamespace(text=self.reply)


async def test_claude_chon_doan_roi_chinh_thoi_luong():
    s = _sentences()
    chat = _Chat('{"start": 100, "end": 110, "hook": "Lật tẩy", "caption": "Xem tới cuối"}')
    pick = await tiktok.pick_climax("T", s, chat=chat)
    assert 180 <= _dur(s, pick.start, pick.end) <= 300
    assert pick.hook == "Lật tẩy" and pick.caption == "Xem tới cuối"
    assert "[199]" in chat.prompts[0]


async def test_claude_loi_thi_dung_doan_du_phong(capsys):
    s = _sentences()
    pick = await tiktok.pick_climax("Tiêu đề", s, chat=_Chat(exc=RuntimeError("mất mạng")))
    assert (pick.start, pick.end) == tiktok.fallback_span(s)
    assert pick.hook == "Tiêu đề"
    assert "CẢNH BÁO" in capsys.readouterr().out


def test_all_bo_qua_truyen_da_co_clip_va_lay_ban_dung_moi_nhat(tmp_path):
    ep, audio = tmp_path / "ep", tmp_path / "audio"
    ep.mkdir(); audio.mkdir()
    script = tmp_path / "s.json"; script.write_text("{}", encoding="utf-8")
    for stem, title in [("a-1", "Một"), ("a-2", "Hai"), ("a-3", "Một")]:
        (ep / f"{stem}-full.json").write_text(json.dumps({"trope": "a", "title": title, "script_path": str(script)}), encoding="utf-8")
        (audio / f"{stem}.json").write_text(json.dumps({"trope": "a", "title": title}), encoding="utf-8")
    done = tmp_path / "done.json"
    done.write_text(json.dumps({"Hai": "x.mp4"}), encoding="utf-8")

    todo = tiktok.pending_stories(ep, done, audio)

    assert [(t, tts.name) for t, tts, _ in todo] == [("Một", "a-3.json")]


def test_video_da_chieu_thi_khong_ghi_gio_len_song():
    from datetime import datetime

    text = tiktok.caption_text(
        "T", "", url="https://youtu.be/A", air=datetime.fromisoformat("2026-09-28T20:00:00+07:00"),
        now=datetime.fromisoformat("2026-10-21T09:00:00+07:00"),
    )
    assert "https://youtu.be/A" in text and "lên sóng" not in text


def _clip(tmp_path, title, index_rows):
    out = tmp_path / "tiktok"; out.mkdir(exist_ok=True)
    video = out / "nghe_la-20261020T001500Z.mp4"; video.write_bytes(b"v")
    video.with_suffix(".txt").write_text(f"{title}\nCâu mồi\n\n#fyp\n", encoding="utf-8")
    (out / "done.json").write_text(json.dumps({title: str(video)}), encoding="utf-8")
    index = tmp_path / "index.jsonl"
    index.write_text("".join(json.dumps(r) + "\n" for r in index_rows), encoding="utf-8")
    return out, index


def test_doi_ten_clip_theo_ngay_len_song_va_ten_truyen(tmp_path):
    title = "Cho Đồng Nghiệp Ở Nhờ Phòng Trọ"
    out, index = _clip(tmp_path, title, [{"story_title": title, "url": "https://youtu.be/A", "publishAt": "2026-10-30T20:00:00+07:00"}])

    tiktok.refresh_captions(done_index=out / "done.json", index_jsonl=index)
    tiktok.refresh_captions(done_index=out / "done.json", index_jsonl=index)  # chạy lại không đổi gì

    names = sorted(p.name for p in out.iterdir() if p.suffix in (".mp4", ".txt"))
    assert names == ["2026-10-30_cho-dong-nghiep-o-nho-phong-tro.mp4", "2026-10-30_cho-dong-nghiep-o-nho-phong-tro.txt"]
    done = json.loads((out / "done.json").read_text(encoding="utf-8"))
    assert done[title].endswith("2026-10-30_cho-dong-nghiep-o-nho-phong-tro.mp4")
    assert "2026-10-30_cho-dong-nghiep-o-nho-phong-tro.mp4" in (out / "SEO_TIKTOK.md").read_text(encoding="utf-8")


def test_chua_dang_youtube_thi_ten_bat_dau_bang_chua_dang(tmp_path):
    out, index = _clip(tmp_path, "Truyện B", [])
    tiktok.refresh_captions(done_index=out / "done.json", index_jsonl=index)
    assert (out / "chua-dang-youtube_truyen-b.mp4").exists()
    assert (out / "chua-dang-youtube_truyen-b.txt").exists()


def test_bo_chuong_mo_dau_khi_do_doan_trich():
    """Short/TikTok dò đoạn trích trong audio: phải bỏ chương 'Mở đầu' (kể trước
    cao trào), kẻo dò trúng bản kể trước thay vì cao trào thật."""
    from scripts.models import PROLOGUE_HEADING, without_prologue

    meta = {"chapters": [{"index": 1, "heading": PROLOGUE_HEADING}, {"index": 2, "heading": "C2"}],
            "sentences": _sentences(80)}
    out = without_prologue(meta)
    assert [c["index"] for c in out["chapters"]] == [2]
    assert all(s["chapter_index"] == 2 for s in out["sentences"]) and len(out["sentences"]) == 40
    assert len(meta["sentences"]) == 80, "không sửa metadata gốc"
    plain = {"chapters": [{"index": 1, "heading": "C1"}], "sentences": _sentences(40)}
    assert without_prologue(plain) == plain
