import pytest

from scripts.trope_bank import get_trope, load_tropes


def test_load_tropes_returns_all_entries(tmp_path):
    yaml_path = tmp_path / "tropes.yaml"
    yaml_path.write_text(
        "tropes:\n"
        "  - id: demo_id\n"
        "    name: Demo Name\n"
        "    description: Demo description\n",
        encoding="utf-8",
    )

    tropes = load_tropes(yaml_path)

    assert len(tropes) == 1
    assert tropes[0].id == "demo_id"
    assert tropes[0].name == "Demo Name"
    assert tropes[0].description == "Demo description"


def test_get_trope_returns_matching_entry(tmp_path):
    yaml_path = tmp_path / "tropes.yaml"
    yaml_path.write_text(
        "tropes:\n"
        "  - id: a\n    name: A\n    description: desc a\n"
        "  - id: b\n    name: B\n    description: desc b\n",
        encoding="utf-8",
    )

    trope = get_trope(yaml_path, "b")

    assert trope.name == "B"


def test_get_trope_raises_key_error_when_missing(tmp_path):
    yaml_path = tmp_path / "tropes.yaml"
    yaml_path.write_text("tropes:\n  - id: a\n    name: A\n    description: desc\n", encoding="utf-8")

    with pytest.raises(KeyError):
        get_trope(yaml_path, "missing")
