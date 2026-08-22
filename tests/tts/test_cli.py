import json
from pathlib import Path

import numpy as np

from scripts.models import Chapter, Script
from tts import cli


def _fake_audio(duration_seconds=1.0, sample_rate=48000, amplitude=0.1) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class _FakeModel:
    def infer(self, text, voice=None, style=None):
        return _fake_audio()


class _FakeModelDoanNgan:
    """Sinh ra buffer rất ngắn (dưới 0.4s) cho mỗi câu — pyloudnorm ném lỗi nếu
    ai đó lỡ chuẩn hoá độ ồn từng câu thay vì trên toàn bộ audio đã ghép."""

    def infer(self, text, voice=None, style=None):
        return _fake_audio(duration_seconds=0.05)


def _voice_yaml(
    tmp_path: Path, gap_seconds="0.1", sentence_gap_seconds=None, ref_audio_path=None
) -> Path:
    voice_path = tmp_path / "voice.yaml"
    content = (
        'voice: "Ngọc Linh"\nstyle: "doc_truyen"\ntarget_lufs: -16.0\n'
        f"sample_rate: 48000\ngap_seconds: {gap_seconds}\n"
    )
    if sentence_gap_seconds is not None:
        content += f"sentence_gap_seconds: {sentence_gap_seconds}\n"
    if ref_audio_path is not None:
        content += f"ref_audio_path: {ref_audio_path}\n"
    voice_path.write_text(content, encoding="utf-8")
    return voice_path


def test_run_generates_normalizes_concatenates_and_saves(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một. Câu hai."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    voice_path = _voice_yaml(tmp_path)
    monkeypatch.setattr(cli, "VOICE_CONFIG_PATH", voice_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    cli._run(script_path, model=_FakeModel())

    saved_audio = list((tmp_path / "output").glob("*.wav"))
    assert len(saved_audio) == 1

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    assert len(saved_metadata) == 1
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề demo"

    assert len(data["chapters"]) == 2
    assert data["chapters"][0]["heading"] == "Chương 1"

    # Chương 1 có 2 câu, chương 2 có 1 câu -> 3 câu tổng cộng, đánh số lại từ 1
    # mỗi chương.
    assert len(data["sentences"]) == 3
    chapter1_sentences = [s for s in data["sentences"] if s["chapter_index"] == 1]
    assert [s["index"] for s in chapter1_sentences] == [1, 2]
    assert chapter1_sentences[0]["text"] == "Nội dung một."
    assert chapter1_sentences[1]["text"] == "Câu hai."

    out = capsys.readouterr().out
    assert "Đã lưu audio" in out
    assert "3 câu" in out


def test_run_khong_vo_khi_cau_ngan_duoi_0_4_giay(tmp_path, monkeypatch):
    # Chuẩn hoá độ ồn phải chạy MỘT LẦN trên audio đã ghép, không phải từng câu:
    # pyloudnorm ném ValueError với buffer dưới 0.4s. Nếu chuẩn hoá bị đặt nhầm
    # vào vòng lặp từng câu, test này đỏ ngay khi model trả buffer 0.05s/câu.
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Sao? Không. Dừng lại. Đi thôi."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    voice_path = _voice_yaml(tmp_path)
    monkeypatch.setattr(cli, "VOICE_CONFIG_PATH", voice_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    cli._run(script_path, model=_FakeModelDoanNgan())

    saved_metadata = list((tmp_path / "output").glob("*.json"))
    data = json.loads(saved_metadata[0].read_text(encoding="utf-8"))
    assert len(data["sentences"]) == 4


class _FakeModelDemGoiEnroll:
    """Đếm add_voice/infer để chứng minh giọng tham chiếu chỉ được enroll một
    lần dù tập có bao nhiêu câu -- đây là điểm mấu chốt của bản sửa finding #1:
    trước đây mỗi câu gọi model.infer(..., ref_audio=...), khiến VieNeu-TTS
    enroll lại (giải mã mp3, khử ồn, trích embedding) từ đầu mỗi câu."""

    def __init__(self):
        self.add_voice_calls = []
        self.infer_calls = []

    def add_voice(self, name, ref_audio, denoise=True, use_ref_codes=True):
        self.add_voice_calls.append((name, ref_audio, denoise, use_ref_codes))
        return name

    def infer(self, text, voice=None, style=None):
        self.infer_calls.append(voice)
        return _fake_audio()


def test_run_enroll_giong_tham_chieu_dung_mot_lan_du_nhieu_cau(tmp_path, monkeypatch):
    script = Script(
        trope="demo",
        title="Tiêu đề demo",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một. Câu hai."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    ref_audio_path = tmp_path / "voices" / "ref.mp3"
    voice_path = _voice_yaml(tmp_path, ref_audio_path=str(ref_audio_path))
    monkeypatch.setattr(cli, "VOICE_CONFIG_PATH", voice_path)
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")

    model = _FakeModelDemGoiEnroll()
    cli._run(script_path, model=model)

    # 2 chương, 3 câu tổng cộng -- nếu code vẫn enroll theo kiểu cũ (ref_audio=
    # trong synthesize_chapter mỗi câu), add_voice_calls sẽ rỗng còn mỗi lần
    # infer sẽ tự enroll lại bên trong model thật; ở đây ta khẳng định trực
    # tiếp add_voice chỉ chạy đúng 1 lần, không phải 1 lần/câu.
    assert len(model.add_voice_calls) == 1
    enrolled_name, ref_audio, denoise, use_ref_codes = model.add_voice_calls[0]
    assert ref_audio == str(ref_audio_path)
    assert denoise is True
    assert use_ref_codes is True

    # Cả 3 câu đều lồng tiếng bằng đúng tên giọng vừa enroll, không phải
    # ref_audio thô.
    assert len(model.infer_calls) == 3
    assert all(voice == enrolled_name for voice in model.infer_calls)


def test_main_parses_argv_and_calls_run(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "_run",
        lambda script_path, model=None: calls.append(script_path),
    )
    monkeypatch.setattr("sys.argv", ["cli.py", "some/script.json"])

    cli.main()

    assert calls == [Path("some/script.json")]
