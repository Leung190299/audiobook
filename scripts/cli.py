# scripts/cli.py
import argparse
import asyncio
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from scripts import history, story_bank
from scripts.generator import generate_script
from scripts.prompts import FORMATS
from scripts.qa import validate_script
from scripts.storage import save_script
from scripts.topics import resolve_topic
from scripts.trope_bank import get_trope

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tropes.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "scripts"
HISTORY_PATH = history.DEFAULT_PATH


async def _run(
    trope_id: str | None,
    idea_file: Path | None,
    label: str | None,
    topic_arg: str | None = None,
    fmt: str = "episodes",
    today: date | None = None,
    story_arg: str | None = None,
) -> None:
    today = today or date.today()
    topic = None
    setting = ""
    story = None
    if story_arg is not None:
        # Nhánh kho (24/09/2026): truyện đã biên tập sẵn trong data/story_bank.json.
        # Tiêu đề do người biên tập quyết nên KHÔNG kiểm tra trùng, nhưng vẫn ghi
        # premise vào history để nhánh --topic sau này biết truyện đã kể.
        story = story_bank.get_story(int(story_arg))
        bank = story_bank.load_bank()
        # run_daily.sh đọc hai dòng này: chủ đề để xếp playlist, id để lần vết.
        print(f"Chủ đề: {story.topic}")
        print(f"Truyện: #{story.id} — {story.title}")
        script = await generate_script(
            story.topic, story.title, story.premise, fmt=fmt, story=story, bank=bank
        )
    elif topic_arg is not None:
        # Nhánh chủ đề (24/09/2026): chọn bối cảnh chưa dùng trong 30 ngày, đưa
        # premise đã dùng vào prompt, và chặn dàn ý trùng tiêu đề/premise.
        topic = resolve_topic(topic_arg, today)
        entries = history.load_history(HISTORY_PATH)
        setting = history.pick_setting(topic.settings, entries, topic.id, today)
        print(f"Chủ đề: {topic.id}")
        print(f"Bối cảnh: {setting}")
        script = await generate_script(
            topic.id,
            topic.name,
            setting,
            fmt=fmt,
            topic=topic,
            setting=setting,
            avoid_premises=history.recent_premises(entries, topic.id, today),
            is_duplicate=lambda title, premise: history.is_duplicate(
                entries, topic.id, title, premise, today
            ),
        )
    elif idea_file is not None:
        idea = idea_file.read_text(encoding="utf-8").strip()
        # `label` chỉ đặt tên file/nhãn thể loại — nội dung truyện vẫn lấy từ idea.
        # Không có label thì mọi lượt chạy từ ý tưởng đều ra file "idea-<ts>.json",
        # rất khó lần lại tập nào là tập nào khi chạy tự động hằng ngày.
        # File ý tưởng của stage 0 có dạng "<tiêu đề gợi ý>\n\n<nội dung>", đúng
        # khuôn tên + mô tả mà nhánh trope dùng. Trước đây chỗ này truyền nguyên
        # văn ý tưởng vào CẢ HAI vị trí, khiến prompt chứa cùng một đoạn 1.800 ký
        # tự hai lần (5.644 ký tự thay vì 3.818) và dòng "Motif:" dài cả đoạn văn.
        title_hint, _, body = idea.partition("\n\n")
        script = await generate_script(
            label or "idea", title_hint.strip(), (body or idea).strip(), fmt=fmt
        )
    else:
        trope = get_trope(CONFIG_PATH, trope_id)
        script = await generate_script(trope.id, trope.name, trope.description, fmt=fmt)

    script.format = script.format or fmt
    validate_script(script)
    out_path = save_script(script, OUTPUT_DIR)

    if topic is not None:
        history.record(
            topic.id, setting, script.title, script.premise, str(out_path), today, HISTORY_PATH
        )
    elif story is not None:
        history.record(
            story.topic, "", script.title, script.premise, str(out_path), today, HISTORY_PATH
        )

    print(f"Định dạng: {script.format}")
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
    group.add_argument(
        "--story",
        help="Id truyện trong data/story_bank.json. Tiêu đề, hook, câu hỏi bình "
        "luận và từ khoá thumbnail lấy nguyên từ kho, Gemini chỉ viết chương.",
    )
    group.add_argument(
        "--topic",
        help="Chủ đề trong scripts/topics.py (ho_hang_viet | nghe_la_hong_bien | "
        "bo_me_trong_sinh) hoặc 'auto' (xoay vòng theo AUDIOBOOK_TOPIC_ROTATION).",
    )
    parser.add_argument(
        "--label",
        help=(
            "Nhãn thể loại dùng để đặt tên file output khi chạy với --idea-file "
            "(mặc định 'idea'). Chỉ ảnh hưởng tên file, không ảnh hưởng nội dung."
        ),
    )
    parser.add_argument(
        "--format",
        choices=FORMATS,
        default="episodes",
        help="full = một video 35-45 phút; episodes = 3 tập có cliffhanger (22/09).",
    )
    args = parser.parse_args()
    asyncio.run(
        _run(args.trope_id, args.idea_file, args.label, args.topic, args.format,
             story_arg=args.story)
    )


if __name__ == "__main__":
    main()
