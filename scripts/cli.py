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


async def _run(trope_id: str | None, idea_file: Path | None, label: str | None) -> None:
    if idea_file is not None:
        idea = idea_file.read_text(encoding="utf-8").strip()
        # `label` chỉ đặt tên file/nhãn thể loại — nội dung truyện vẫn lấy từ idea.
        # Không có label thì mọi lượt chạy từ ý tưởng đều ra file "idea-<ts>.json",
        # rất khó lần lại tập nào là tập nào khi chạy tự động hằng ngày.
        script = await generate_script(label or "idea", idea, idea)
    else:
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("trope_id", nargs="?", help="ID trope trong config/tropes.yaml")
    group.add_argument(
        "--idea-file",
        type=Path,
        help=(
            "Đường dẫn file text chứa ý tưởng truyện tự do (bỏ qua tropes.yaml). "
            "Dùng file thay vì truyền thẳng chuỗi để tránh command injection khi "
            "nội dung đến từ nguồn ngoài (vd: tin nhắn Telegram)."
        ),
    )
    parser.add_argument(
        "--label",
        help=(
            "Nhãn thể loại dùng để đặt tên file output khi chạy với --idea-file "
            "(mặc định 'idea'). Chỉ ảnh hưởng tên file, không ảnh hưởng nội dung."
        ),
    )
    args = parser.parse_args()
    asyncio.run(_run(args.trope_id, args.idea_file, args.label))


if __name__ == "__main__":
    main()
