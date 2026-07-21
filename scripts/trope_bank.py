from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Trope:
    id: str
    name: str
    description: str


def load_tropes(path: Path) -> list[Trope]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [
        Trope(id=t["id"], name=t["name"], description=t["description"])
        for t in data["tropes"]
    ]


def get_trope(path: Path, trope_id: str) -> Trope:
    for trope in load_tropes(path):
        if trope.id == trope_id:
            return trope
    raise KeyError(f"Không tìm thấy trope id={trope_id} trong {path}")
