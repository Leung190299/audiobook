import json

import numpy as np
import pytest
import soundfile as sf

from episodes.audio_build import EpisodeAudioError, build_episode_wav
from episodes.cutter import EpisodeCut, plan_cuts
from episodes.plan import plan_episodes
from episodes.props_builder import (
    COLD_OPEN_HEADING,
    EpisodePropsBuildError,
    build_episode_props,
    chapter_lines,
    outro_text,
)
from scripts.models import Script
from tests.episodes.conftest import SAMPLE_RATE


def test_build_episode_wav_do_dai_bang_tong_ba_khuc(sandbox):
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[0]
    dest = sandbox["repo_root"] / "output" / "episodes" / "ep-01.wav"
    duration = build_episode_wav(sandbox["wav_path"], cut, dest)
    assert duration == pytest.approx(cut.total_seconds, abs=1e-3)
    data, sr = sf.read(dest, dtype="float32")
    assert sr == SAMPLE_RATE
    # Khoảng nghỉ sau cold open và outro phải im lặng, thân tập phải có tiếng.
    gap_start = round(cut.cold_open.duration_seconds * sr)
    gap = data[gap_start + 10 : gap_start + round(cut.gap_seconds * sr) - 10]
    assert np.all(gap == 0)
    body_start = round(cut.body_offset_seconds * sr)
    assert np.abs(data[body_start : body_start + sr]).max() > 0.1
    outro = data[round(cut.outro_start_seconds * sr) + 10 :]
    assert np.all(outro == 0)


def test_build_episode_wav_khong_co_cold_open(sandbox):
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[0]
    cut = EpisodeCut(
        episode=cut.episode,
        body_source_start_seconds=cut.body_source_start_seconds,
        body_source_end_seconds=cut.body_source_end_seconds,
        cold_open=None,
    )
    dest = sandbox["repo_root"] / "ep.wav"
    duration = build_episode_wav(sandbox["wav_path"], cut, dest)
    assert duration == pytest.approx(cut.body_duration_seconds + cut.outro_seconds, abs=1e-3)


def test_build_episode_wav_ngoai_file_thi_loi(sandbox):
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[0]
    bad = EpisodeCut(
        episode=cut.episode,
        body_source_start_seconds=0.0,
        body_source_end_seconds=10_000.0,
        cold_open=None,
    )
    with pytest.raises(EpisodeAudioError):
        build_episode_wav(sandbox["wav_path"], bad, sandbox["repo_root"] / "x.wav")


def _props(sandbox, ep_number: int) -> tuple[dict, EpisodeCut]:
    script = Script.from_dict(json.loads(sandbox["script_path"].read_text(encoding="utf-8")))
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[ep_number - 1]
    audio_path = sandbox["repo_root"] / "output" / "episodes" / f"ep-0{ep_number}.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"")
    props = build_episode_props(
        script,
        sandbox["tts_metadata"],
        sandbox["images_metadata"],
        cut,
        audio_path=audio_path,
        images_dir=sandbox["images_dir"],
        repo_root=sandbox["repo_root"],
    )
    return props, cut


def test_props_cold_open_la_chuong_0_va_than_tap_doi_theo_offset(sandbox):
    props, cut = _props(sandbox, 2)
    chapters = props["chapters"]
    assert chapters[0]["index"] == 0
    assert chapters[0]["heading"] == COLD_OPEN_HEADING
    assert chapters[0]["startSeconds"] == 0.0
    assert chapters[0]["endSeconds"] == pytest.approx(cut.cold_open.duration_seconds)
    assert chapters[0]["sentences"][0]["startSeconds"] == pytest.approx(0.0)
    assert all(
        0.0 <= s["startSeconds"] < s["endSeconds"] <= chapters[0]["endSeconds"] + 1e-6
        for s in chapters[0]["sentences"]
    )
    assert all(
        0.0 <= sc["startSeconds"] < sc["endSeconds"] <= chapters[0]["endSeconds"] + 1e-6
        for sc in chapters[0]["scenes"]
    )

    body = chapters[1:]
    assert [c["index"] for c in body] == [3, 4]
    assert body[0]["startSeconds"] == pytest.approx(cut.body_offset_seconds)
    assert body[-1]["endSeconds"] == pytest.approx(cut.outro_start_seconds)
    # Câu đầu của chương 3 nằm ngay mốc bắt đầu thân tập.
    assert body[0]["sentences"][0]["startSeconds"] == pytest.approx(cut.body_offset_seconds)
    # Cảnh liên tục, không mốc âm, không vượt outro.
    for c in body:
        for sc in c["scenes"]:
            assert cut.body_offset_seconds - 1e-6 <= sc["startSeconds"] < sc["endSeconds"] <= cut.outro_start_seconds + 1e-6
        assert all(sc["imagePath"].startswith("output/images/") for sc in c["scenes"])

    assert props["episodeLabel"] == "TẬP 2/3"
    assert props["hookText"] == "Cô bị tráo phôi"
    assert props["coldOpenSeconds"] == pytest.approx(cut.cold_open.duration_seconds)
    assert props["outroSeconds"] == cut.outro_seconds
    assert "Tập 3 lên sóng" in props["outroText"]
    assert props["outroText"].startswith("Bạn sẽ tha thứ chứ?")
    assert props["audioPath"] == "output/episodes/ep-02.wav"


def test_props_tap_cuoi_outro_khong_hen_tap_sau(sandbox):
    props, _ = _props(sandbox, 3)
    assert "lên sóng" not in props["outroText"]
    assert "Đăng ký" in props["outroText"]


def test_outro_text_khong_co_cau_hoi():
    cut = plan_cuts(__import__("tests.episodes.conftest", fromlist=["x"]).make_tts_metadata(), plan_episodes(6))[0]
    assert outro_text(cut, "") == "Tập 2 lên sóng 20h mai — đăng ký để không bỏ lỡ!"


def test_chapter_lines_bat_dau_0_00_va_doi_theo_truc_tap(sandbox):
    script = Script.from_dict(json.loads(sandbox["script_path"].read_text(encoding="utf-8")))
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[1]
    lines = chapter_lines(cut, script, sandbox["tts_metadata"])
    assert lines[0] == {"heading": COLD_OPEN_HEADING, "start_seconds": 0.0}
    assert [l["heading"] for l in lines[1:]] == ["Chương 3", "Chương 4"]
    assert lines[1]["start_seconds"] == pytest.approx(cut.body_offset_seconds, abs=1e-3)
    assert lines[2]["start_seconds"] > lines[1]["start_seconds"]


def test_props_metadata_lech_title_thi_loi(sandbox):
    script = Script.from_dict(json.loads(sandbox["script_path"].read_text(encoding="utf-8")))
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[0]
    bad_images = dict(sandbox["images_metadata"], title="Khác")
    with pytest.raises(EpisodePropsBuildError):
        build_episode_props(
            script, sandbox["tts_metadata"], bad_images, cut,
            audio_path=sandbox["repo_root"] / "a.wav", images_dir=sandbox["images_dir"], repo_root=sandbox["repo_root"],
        )


# --- không có ảnh: dựng bằng video nền (05/10/2026) ---------------------------


def test_props_khong_co_anh_thi_moi_chuong_scenes_rong(sandbox):
    """Có video nền thì bỏ hẳn stage 3 (~30 phút sinh ảnh mỗi truyện): MainVideo
    chỉ vẽ video nền, không cần cảnh ảnh. Mốc chương, câu, cold open vẫn đủ."""
    script = Script.from_dict(json.loads(sandbox["script_path"].read_text(encoding="utf-8")))
    cut = plan_cuts(sandbox["tts_metadata"], plan_episodes(6))[1]
    audio_path = sandbox["repo_root"] / "output" / "episodes" / "ep-02.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"")

    props = build_episode_props(
        script, sandbox["tts_metadata"], None, cut,
        audio_path=audio_path, images_dir=None, repo_root=sandbox["repo_root"],
    )

    assert props["chapters"], "phải còn chương"
    assert all(c["scenes"] == [] for c in props["chapters"])
    assert any(c["sentences"] for c in props["chapters"])
    # Cold open vẫn là chương 0, như khi có ảnh.
    assert props["chapters"][0]["index"] == 0
