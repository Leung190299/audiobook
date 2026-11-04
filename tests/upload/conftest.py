# tests/upload/conftest.py
import pytest


@pytest.fixture(autouse=True)
def _index_jsonl_tam(tmp_path, monkeypatch):
    """Không bao giờ ghi vào output/metadata/index.jsonl thật của repo khi test."""
    from upload import episodes_cli

    monkeypatch.setattr(episodes_cli, "INDEX_JSONL", tmp_path / "index.jsonl")
    for var in ("YOUTUBE_PLAYLIST_HO_HANG", "YOUTUBE_PLAYLIST_NGHE_LA", "YOUTUBE_PLAYLIST_BO_ME", "YOUTUBE_PLAYLIST_URL"):
        monkeypatch.delenv(var, raising=False)
