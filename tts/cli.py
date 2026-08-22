import argparse
import json
from pathlib import Path

from scripts.models import Chapter, Script
from tts.audio_postprocess import concatenate_sentences, normalize_loudness
from tts.sentences import split_sentences
from tts.storage import save_audio
from tts.synthesizer import synthesize_chapter
from tts.voice_profile import load_voice_profile

VOICE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "voice.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "audio"


def _load_model():
    from vieneu import Vieneu

    return Vieneu(backend="onnx")


def _run(script_path: Path, model=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    voice_profile = load_voice_profile(VOICE_CONFIG_PATH)

    if model is None:
        model = _load_model()

    # Đọc từng câu một, không đọc trọn chương, để ghi được mốc thời gian theo
    # câu — stage 7 cần mốc đó để cắt short đúng chỗ mà không phải TTS lại.
    chapters_for_concat = []
    total_sentences = 0
    for chapter in script.chapters:
        sentences = split_sentences(chapter.text)
        pieces = []
        for sentence_index, sentence_text in enumerate(sentences, start=1):
            # synthesize_chapter chỉ dùng chapter.text để đọc, còn index/heading
            # chỉ phục vụ thông báo lỗi -> bọc mỗi câu vào một Chapter tạm là đủ.
            # Giữ index thật của chương và nhét số câu vào heading để thông báo
            # lỗi nêu được cả hai, còn lần ra chỗ hỏng trong một tập 700 câu.
            sentence_chapter = Chapter(
                index=chapter.index,
                heading=f"{chapter.heading}, câu {sentence_index}",
                text=sentence_text,
            )
            audio = synthesize_chapter(sentence_chapter, model, voice_profile)
            pieces.append((sentence_text, audio))
        chapters_for_concat.append((chapter.index, chapter.heading, pieces))
        total_sentences += len(sentences)

    raw_audio, chapter_timings, sentence_timings = concatenate_sentences(
        chapters_for_concat,
        sample_rate=voice_profile.sample_rate,
        sentence_gap_seconds=voice_profile.sentence_gap_seconds,
        chapter_gap_seconds=voice_profile.gap_seconds,
    )
    # Giải phóng ngay các buffer rời từng câu: đã ghép xong vào raw_audio, giữ
    # lại chỉ tốn thêm một bản sao gần bằng cả tập trong lúc chuẩn hoá độ ồn.
    del chapters_for_concat

    # Chuẩn hoá độ ồn MỘT LẦN trên toàn bộ audio đã ghép, không theo từng câu:
    # pyloudnorm ném ValueError với mọi đoạn ngắn hơn 0.4 giây, và đo LUFS trên
    # một câu là vô nghĩa. Đổi hành vi so với trước (mỗi chương chuẩn hoá riêng
    # rồi mới ghép) — hết luôn chênh mức giữa các chương.
    full_audio = normalize_loudness(
        raw_audio, voice_profile.sample_rate, voice_profile.target_lufs
    )

    audio_path, metadata_path = save_audio(
        trope=script.trope,
        title=script.title,
        audio=full_audio,
        sample_rate=voice_profile.sample_rate,
        timings=chapter_timings,
        sentence_timings=sentence_timings,
        output_dir=OUTPUT_DIR,
    )

    duration_seconds = len(full_audio) / voice_profile.sample_rate
    print(
        f"Đã lưu audio: {audio_path} ({duration_seconds:.1f} giây, "
        f"{len(script.chapters)} chương, {total_sentences} câu)\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lồng tiếng kịch bản truyện audio bằng VieNeu-TTS."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    args = parser.parse_args()
    _run(Path(args.script_path))


if __name__ == "__main__":
    main()
