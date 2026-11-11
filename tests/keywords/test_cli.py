import asyncio
import json
from types import SimpleNamespace

import pytest

from keywords import cli, sources
from keywords.scoring import Cluster


def _args(tmp_path, **kw):
    base = dict(config=sources.DEFAULT_CONFIG_PATH, cache_dir=tmp_path / "kw", auto_bank=tmp_path / "story_bank.auto.json",
                dry_run=False, no_llm=False, refresh_competitors=False, llm=None, phrase=None)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def quiet_sources(monkeypatch):
    monkeypatch.setattr(sources, "collect_suggestions", lambda seeds, letters, fetch=None, pause=0.12: {
        "truyện audio mẹ chồng giữ sổ đỏ": 100, "truyện audio em chồng vay app đen": 80, "truyện audio ma": 90})
    monkeypatch.setattr(cli, "competitor_videos", lambda config, cache_dir, refresh: [])


def test_cum_khop_kho_thi_tra_truyen_trong_kho_khong_goi_mo_hinh(tmp_path, quiet_sources, monkeypatch, capsys):
    async def boom(*a, **k):
        raise AssertionError("không được gọi mô hình")
    monkeypatch.setattr(cli, "write_story", boom)

    code = cli.main_sync(_args(tmp_path))

    out = capsys.readouterr().out
    assert code == 0
    assert "Từ khóa: truyện audio mẹ chồng giữ sổ đỏ" in out and "Nguồn: kho" in out and "Truyện: 115" in out
    used = json.loads((tmp_path / "kw" / "used.json").read_text(encoding="utf-8"))
    assert used[0]["story_id"] == 115 and used[0]["source"] == "kho"


def test_khong_khop_kho_thi_tu_viet_va_luu_kho_phu(tmp_path, quiet_sources, monkeypatch, capsys):
    monkeypatch.setattr(sources, "collect_suggestions", lambda *a, **k: {"truyện audio con rể ở nhà vợ": 100})

    async def fake_write(cluster, bank, titles, llm, **kw):
        return {"topic": "ho_hang_viet", "title": "Con Rể Ở Nhà Vợ Ba Năm, Tôi Đưa Sổ Chi Tiêu Ra Mâm",
                "hook": "h", "premise": " ".join(["t"] * 180), "twist": " ".join(["t"] * 180),
                "comment_question": "q", "thumb_keywords": ["Sổ Chi Tiêu"]}
    monkeypatch.setattr(cli, "write_story", fake_write)

    code = cli.main_sync(_args(tmp_path))

    out = capsys.readouterr().out
    assert code == 0 and "Nguồn: mới" in out and "Truyện: 1000" in out
    rows = json.loads((tmp_path / "story_bank.auto.json").read_text(encoding="utf-8"))["stories"]
    assert rows[0]["id"] == 1000 and rows[0]["keyword"] == "truyện audio con rể ở nhà vợ"


def test_khong_cum_nao_dat_thi_thoat_3(tmp_path, quiet_sources, monkeypatch, capsys):
    monkeypatch.setattr(sources, "collect_suggestions", lambda *a, **k: {"truyện audio ma kinh dị": 100})

    assert cli.main_sync(_args(tmp_path)) == 3
    assert "Không cụm nào đạt ngưỡng" in capsys.readouterr().out


def test_dry_run_chi_in_bang_khong_viet_gi(tmp_path, quiet_sources, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("không được gọi mô hình")
    monkeypatch.setattr(cli, "write_story", boom)

    assert cli.main_sync(_args(tmp_path, dry_run=True)) == 0
    assert not (tmp_path / "kw" / "used.json").exists()


def test_mo_hinh_that_bai_thi_thu_cum_khac_roi_thoat_3(tmp_path, quiet_sources, monkeypatch, capsys):
    monkeypatch.setattr(sources, "collect_suggestions", lambda *a, **k: {
        "truyện audio con rể ở nhà vợ": 100, "truyện audio bố vợ đòi sính lễ": 90})
    tried = []

    async def fake_write(cluster, bank, titles, llm, **kw):
        tried.append(cluster.phrase)
        return None
    monkeypatch.setattr(cli, "write_story", fake_write)

    assert cli.main_sync(_args(tmp_path)) == 3
    assert len(tried) == 2


def test_phrase_ep_dung_cum_da_chon(tmp_path, quiet_sources, monkeypatch, capsys):
    monkeypatch.setattr(sources, "collect_suggestions", lambda *a, **k: {
        "truyện audio con rể ở nhà vợ": 100, "truyện audio bố vợ đòi sính lễ": 90})
    tried = []

    async def fake_write(cluster, bank, titles, llm, **kw):
        tried.append(cluster.phrase)
        return None
    monkeypatch.setattr(cli, "write_story", fake_write)

    assert cli.main_sync(_args(tmp_path, phrase="truyện audio bố vợ đòi sính lễ")) == 3
    assert tried == ["truyện audio bố vợ đòi sính lễ"]
    assert cli.main_sync(_args(tmp_path, phrase="truyện audio không có")) == 3
    assert "không có trong các cụm đạt ngưỡng" in capsys.readouterr().out


def _story_json(**over):
    base = {"topic": "ho_hang_viet", "title": "Bố Mẹ Nuôi Đòi Sang Tên Đất, Tôi Ném Giấy Nhận Con Nuôi",
            "hook": "Bà Phượng quát: 'Mày chỉ là con nuôi, đất này để cho em!'",
            "premise": "Bà Phượng nuôi Hoài. " + " ".join(["từ"] * 170), "twist": " ".join(["từ"] * 180),
            "comment_question": "Bạn chọn? 1 = Kiện, 2 = Nhịn", "thumb_keywords": ["Bố Mẹ Nuôi"]}
    base.update(over)
    return json.dumps(base, ensure_ascii=False)


class _FakeChat:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    async def send_message(self, text):
        self.prompts.append(text)
        return SimpleNamespace(text=self.replies.pop(0))


class _FakeClient:
    def __init__(self, replies):
        self.chat = _FakeChat(replies)

    def start_chat(self):
        return self.chat


def test_write_story_bien_tap_lan_hai_sau_ban_nhap_dat():
    from scripts.story_bank import load_bank
    edited = _story_json(twist="Lớp 1 bằng chứng, lớp 2 ghi âm. " + " ".join(["từ"] * 175))
    client = _FakeClient([_story_json(), edited])

    data = asyncio.run(cli.write_story(Cluster(phrase="bố mẹ nuôi"), load_bank(), [], None,
                                       recent_premises=["Ở phường Ô Chợ Dừa"], client=client))

    assert data["twist"].startswith("Lớp 1 bằng chứng")
    assert len(client.chat.prompts) == 2
    assert "BIÊN TẬP LẦN HAI" in client.chat.prompts[1] and "Ô Chợ Dừa" in client.chat.prompts[1]


def test_ban_bien_tap_hong_thi_giu_ban_nhap():
    from scripts.story_bank import load_bank
    bad = _story_json(hook=" ".join(["a"] * 30))  # hook quá dài, hỏi lại 3 lượt vẫn hỏng
    client = _FakeClient([_story_json(), bad, bad, bad])

    data = asyncio.run(cli.write_story(Cluster(phrase="bố mẹ nuôi"), load_bank(), [], None, client=client))

    assert data["hook"].startswith("Bà Phượng")
    assert len(client.chat.prompts) == 4


def test_ban_bien_tap_duoc_sua_tieu_de_neu_van_dat_luat():
    from scripts.story_bank import load_bank
    client = _FakeClient([_story_json(), _story_json(title="Bố Mẹ Nuôi Lật Mặt Đòi Đất, Tôi Ném Giấy", thumb_keywords=["Bố Mẹ Nuôi"])])

    data = asyncio.run(cli.write_story(Cluster(phrase="bố mẹ nuôi"), load_bank(), [], None, client=client))

    assert data["title"] == "Bố Mẹ Nuôi Lật Mặt Đòi Đất, Tôi Ném Giấy"
