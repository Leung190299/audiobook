# scripts/generator.py
import asyncio
import json

import anthropic
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from scripts.llm import make_client

from scripts.models import Chapter, Script
from scripts.prompts import (
    MAX_HOOK_WORDS,
    MAX_QUESTION_WORDS,
    MAX_TOPIC_QUESTION_WORDS,
    SHORT_BEAT_COUNT,
    build_chapter_prompt,
    build_length_note,
    build_shorten_prompt,
    chapter_words_range,
    build_outline_prompt,
    build_short_beats_prompt,
    build_story_outline_prompt,
    build_topic_outline_prompt,
)
from scripts.qa import MIN_CHAPTER_WORDS, looks_like_refusal, title_problem
from scripts.text_tools import clean_thumb_fields, clip_chars, locate_quote, split_sentences


# Tên chương hiện trên khung hình ở cỡ chữ 20px và không xuống dòng
# (remotion/src/MainVideo.tsx): dài quá là tràn ra ngoài mép phải.
HEADING_MAX_CHARS = 80

# Số lần hỏi Gemini cho dàn ý trước khi bỏ cuộc. Xem lý do ở generate_script().
OUTLINE_ATTEMPTS = 3
# Giây chờ trước lần thử lại đầu tiên; lần sau nhân đôi, nhân ba.
RETRY_DELAY_SECONDS = 5
# Số lần hỏi lại MỘT chương khi Gemini trả lời từ chối hoặc chương cụt. Tập
# 05/09: chương 4 về là nguyên văn "tôi chỉ là một mô hình ngôn ngữ", 29 từ, và
# được nhận như nội dung thật. Hỏi lại trong cùng chat thường ra chương bình
# thường; hết lượt thì ném lỗi, không bao giờ để chương từ chối lọt xuống TTS.
CHAPTER_ATTEMPTS = 3
# Chương dài hơn trần quá tỉ lệ này thì xin viết gọn lại. 08/10: Claude viết
# 895-1.008 từ/chương dù prompt bảo 590-770, cả truyện 56 phút thay vì 35-45.
# Báo số từ thật của chương trước (build_length_note) kéo chương sau về; chương
# vẫn vượt xa thì mới tốn thêm một lượt viết lại.
SHORTEN_RATIO = 1.15


# Lỗi phía mô hình (mạng, xác thực, quá tải) -- không tự khỏi khi hỏi lại
# trong cùng lượt, nên ném ngay thành ScriptGenerationError.
LLM_ERRORS = (GeminiError, APIError, AuthError, anthropic.APIError)


class ScriptGenerationError(Exception):
    pass


async def generate_script(
    trope_id: str,
    trope_name: str,
    trope_description: str,
    client=None,
    *,
    llm: "str | None" = None,
    fmt: str = "episodes",
    topic=None,
    story=None,
    bank=None,
    setting: str = "",
    avoid_premises: "list[str] | None" = None,
    is_duplicate=None,
) -> Script:
    """Sinh một kịch bản.

    Nhánh cũ (trope/trend): `topic=None`, prompt như trước, chỉ thêm `fmt`.
    Nhánh chủ đề (24/09/2026): `topic` là scripts.topics.Topic; dàn ý trả thêm
    premise/thumb_text/thumb_keywords/short_beats; `is_duplicate(title, premise)`
    trả True thì coi dàn ý là hỏng và hỏi lại (chặn trùng 30 ngày); viết xong
    các chương thì hỏi thêm một lượt lấy NGUYÊN VĂN 3 đoạn hài/sảng.

    `client` là bất cứ gì có `start_chat()` (test truyền giả); bỏ trống thì tạo
    theo `llm` / STORY_LLM (scripts/llm.py): Claude API hoặc Gemini.
    """
    topic_mode = topic is not None
    # Nhánh kho (24/09): truyện đã biên tập sẵn. Loại trừ với topic_mode -- khi
    # có story thì caller truyền topic=None, nên mọi kiểm tra trùng tiêu đề của
    # nhánh chủ đề tự động không chạy, đúng như spec yêu cầu.
    story_mode = story is not None
    if story_mode:
        outline_prompt = build_story_outline_prompt(bank, story, fmt)
    elif topic_mode:
        from scripts.topics import TITLE_MAX_CHARS

        outline_prompt = build_topic_outline_prompt(topic, setting, fmt, avoid_premises)
    else:
        outline_prompt = build_outline_prompt(trope_name, trope_description, fmt)

    if client is None:
        client = await make_client(llm)

    chat = client.start_chat()

    # Gemini thỉnh thoảng trả JSON hỏng ở dàn ý — hay gặp nhất là một dấu nháy kép
    # không escape lọt vào giữa summary của chương cuối, đóng chuỗi sớm và làm vỡ cả
    # khối. Đo thực tế: hỏng 2 lần trong cùng một ngày, cùng vị trí. Prompt đã cấm
    # nháy kép, nhưng cấm không bằng thử lại: hỏng ở đây là mất trắng cả lượt chạy
    # một tiếng rưỡi. Chỉ thử lại lỗi parse; lỗi API thì ném ngay vì nó không tự khỏi.
    outline = None
    retry_note = ""
    for attempt in range(OUTLINE_ATTEMPTS):
        try:
            outline_response = await chat.send_message(outline_prompt + retry_note)
        except LLM_ERRORS as exc:
            raise ScriptGenerationError(f"Mô hình lỗi khi sinh dàn ý: {exc}") from exc

        try:
            outline = _parse_json_response(outline_response.text)
            # Tiêu đề tục coi như dàn ý hỏng: hỏi lại trong cùng chat. Tập 20/09
            # phải dừng tay giữa TTS vì "Bà Chó Sủa…" lọt qua.
            if isinstance(outline, dict) and (problem := title_problem(str(outline.get("title", "")))):
                raise ScriptGenerationError(problem)
            if topic_mode and isinstance(outline, dict):
                title_text = " ".join(str(outline.get("title", "")).split())
                is_last = attempt == OUTLINE_ATTEMPTS - 1
                # Tiêu đề dài hơn 60 ký tự thì bị cắt cụt trên mobile: hỏi lại;
                # lần cuối thì cắt ở ranh giới từ còn hơn mất lượt chạy.
                if len(title_text) > TITLE_MAX_CHARS and not is_last:
                    raise ScriptGenerationError(
                        f"Tiêu đề dài {len(title_text)} ký tự, quá {TITLE_MAX_CHARS}: {title_text!r}"
                    )
                if is_duplicate is not None and is_duplicate(
                    title_text, str(outline.get("premise", ""))
                ):
                    raise ScriptGenerationError(
                        f"Dàn ý trùng truyện đã đăng trong 30 ngày: {title_text!r}"
                    )
            break
        except ScriptGenerationError as exc:
            if attempt == OUTLINE_ATTEMPTS - 1:
                raise
            if topic_mode:
                # Hỏi lại y nguyên thì Gemini hay trả lại đúng dàn ý cũ; nói rõ
                # vì sao bị loại để lần sau khác đi.
                retry_note = f"\n\nLƯU Ý: dàn ý trước KHÔNG dùng được vì: {exc}. Hãy làm dàn ý KHÁC."
            # Chờ trước khi hỏi lại. Một lượt hỏng ngày 03/09 nhận ba phản hồi RỖNG
            # liên tiếp trong chưa đầy hai phút — hỏi lại tức thì chỉ lặp lại đúng
            # trạng thái đó. Chờ vài giây cho Gemini qua cơn.
            await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    try:
        title = outline["title"]
        chapter_plans = [(plan["heading"], plan["summary"]) for plan in outline["chapters"]]
    except (KeyError, TypeError) as exc:
        raise ScriptGenerationError(
            f"Dữ liệu dàn ý không đúng cấu trúc mong đợi: {exc}\n"
            f"Phản hồi thô từ mô hình: {outline_response.text[:500]!r}"
        ) from exc
    # Hai trường mới (22/09) không bắt buộc: Gemini thỉnh thoảng bỏ field phụ dù
    # prompt yêu cầu, và một dàn ý thiếu câu hỏi bình luận không đáng để mất cả
    # lượt chạy -- stage 6 tự thay bằng câu hỏi chung khi rỗng.
    hook = _clip_words(str(outline.get("hook") or ""), MAX_HOOK_WORDS)
    comment_question = _clip_words(
        str(outline.get("comment_question") or ""),
        MAX_TOPIC_QUESTION_WORDS if topic_mode else MAX_QUESTION_WORDS,
    )
    extra: dict = {}
    beat_plans: list[str] = []
    if story_mode:
        # Kho là nguồn sự thật: tiêu đề, hook, câu hỏi và từ khoá thumbnail do
        # người biên tập quyết, Gemini có trả khác cũng bỏ qua.
        title = story.title
        hook = story.hook
        comment_question = story.comment_question
        if story.outline:
            # Dàn ý đã duyệt: chương N theo đúng dòng N, không để Gemini chia lại.
            #
            # Chỉ dùng dòng dàn ý làm CHỈ DẪN VIẾT, không làm tên chương: nó là
            # ghi chú nội bộ cho người viết ("Miếng hài: ...", "Cliffhanger:
            # ..."), mà heading thì bị đốt lên khung hình (MainVideo.tsx) và
            # thành mốc chương trong mô tả YouTube. Ngày 25/09 video truyện #2
            # đã hiện nguyên câu "Miếng hài: bác Cả tự đo đất bằng bước chân"
            # cho người xem. Tên chương lấy của Gemini như nhánh --topic.
            goi_y = [h for h, _ in chapter_plans]
            chapter_plans = [
                (
                    clip_chars(" ".join(goi_y[i].split()), HEADING_MAX_CHARS)
                    if i < len(goi_y) and str(goi_y[i]).strip()
                    else f"Chương {i + 1}",
                    line,
                )
                for i, line in enumerate(story.outline)
            ]
        raw_beats = outline.get("short_beats") or []
        beat_plans = [str(b) for b in raw_beats if str(b).strip()][:SHORT_BEAT_COUNT]
        extra = dict(
            topic=story.topic,
            premise=story.premise,
            story_id=story.id,
            series=story.series,
            thumb_text=story.title,
            thumb_keywords=list(story.thumb_keywords),
        )
    elif topic_mode:
        title = clip_chars(" ".join(str(title).split()), TITLE_MAX_CHARS)
        thumb_text, thumb_keywords = clean_thumb_fields(
            str(outline.get("thumb_text") or ""),
            outline.get("thumb_keywords") or [],
            title,
        )
        raw_beats = outline.get("short_beats") or []
        beat_plans = [str(b) for b in raw_beats if str(b).strip()][:SHORT_BEAT_COUNT]
        extra = dict(
            topic=topic.id,
            setting=setting,
            premise=" ".join(str(outline.get("premise") or "").split()),
            thumb_text=thumb_text,
            thumb_keywords=thumb_keywords,
        )

    total_chapters = len(chapter_plans)
    chapters = []
    w_lo, w_hi = chapter_words_range(fmt)
    length_note = ""
    for i, (heading, summary) in enumerate(chapter_plans):
        chapter_number = i + 1
        for attempt in range(CHAPTER_ATTEMPTS):
            try:
                chapter_response = await chat.send_message(
                    build_chapter_prompt(
                        chapter_number,
                        total_chapters,
                        heading,
                        summary,
                        fmt=fmt,
                        topic_mode=topic_mode,
                    )
                    + length_note
                )
            except LLM_ERRORS as exc:
                raise ScriptGenerationError(
                    f"Mô hình lỗi khi sinh chương {chapter_number}: {exc}"
                ) from exc

            text = chapter_response.text.strip()
            problem = _chapter_problem(text)
            if problem is None:
                break
            if attempt == CHAPTER_ATTEMPTS - 1:
                raise ScriptGenerationError(
                    f"Mô hình không sinh được chương {chapter_number} sau "
                    f"{CHAPTER_ATTEMPTS} lần: {problem}. Nguyên văn: {text[:200]!r}"
                )
            await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        words = len(text.split())
        if words > w_hi * SHORTEN_RATIO:
            try:
                shorter = (await chat.send_message(build_shorten_prompt(words, w_lo, w_hi))).text.strip()
            except LLM_ERRORS as exc:
                print(f"CẢNH BÁO: không viết gọn được chương {chapter_number} ({exc}); giữ bản dài.")
                shorter = ""
            if shorter and _chapter_problem(shorter) is None and len(shorter.split()) < words:
                print(f"Chương {chapter_number}: {words} từ, viết gọn còn {len(shorter.split())}.")
                text = shorter
                words = len(text.split())
        length_note = build_length_note(words, w_lo, w_hi)

        if story_mode and chapter_number == 1 and story.hook:
            # Spec: câu đầu chương 1 phải là hook NGUYÊN VĂN. Prompt đã yêu cầu,
            # nhưng Gemini hay mở bài bằng một câu dẫn -- ghép lại cho chắc.
            first = " ".join(text.split())
            if not first.startswith(story.hook):
                text = f"{story.hook} {text}"

        chapters.append(Chapter(index=chapter_number, heading=heading, text=text))

    short_beats: list[str] = []
    if topic_mode or story_mode:
        short_beats = await _ask_short_beats(chat, beat_plans, chapters)

    return Script(
        trope=trope_id,
        title=title,
        chapters=chapters,
        hook=hook,
        comment_question=comment_question,
        format=fmt,
        short_beats=short_beats,
        **extra,
    )


async def _ask_short_beats(chat, beat_plans: list[str], chapters: list[Chapter]) -> list[str]:
    """Nguyên văn 3 đoạn hài/sảng. Không bắt buộc: hỏng thì trả [] và stage 4/7
    tự rơi về cách chọn đoạn cũ (theo vị trí trong chương) -- một lượt Gemini
    phụ không đáng làm mất cả kịch bản 15 chương vừa viết."""
    sentences = [
        {"text": t, "start_seconds": float(i), "end_seconds": float(i + 1), "chapter_index": c.index}
        for c in chapters
        for i, t in enumerate(split_sentences(c.text))
    ]
    try:
        response = await chat.send_message(build_short_beats_prompt(beat_plans))
        data = _parse_json_response(response.text)
        raw = data.get("short_beats") if isinstance(data, dict) else data
        beats = [" ".join(str(b).split()) for b in (raw or []) if str(b).strip()]
    except Exception as exc:  # noqa: BLE001 -- cố ý: bước phụ, không được làm hỏng kịch bản
        print(f"CẢNH BÁO: không lấy được short_beats ({exc}); stage 4/7 dùng cách chọn đoạn cũ.")
        return []
    # Chỉ giữ đoạn dò được trong văn bản thật -- Gemini đôi khi "trích" bằng
    # cách viết lại, khi đó stage 4/7 không tìm ra mốc thời gian.
    found = [b for b in beats if locate_quote(b, sentences) is not None]
    if len(found) < len(beats):
        print(f"CẢNH BÁO: {len(beats) - len(found)} short_beat không khớp nguyên văn, đã bỏ.")
    return found[:SHORT_BEAT_COUNT]


def _clip_words(text: str, max_words: int) -> str:
    """Gọn một dòng, cắt theo số từ. Gemini hay vượt giới hạn từ vài chữ; cắt
    còn hơn bỏ, vì hook 22 từ vẫn dùng được còn hook rỗng thì không."""
    words = " ".join(text.split()).split(" ")
    words = [w for w in words if w]
    return " ".join(words[:max_words])


def _chapter_problem(text: str) -> "str | None":
    """Lý do một chương không dùng được, hoặc None nếu ổn. Cùng hai tiêu chí với
    scripts/qa.py -- QA là lưới thứ hai cho trường hợp hàm này bị bỏ qua."""
    if looks_like_refusal(text):
        return "lời từ chối của mô hình"
    words = len(text.split())
    if words < MIN_CHAPTER_WORDS:
        return f"chỉ {words} từ, dưới sàn {MIN_CHAPTER_WORDS}"
    return None


def _parse_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[len("json") :].strip()
    elif not text.startswith(("{", "[")) and "{" in text and text.rstrip().endswith(("}", "```")):
        # Claude đôi khi mở bằng một câu dẫn ("Đây là dàn ý:") rồi mới tới khối
        # JSON (có thể bọc ```json). Lấy từ dấu { đầu tới dấu } cuối.
        text = text[text.index("{") : text.rindex("}") + 1]
    try:
        # strict=False: Gemini hay nhét ký tự xuống dòng thô vào giữa chuỗi, mà
        # json.loads mặc định từ chối ký tự điều khiển trong chuỗi. Đo thực tế:
        # lỗi "Invalid control character" làm hỏng một lượt chạy ngày 03/09.
        return json.loads(text, strict=False)
    except json.JSONDecodeError as exc:
        # Gemini từ chối nội dung thì trả văn bản thường, không phải JSON hỏng.
        # Báo đúng loại lỗi kèm nguyên văn: một lượt ngày 03/09 mất bốn lần chạy
        # và ba bản vá nhầm chỗ chỉ vì thông báo cũ nói "không parse được JSON".
        if not text.lstrip().startswith(("{", "[")):
            raise ScriptGenerationError(
                "Mô hình không trả về JSON mà trả văn bản thường — nhiều khả năng "
                f"là lời từ chối nội dung. Nguyên văn: {text[:300]!r}"
            ) from exc
        raise ScriptGenerationError(
            f"Không parse được JSON từ phản hồi mô hình: {exc}"
        ) from exc
