# tests/thumbnail/test_sticker.py
"""Layout thumbnail 'linh vật sticker + cả câu tiêu đề' (24/09/2026)."""

import io
import json

import pytest
from PIL import Image, ImageDraw, ImageFont

from scripts.models import Chapter, Script
from scripts.topics import TOPICS
from thumbnail import cli
from thumbnail.sticker import (
    HEIGHT,
    MAX_LINES,
    MIN_FONT_SIZE,
    TITLE_FONT_PATH,
    WIDTH,
    compose_sticker_thumbnail,
    cut_out_background,
    text_bounds,
)

# 12 chữ, dấu chồng (Ố Ẫ Ự Ỹ), từ dài.
LONG_TITLES = {
    "ho_hang_viet": "Bác Cả Đòi Chia Đất Hương Hoả, Tôi Livestream Luôn Cả Họ",
    "nghe_la_hong_bien": "Giặt Đồ Thuê, Tôi Tìm Thấy Sổ Đỏ Trong Túi Áo Khách",
    "bo_me_trong_sinh": "Trọng Sinh Năm Sáu Mươi Tuổi, Tôi Không Chia Nhà Ố Ẫ",
}


def _mascot_bytes() -> bytes:
    img = Image.new("RGB", (512, 512), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([100, 120, 420, 480], fill=(90, 190, 90), outline=(60, 35, 20), width=12)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_font_co_du_dau_tieng_viet():
    # Ký tự font không có sẽ vẽ ra ô .notdef giống hệt nhau; so với một ký tự
    # chắc chắn không có (vùng dùng riêng) là biết thiếu dấu nào.
    font = ImageFont.truetype(str(TITLE_FONT_PATH), 80)

    def glyph(ch: str) -> bytes:
        img = Image.new("L", (120, 160), 0)
        ImageDraw.Draw(img).text((10, 20), ch, font=font, fill=255)
        return img.tobytes()

    notdef = glyph("\ue000")
    for ch in "ỐẪỰỸốẫựỹĐđƯƠẠẶẬỆỊỘỢỤỪỬỮỲỴ":
        assert glyph(ch) != notdef, f"font thiếu {ch}"
    assert glyph("Ố") != glyph("O")


@pytest.mark.parametrize("topic_id", sorted(LONG_TITLES))
def test_tieu_de_12_chu_co_dau_khong_tran_khung(topic_id):
    title = LONG_TITLES[topic_id]
    assert len(title.split()) == 12
    size, lines, widest, height, box_w = text_bounds(title)
    assert size >= MIN_FONT_SIZE
    assert lines <= MAX_LINES
    assert widest <= box_w
    png = compose_sticker_thumbnail(
        _mascot_bytes(), title, ["Chia Đất", "Sổ Đỏ", "Không Chia"], TOPICS[topic_id].thumb_palette
    )
    img = Image.open(io.BytesIO(png))
    assert img.size == (WIDTH, HEIGHT)
    assert len(png) < 2 * 1024 * 1024  # trần thumbnail của YouTube
    # Nền góc phải dưới vẫn là màu pastel của chủ đề (chữ không tràn ra mép).
    bg = tuple(int(TOPICS[topic_id].thumb_palette[0][i : i + 2], 16) for i in (1, 3, 5))
    assert img.convert("RGB").getpixel((WIDTH - 3, HEIGHT - 3)) == bg


def test_mau_nen_khac_nhau_theo_chu_de():
    pixels = set()
    for topic_id in TOPICS:
        png = compose_sticker_thumbnail(None, "Tôi Làm Chủ Trọ", [], TOPICS[topic_id].thumb_palette)
        pixels.add(Image.open(io.BytesIO(png)).convert("RGB").getpixel((WIDTH - 3, HEIGHT - 3)))
    assert len(pixels) == len(TOPICS)


def test_tach_nen_trang_thanh_trong_suot():
    cut = cut_out_background(Image.open(io.BytesIO(_mascot_bytes())))
    assert cut.mode == "RGBA"
    # Đã crop sát nhân vật, góc là nền đã trong suốt, tâm vẫn đục.
    assert cut.getpixel((0, 0))[3] == 0
    assert cut.getpixel((cut.width // 2, cut.height // 2))[3] == 255


def _topic_script(tmp_path, fmt="full"):
    script = Script(
        trope="ho_hang_viet",
        title="Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn",
        topic="ho_hang_viet",
        format=fmt,
        thumb_text="Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn",
        thumb_keywords=["Chia Đất", "Livestream Luôn"],
        chapters=[Chapter(index=1, heading="C1", text="x")],
    )
    path = tmp_path / "script.json"
    path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")
    return path


async def test_cli_chu_de_full_ra_ban_a_va_b_khong_goi_gemini(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "out")
    names = []

    def fake_sticker(name):
        names.append(name)
        return _mascot_bytes()

    monkeypatch.setattr(cli, "load_sticker", fake_sticker)

    async def boom(*a, **k):
        raise AssertionError("không được gọi Gemini cho kịch bản chủ đề")

    monkeypatch.setattr(cli, "generate_thumbnail_prompt", boom)
    await cli._run(_topic_script(tmp_path), gemini_client=object())
    out = capsys.readouterr().out
    assert "Đã lưu thumbnail:" in out and "-thumbnail-a.png" in out
    assert "Thumbnail B:" in out and "-thumbnail-b.png" in out
    files = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert len(files) == 2
    assert names == list(TOPICS["ho_hang_viet"].thumb_stickers), "bản B đổi sticker linh vật"
    a, b = ((tmp_path / "out" / f).read_bytes() for f in files)
    assert a != b


async def test_cli_chu_de_episodes_giu_badge_tap(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(cli, "load_sticker", lambda name: _mascot_bytes())
    manifest = tmp_path / "x-episodes.json"
    manifest.write_text(
        json.dumps({"format": "episodes", "episodes": [{"number": n, "total": 3} for n in (1, 2, 3)]}),
        encoding="utf-8",
    )
    await cli._run(_topic_script(tmp_path, "episodes"), episodes_manifest=manifest)
    out = capsys.readouterr().out
    assert out.count("Thumbnail tập") == 3 and "Thumbnail B:" in out


def test_moi_sticker_cua_chu_de_ghep_duoc_thumbnail():
    from thumbnail.sticker import load_sticker

    for topic in TOPICS.values():
        for name in topic.thumb_stickers:
            png = compose_sticker_thumbnail(load_sticker(name), "Tiêu Đề Thử", [], topic.thumb_palette)
            assert Image.open(io.BytesIO(png)).size == (WIDTH, HEIGHT)


def test_thieu_sticker_bao_cach_cat(tmp_path, monkeypatch):
    from thumbnail import sticker as mod

    monkeypatch.setattr(mod, "STICKER_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="cut_sticker_sheet"):
        mod.load_sticker("hum")
