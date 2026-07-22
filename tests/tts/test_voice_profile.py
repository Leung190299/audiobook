from tts.voice_profile import VoiceProfile, load_voice_profile


def test_load_voice_profile_reads_all_fields(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    yaml_path.write_text(
        "instruction: giọng nữ ấm áp\n"
        "target_lufs: -16.0\n"
        "sample_rate: 24000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile == VoiceProfile(
        instruction="giọng nữ ấm áp",
        target_lufs=-16.0,
        sample_rate=24000,
        gap_seconds=0.5,
        ref_audio_path=None,
    )


def test_load_voice_profile_resolves_relative_ref_audio_path(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_path = config_dir / "voice.yaml"
    yaml_path.write_text(
        "instruction: giọng nữ ấm áp\n"
        "ref_audio_path: config/voices/sample.mp3\n"
        "target_lufs: -16.0\n"
        "sample_rate: 24000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile.ref_audio_path == tmp_path / "config" / "voices" / "sample.mp3"


def test_load_voice_profile_keeps_absolute_ref_audio_path(tmp_path):
    yaml_path = tmp_path / "voice.yaml"
    abs_path = tmp_path / "sample.mp3"
    yaml_path.write_text(
        "instruction: giọng nữ ấm áp\n"
        f"ref_audio_path: {abs_path}\n"
        "target_lufs: -16.0\n"
        "sample_rate: 24000\n"
        "gap_seconds: 0.5\n",
        encoding="utf-8",
    )

    profile = load_voice_profile(yaml_path)

    assert profile.ref_audio_path == abs_path
