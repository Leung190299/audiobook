# tests/tts/test_sentences.py
from tts.sentences import split_sentences


def test_tach_cau_theo_dau_ket_cau():
    assert split_sentences("Cô ấy đến. Trời mưa! Anh biết chứ?") == [
        "Cô ấy đến.",
        "Trời mưa!",
        "Anh biết chứ?",
    ]


def test_cau_ngan_giu_tach_biet():
    assert split_sentences("Không. Dừng lại. Sao?") == [
        "Không.",
        "Dừng lại.",
        "Sao?",
    ]


def test_tach_cau_chuoi_rong():
    assert split_sentences("   ") == []
