from tts.voice_profile import VoiceProfile, load_voice_profile


def test_load_voice_profile_reads_all_fields(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(
        'voice: "Ngọc Linh"\n'
        'style: "doc_truyen"\n'
        "target_lufs: -16.0\n"
        "sample_rate: 48000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile == VoiceProfile(
        voice="Ngọc Linh",
        style="doc_truyen",
        target_lufs=-16.0,
        sample_rate=48000,
        gap_seconds=0.5,
        sentence_gap_seconds=0.15,
        ref_audio_path=None,
    )


def test_load_voice_profile_mac_dinh_sentence_gap_seconds_khi_thieu_trong_cau_hinh(tmp_path):
    # Cấu hình cũ chưa có sentence_gap_seconds -> vẫn phải nạp được, dùng mặc định.
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(
        'voice: "Ngọc Linh"\n'
        'style: "doc_truyen"\n'
        "target_lufs: -16.0\n"
        "sample_rate: 48000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile.sentence_gap_seconds == 0.15


def test_load_voice_profile_doc_sentence_gap_seconds_tuy_chinh(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(
        'voice: "Ngọc Linh"\n'
        'style: "doc_truyen"\n'
        "target_lufs: -16.0\n"
        "sample_rate: 48000\n"
        "gap_seconds: 0.5\n"
        "sentence_gap_seconds: 0.2\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile.sentence_gap_seconds == 0.2


def test_load_voice_profile_resolves_relative_ref_audio_path(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_path = config_dir / "voice.yaml"
    yaml_path.write_text(
        'voice: "Ngọc Linh"\n'
        'style: "doc_truyen"\n'
        "ref_audio_path: config/voices/sample.mp3\n"
        "target_lufs: -16.0\n"
        "sample_rate: 48000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile.ref_audio_path == tmp_path / "config" / "voices" / "sample.mp3"


def test_load_voice_profile_keeps_absolute_ref_audio_path(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    abs_path = tmp_path / "sample.mp3"
    yaml_path.write_text(
        'voice: "Ngọc Linh"\n'
        'style: "doc_truyen"\n'
        f"ref_audio_path: {abs_path}\n"
        "target_lufs: -16.0\n"
        "sample_rate: 48000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile.ref_audio_path == abs_path


def test_load_voice_profile_speed_mac_dinh_1_va_doc_tu_cau_hinh(tmp_path):
    base = 'voice: "A"\nstyle: "doc_truyen"\ntarget_lufs: -16.0\nsample_rate: 48000\ngap_seconds: 0.5\n'
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(base, encoding="utf-8")
    assert load_voice_profile(yaml_path).speed == 1.0
    yaml_path.write_text(base + "speed: 1.25\n", encoding="utf-8")
    assert load_voice_profile(yaml_path).speed == 1.25
