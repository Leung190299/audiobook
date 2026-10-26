# tests/episodes/test_full.py
"""Định dạng FULL (24/09/2026): 1 video = cold open 20-30s + mọi chương + card 8s."""

import json

from episodes import cli as episodes_cli
from episodes.full import (
    FULL_OUTRO_SECONDS,
    full_outro_text,
    plan_full_cut,
    suggest_same_topic,
)
from tests.episodes.conftest import CHAPTER_COUNT, make_tts_metadata
from tests.episodes.test_cli import patched  # noqa: F401 -- fixture dùng lại


def test_cold_open_lay_tu_short_beat_dau_tien_trong_20_30_giay():
    tts = make_tts_metadata()
    cut = plan_full_cut(tts, CHAPTER_COUNT, ["Câu 3.2. Câu 3.3. Câu 3.4."])
    co = cut.cold_open
    assert co is not None and co.chapter_index == 3
    assert 20.0 <= co.duration_seconds <= 30.0
    first = next(s for s in tts["sentences"] if s["text"] == "Câu 3.2.")
    assert co.source_start_seconds == first["start_seconds"]
    assert cut.episode.first_chapter == 1 and cut.episode.last_chapter == CHAPTER_COUNT
    assert cut.episode.total == 1
    assert cut.outro_seconds == FULL_OUTRO_SECONDS == 8.0


def _long_tts(chapters=4, per_chapter=20, sec=3.0):
    sentences, chaps, t = [], [], 0.0
    for ci in range(1, chapters + 1):
        start = t
        for si in range(1, per_chapter + 1):
            sentences.append({"chapter_index": ci, "index": si, "text": f"Câu {ci}.{si}.",
                              "start_seconds": t, "end_seconds": t + sec})
            t += sec
        chaps.append({"index": ci, "heading": f"C{ci}", "start_seconds": start, "end_seconds": t})
    return {"chapters": chaps, "sentences": sentences}


def test_khong_do_duoc_beat_thi_dung_chuong_ap_chot():
    CHAPTER_COUNT = 4
    tts = _long_tts(CHAPTER_COUNT)
    cut = plan_full_cut(tts, CHAPTER_COUNT, ["đoạn không hề có trong truyện này đâu nhé bạn"])
    assert cut.cold_open is not None
    assert cut.cold_open.chapter_index == CHAPTER_COUNT - 1
    cut2 = plan_full_cut(tts, CHAPTER_COUNT, [])
    assert cut2.cold_open.chapter_index == CHAPTER_COUNT - 1


def test_goi_y_truyen_cung_chu_de(tmp_path):
    jsonl = tmp_path / "index.jsonl"
    jsonl.write_text(
        "\n".join(
            json.dumps(r, ensure_ascii=False)
            for r in [
                {"topic": "ho_hang_viet", "title": "Cũ Nhất"},
                {"topic": "bo_me_trong_sinh", "title": "Khác Chủ Đề"},
                {"topic": "ho_hang_viet", "title": "Mới Nhất"},
                {"topic": "ho_hang_viet", "title": "Chính Nó"},
            ]
        ),
        encoding="utf-8",
    )
    assert suggest_same_topic("ho_hang_viet", "Chính Nó", jsonl, tmp_path / "none.json") == "Mới Nhất"
    assert suggest_same_topic("", "x", jsonl, tmp_path / "none.json") == ""
    assert "Nghe tiếp: Mới Nhất" in full_outro_text("Câu hỏi?", "Mới Nhất")
    assert "20h mỗi tối" in full_outro_text()


def test_cli_full_render_mot_video_khong_badge_tap(patched, capsys, monkeypatch, tmp_path):
    sandbox, calls = patched
    monkeypatch.setattr(episodes_cli, "METADATA_INDEX_JSONL", tmp_path / "none.jsonl")
    monkeypatch.setattr(episodes_cli, "TOPICS_HISTORY", tmp_path / "none.json")
    data = json.loads(sandbox["script_path"].read_text(encoding="utf-8"))
    data.update(topic="ho_hang_viet", format="full", short_beats=["Câu 4.1. Câu 4.2."])
    sandbox["script_path"].write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    manifest_path = episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], sandbox["images_path"])
    out = capsys.readouterr().out
    assert "Đã render video full:" in out
    assert "Đã render 1 video vào" in out
    assert manifest_path.name.endswith("-full.json")
    assert len(calls) == 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["format"] == "full" and manifest["topic"] == "ho_hang_viet"
    (ep,) = manifest["episodes"]
    assert ep["video_path"].endswith("-full.mp4")
    assert ep["number"] == 1 and ep["total"] == 1
    assert ep["chapters"][0] == {"heading": "Mở đầu", "start_seconds": 0.0}
    assert len(ep["chapters"]) == CHAPTER_COUNT + 1
    props = json.loads(open(ep["props_path"], encoding="utf-8").read())
    assert props["episodeLabel"] == ""
    assert props["hookText"]
    assert props["outroSeconds"] == 8.0
    assert "20h mỗi tối" in props["outroText"]
    assert 20.0 <= props["coldOpenSeconds"] <= 30.0


def test_cli_kich_ban_cu_khong_co_format_van_chia_tap(patched, capsys):
    sandbox, calls = patched
    manifest_path = episodes_cli._run(sandbox["script_path"], sandbox["tts_path"], sandbox["images_path"])
    assert manifest_path.name.endswith("-episodes.json")
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["format"] == "episodes"


def test_truyen_co_chuong_mo_dau_thi_khong_ghep_trich_doan_audio():
    """Đã có chương 'Mở đầu' kể trước đoạn gay cấn: ghép thêm cold open nữa là
    người nghe nghe hai lần mở đầu liền nhau."""
    from scripts.models import PROLOGUE_HEADING

    tts = _long_tts(5)
    tts["chapters"][0]["heading"] = PROLOGUE_HEADING
    cut = plan_full_cut(tts, 5, ["Câu 3.2. Câu 3.3. Câu 3.4."])
    assert cut.cold_open is None
    assert cut.body_source_start_seconds == tts["chapters"][0]["start_seconds"]
