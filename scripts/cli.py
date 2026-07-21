# scripts/cli.py
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from scripts.generator import generate_script
from scripts.qa import validate_script
from scripts.storage import save_script
from scripts.trope_bank import get_trope

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tropes.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "scripts"


async def _run(trope_id: str) -> None:
    trope = get_trope(CONFIG_PATH, trope_id)
    script = await generate_script(trope.id, trope.name, trope.description)
    validate_script(script)
    out_path = save_script(script, OUTPUT_DIR)

    print(
        f"Đã lưu kịch bản: {out_path} "
        f"({script.word_count} từ, {len(script.chapters)} chương)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh kịch bản truyện audio từ trope.")
    parser.add_argument("trope_id", help="ID trope trong config/tropes.yaml")
    args = parser.parse_args()
    asyncio.run(_run(args.trope_id))


if __name__ == "__main__":
    main()
