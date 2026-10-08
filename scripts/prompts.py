# scripts/prompts.py
from __future__ import annotations

from typing import TYPE_CHECKING

from episodes.plan import EPISODE_COUNT, cliffhanger_chapters, plan_episodes

if TYPE_CHECKING:
    from scripts.topics import Topic

FORMATS = ("full", "episodes")

TARGET_CHAPTERS = 16
TOTAL_WORDS_RANGE = "10.000–13.000"

# Chương phải kết bằng cliffhanger = chương cuối của tập 1 và tập 2 (xem
# episodes/plan.py). Với 16 chương: chương 5 và chương 11. Đọc từ cùng một kế
# hoạch mà stage 4 dùng để cắt video, nên cú lật luôn rơi đúng cuối tập.
CLIFFHANGER_CHAPTERS = tuple(cliffhanger_chapters(TARGET_CHAPTERS))

# Số từ tối đa cho câu hook và câu hỏi bình luận. Hook lên dòng đầu mô tả và
# card mở đầu nên phải đọc trong 2 giây; câu hỏi phải trả lời được bằng một
# câu ngắn thì người nghe mới gõ.
MAX_HOOK_WORDS = 20
MAX_QUESTION_WORDS = 25


def _episode_plan_text() -> str:
    lines = []
    for ep in plan_episodes(TARGET_CHAPTERS):
        tail = "kết thúc trọn vẹn" if ep.is_last else "chương cuối tập PHẢI kết bằng cliffhanger"
        lines.append(
            f"- Tập {ep.number}/{ep.total}: chương {ep.first_chapter}–{ep.last_chapter} ({tail})"
        )
    return "\n".join(lines)


SYSTEM_PROMPT = f"""Bạn là biên kịch chuyên viết truyện audio tiếng Việt cho kênh YouTube.
Nhiệm vụ: sáng tác một truyện HOÀN TOÀN GỐC (nguyên tác của bạn), lấy cảm hứng từ
motif/trope được cung cấp — KHÔNG được chuyển thể, dịch, hay mô phỏng sát nội dung
của bất kỳ tiểu thuyết/tác phẩm có sẵn nào. Nhân vật, tên riêng, tình tiết cụ thể
phải do bạn tự sáng tạo.

Yêu cầu:
- Độ dài: {TOTAL_WORDS_RANGE} từ tiếng Việt.
- Chia thành đúng {TARGET_CHAPTERS} chương, mỗi chương có tiêu đề ngắn gọn.
- Truyện sẽ được đăng thành {EPISODE_COUNT} TẬP (mỗi tập 15–20 phút nghe) theo đúng ranh giới:
{_episode_plan_text()}
- Chương 1 phải MỞ THẲNG VÀO XUNG ĐỘT ngay câu đầu tiên (một câu thoại gắt, một cú
  tát, một tờ đơn ly hôn, một bản xét nghiệm…). KHÔNG mở bằng giới thiệu bối cảnh,
  tiểu sử nhân vật, thời tiết hay 'ngày xưa'. Người nghe trên YouTube quyết định
  ở lại hay bỏ đi trong 30 giây đầu.
- Cliffhanger nghĩa là: chương dừng ĐÚNG khoảnh khắc một bí mật vừa hé lộ, một cú
  lật vừa xảy ra, hoặc nhân vật chính vừa ra một quyết định không thể quay đầu —
  câu cuối chương là câu khiến người nghe bắt buộc phải bấm tập sau.
- Văn phong ưu tiên thoại và diễn biến tâm lý nhân vật hơn là mô tả thị giác thuần
  tuý, vì người nghe không nhìn màn hình khi nghe.
- Có cao trào rõ ràng ở các chương cuối và kết thúc thoả mãn (không bỏ lửng ở tập
  cuối).
- Không dùng tên nhân vật, địa danh, hoặc chi tiết cốt truyện trùng với tác phẩm nổi
  tiếng nào đang tồn tại.
"""


def build_outline_prompt(trope_name: str, trope_description: str, fmt: str = "episodes") -> str:
    cliff_list = ", ".join(str(c) for c in CLIFFHANGER_CHAPTERS)
    if fmt == "full":
        # Bản FULL không chia tập: bỏ ranh giới tập/cliffhanger khỏi prompt cũ,
        # giữ nguyên phần còn lại để nhánh trope/trend chạy được cả hai định dạng.
        return _full_outline_from_trope(trope_name, trope_description)
    return f"""{SYSTEM_PROMPT}

Motif: {trope_name}
Mô tả motif: {trope_description}

Hãy LÊN DÀN Ý (outline) cho truyện gốc theo motif trên — CHƯA viết nội dung đầy đủ, chỉ
lên kế hoạch. Dàn ý gồm:
- Tiêu đề truyện (dạng câu hook giật, dưới 60 ký tự).
- Đúng {TARGET_CHAPTERS} chương, mỗi chương có: tiêu đề ngắn gọn, và tóm tắt 2-3 câu về diễn biến
  chính, nhân vật xuất hiện, và cảm xúc/xung đột trung tâm của chương đó. Tóm tắt của
  chương {cliff_list} PHẢI nói rõ cliffhanger kết chương là gì. Đảm bảo mạch
  truyện xuyên suốt có cao trào rõ ràng ở các chương cuối và kết thúc thoả mãn.
- Một câu HOOK (tối đa {MAX_HOOK_WORDS} từ): nỗi oan hoặc cú lật lớn nhất của truyện, viết như
  lời quảng cáo khiến người ta phải nghe. Không tiết lộ cái kết.
- Một CÂU HỎI BÌNH LUẬN (tối đa {MAX_QUESTION_WORDS} từ): hỏi thẳng người nghe họ sẽ làm gì ở tình
  huống then chốt của truyện (ví dụ: 'Nếu là bạn, bạn ký đơn hay tha thứ?'). Phải trả
  lời được bằng một câu ngắn.

QUAN TRỌNG: Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm bất kỳ giải thích hay
văn bản nào khác ngoài JSON, đúng theo cấu trúc sau — "chapters" PHẢI là một mảng gồm
CHÍNH XÁC {TARGET_CHAPTERS} object phẳng (không được lồng mảng con, không được bọc thêm object cha
nào khác), mỗi object chỉ có đúng 2 field "heading" và "summary" dạng chuỗi văn bản:
{{
  "title": "<tiêu đề truyện>",
  "hook": "<câu hook>",
  "comment_question": "<câu hỏi bình luận>",
  "chapters": [
    {{"heading": "<tiêu đề chương 1>", "summary": "<tóm tắt chương 1>"}},
    {{"heading": "<tiêu đề chương 2>", "summary": "<tóm tắt chương 2>"}}
  ]
}}

TUYỆT ĐỐI KHÔNG dùng dấu nháy kép bên trong nội dung của "title", "hook",
"comment_question", "heading" hay "summary" — muốn nhấn mạnh hay trích lời thoại thì
dùng nháy đơn. Một dấu nháy kép lọt vào giữa chuỗi sẽ đóng chuỗi sớm và làm hỏng cả
khối JSON.
"""


def build_chapter_prompt(
    chapter_number: int,
    total_chapters: int,
    heading: str,
    summary: str,
    fmt: str = "episodes",
    topic_mode: bool = False,
) -> str:
    if fmt == "full":
        return _build_full_chapter_prompt(chapter_number, total_chapters, heading, summary, topic_mode)
    if chapter_number == 1:
        structure_rule = (
            "- Đây là CHƯƠNG MỞ ĐẦU: ba câu đầu tiên phải là hành động hoặc lời thoại "
            "đang diễn ra trong xung đột (không giới thiệu nhân vật, không tả bối "
            "cảnh, không 'ngày xưa'). Người nghe phải biết ngay ai đang bị hại và bởi "
            "ai trước khi hết đoạn đầu tiên.\n"
        )
    elif chapter_number in CLIFFHANGER_CHAPTERS:
        structure_rule = (
            "- Đây là CHƯƠNG CUỐI TẬP: câu cuối cùng của chương PHẢI là cliffhanger — "
            "dừng đúng khoảnh khắc bí mật vừa hé lộ / cú lật vừa xảy ra / quyết định "
            "không thể quay đầu vừa được đưa ra. KHÔNG giải quyết, KHÔNG tóm tắt, "
            "KHÔNG viết câu kết kiểu 'và mọi chuyện bắt đầu từ đây'. Câu cuối phải "
            "là một câu ngắn, mạnh.\n"
        )
    elif chapter_number == total_chapters:
        structure_rule = (
            "- Đây là CHƯƠNG KẾT: giải quyết trọn vẹn xung đột chính, kẻ ác nhận hậu "
            "quả rõ ràng, nhân vật chính có kết thúc thoả mãn. Không bỏ lửng.\n"
        )
    else:
        structure_rule = ""
    if topic_mode:
        structure_rule += TOPIC_CHAPTER_VOICE_RULE

    return f"""Bây giờ hãy viết ĐẦY ĐỦ nội dung Chương {chapter_number}/{total_chapters}: "{heading}".

Tóm tắt diễn biến chương này theo dàn ý đã thống nhất ở trên: {summary}

YÊU CẦU BẮT BUỘC:
{structure_rule}- Viết đầy đủ cảnh, thoại giữa các nhân vật, diễn biến nội tâm chi tiết — KHÔNG tóm tắt.
- Độ dài BẮT BUỘC từ 650 đến 800 từ — TUYỆT ĐỐI không vượt quá 800 từ (các chương trước
  từng viết dài hơn yêu cầu, dẫn đến tổng truyện vượt giới hạn cho phép). Nếu thấy nội
  dung sắp hết trước khi đủ 650 từ, hãy mở rộng bằng thêm thoại, thêm miêu tả cảm
  xúc/suy nghĩ nhân vật, thêm chi tiết bối cảnh — nhưng dừng lại ngay khi chạm mốc 800 từ.
- Giữ nhất quán với các chương trước đó trong cuộc trò chuyện này (tên nhân vật, bối
  cảnh, mạch cảm xúc, mốc thời gian).
- CHỈ trả về nội dung văn xuôi của chương, KHÔNG kèm tiêu đề chương, KHÔNG kèm JSON,
  KHÔNG kèm giải thích hay bình luận nào khác ngoài nội dung truyện.
"""


# --- Định dạng FULL + 3 chủ đề (24/09/2026) ----------------------------------
#
# Tốc độ đọc VieNeu đo trên 6 tập 20-24/09/2026: 18,4-18,8 ký tự/giây, tức
# ~4,25 từ/giây. Mục tiêu 35-45 phút sau TTS => 8.900-11.500 từ. Chỉnh hai hằng
# số này nếu đổi giọng/tốc độ đọc, mọi con số trong prompt tự tính lại.
TTS_CHARS_PER_SECOND = 18.5
TTS_WORDS_PER_SECOND = 4.25
FULL_TARGET_MINUTES = (35, 45)
FULL_CHAPTERS_RANGE = (14, 16)
FULL_TARGET_CHAPTERS = 15
# Văn Claude đọc chậm hơn: truyện #43 (08/10) 11.913 từ ra video 53:47, tức
# ~3,75 từ/giây. Claude viết nhiều thoại ngắn, ~39 đoạn/chương so với ~11 của
# Gemini, mỗi câu thêm một quãng nghỉ (sentence_gap_seconds). Đo trên MỘT
# truyện -- đo lại sau vài truyện nữa.
CLAUDE_WORDS_PER_SECOND = 3.75


def words_per_second() -> float:
    """Tốc độ đọc dùng để quy phút ra số từ, theo mô hình đang viết truyện."""
    from scripts.llm import CLAUDE, resolve_provider

    try:
        claude = resolve_provider() == CLAUDE
    except ValueError:
        claude = False
    return CLAUDE_WORDS_PER_SECOND if claude else TTS_WORDS_PER_SECOND


def full_words_range() -> tuple[int, int]:
    lo, hi = FULL_TARGET_MINUTES
    wps = words_per_second()
    return (
        int(round(lo * 60 * wps, -2)),
        int(round(hi * 60 * wps, -2)),
    )


# Khoảng số từ một chương ở định dạng 3 tập (ghi cứng trong prompt chương).
EPISODE_CHAPTER_WORDS = (650, 800)


def chapter_words_range(fmt: str) -> tuple[int, int]:
    """Khoảng số từ một chương mà prompt chương yêu cầu, theo định dạng."""
    return full_chapter_words_range() if fmt == "full" else EPISODE_CHAPTER_WORDS


def build_length_note(words: int, lo: int, hi: int) -> str:
    """Nhắc số từ THẬT của chương vừa viết, nối vào cuối prompt chương sau.

    Mô hình không đếm được chữ của chính nó; báo con số đo được thì chương sau
    tự co lại. Trong khoảng cho phép thì không nói gì."""
    if words > hi:
        return (
            f"\n\nLƯU Ý ĐỘ DÀI: chương vừa rồi dài {words} từ, VƯỢT trần {hi}. "
            f"Chương này viết NGẮN hơn hẳn, trong khoảng {lo}-{hi} từ."
        )
    if words < lo:
        return f"\n\nLƯU Ý ĐỘ DÀI: chương vừa rồi chỉ {words} từ, dưới {lo}. Chương này viết đủ {lo}-{hi} từ."
    return ""


def build_shorten_prompt(words: int, lo: int, hi: int) -> str:
    return (
        f"Chương vừa viết dài {words} từ, vượt quá trần {hi} từ. Viết lại CHÍNH chương đó "
        f"gọn còn {lo}-{hi} từ (đếm theo tiếng cách nhau bởi dấu cách): giữ nguyên diễn "
        "biến, tên nhân vật, các câu thoại đắt và câu kết chương; bỏ bớt miêu tả lặp và "
        "thoại thừa. CHỈ trả về văn xuôi của chương, KHÔNG tiêu đề, KHÔNG giải thích."
    )


def full_chapter_words_range() -> tuple[int, int]:
    lo, hi = full_words_range()
    return (int(round(lo / FULL_TARGET_CHAPTERS, -1)), int(round(hi / FULL_TARGET_CHAPTERS, -1)))


def _fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


SHORT_BEAT_COUNT = 3
# Câu hỏi chọn phe có hai vế đáp án ("1 = ..., 2 = ...") nên dài hơn câu hỏi cũ;
# cắt ở 25 từ dễ mất vế 2.
MAX_TOPIC_QUESTION_WORDS = 35

TOPIC_CHAPTER_VOICE_RULE = (
    "- Giữ giọng kể ngôi 'tôi'. Chương PHẢI có ít nhất 1 miếng hài (thoại mỏ hỗn / so sánh "
    "bất ngờ) và 1 nhịp sảng (kẻ xấu bị bẽ mặt nhỏ).\n"
)

_JSON_QUOTE_RULE = """TUYỆT ĐỐI KHÔNG dùng dấu nháy kép bên trong nội dung chuỗi — muốn trích lời thoại thì
dùng nháy đơn. Một dấu nháy kép lọt vào giữa chuỗi sẽ làm hỏng cả khối JSON."""


def _full_outline_from_trope(trope_name: str, trope_description: str) -> str:
    lo, hi = full_words_range()
    c_lo, c_hi = FULL_CHAPTERS_RANGE
    return f"""Bạn là biên kịch chuyên viết truyện audio tiếng Việt cho kênh YouTube.
Sáng tác một truyện HOÀN TOÀN GỐC lấy cảm hứng từ motif dưới đây — không chuyển thể
hay mô phỏng tác phẩm có sẵn. Truyện đăng thành MỘT video FULL {FULL_TARGET_MINUTES[0]}–{FULL_TARGET_MINUTES[1]} phút.

Motif: {trope_name}
Mô tả motif: {trope_description}

Yêu cầu: {_fmt_num(lo)}–{_fmt_num(hi)} từ, {c_lo}–{c_hi} chương (khuyến nghị {FULL_TARGET_CHAPTERS}). Chương 1 mở thẳng
vào xung đột; cao trào rõ ở các chương cuối; kết thúc thoả mãn.

Hãy LÊN DÀN Ý (chưa viết nội dung). Chỉ trả về DUY NHẤT một khối JSON:
{{
  "title": "<tiêu đề dưới 60 ký tự>",
  "hook": "<tối đa {MAX_HOOK_WORDS} từ>",
  "comment_question": "<tối đa {MAX_QUESTION_WORDS} từ>",
  "chapters": [
    {{"heading": "<tiêu đề chương>", "summary": "<tóm tắt 2-3 câu>"}}
  ]
}}
"chapters" là mảng phẳng {c_lo}–{c_hi} object, mỗi object đúng 2 field "heading" và "summary".
{_JSON_QUOTE_RULE}
"""


def build_topic_outline_prompt(
    topic: "Topic",
    setting: str,
    fmt: str = "full",
    avoid_premises: list[str] | None = None,
) -> str:
    """Dàn ý cho một truyện thuộc 1 trong 3 chủ đề trọng tâm (scripts/topics.py).

    Trả thêm so với dàn ý cũ: premise, thumb_text, thumb_keywords, short_beats
    (kế hoạch 3 đoạn hài/sảng -- nguyên văn được hỏi lại sau khi viết xong)."""
    from scripts.topics import (
        THUMB_TEXT_MAX_WORDS,
        TITLE_MAX_CHARS,
        VIETNAM_ONLY_RULE,
        VOICE_RULES,
    )

    if fmt == "full":
        lo, hi = full_words_range()
        c_lo, c_hi = FULL_CHAPTERS_RANGE
        length_rule = (
            f"- Truyện đăng thành MỘT video FULL {FULL_TARGET_MINUTES[0]}–{FULL_TARGET_MINUTES[1]} phút: "
            f"{_fmt_num(lo)}–{_fmt_num(hi)} từ, {c_lo}–{c_hi} chương (khuyến nghị {FULL_TARGET_CHAPTERS})."
        )
        chapters_rule = f"từ {c_lo} đến {c_hi} chương"
        cliff_rule = ""
    else:
        length_rule = (
            f"- {TOTAL_WORDS_RANGE} từ, đúng {TARGET_CHAPTERS} chương, đăng thành {EPISODE_COUNT} TẬP theo ranh giới:\n"
            + _episode_plan_text()
        )
        chapters_rule = f"đúng {TARGET_CHAPTERS} chương"
        cliff_list = ", ".join(str(c) for c in CLIFFHANGER_CHAPTERS)
        cliff_rule = f"\n  Tóm tắt chương {cliff_list} PHẢI nói rõ cliffhanger kết chương."

    voice = "\n".join(f"- {r}" for r in VOICE_RULES)
    if topic.vietnam_only:
        voice += f"\n- {VIETNAM_ONLY_RULE}"
    formulas = "\n".join(f"  • {f}" for f in topic.title_formulas)
    banned = list(topic.banned_motifs)
    avoid = [p for p in (avoid_premises or []) if p]
    banned_text = "\n".join(f"  • {b}" for b in banned)
    avoid_text = (
        "\nCác truyện CÙNG CHỦ ĐỀ đã đăng trong 30 ngày qua — KHÔNG được lặp lại tình huống, "
        "tiêu đề hay cú lật của chúng:\n" + "\n".join(f"  • {a}" for a in avoid[-20:])
        if avoid
        else ""
    )

    return f"""Bạn là biên kịch truyện audio tiếng Việt cho một kênh YouTube chuyên truyện HÀI + VẢ MẶT.
Sáng tác một truyện HOÀN TOÀN GỐC — không chuyển thể, không mô phỏng tác phẩm có sẵn.

CHỦ ĐỀ: {topic.name}
- Nhân vật chính: {topic.protagonist}
- Bối cảnh cho truyện này: {setting}
- Giọng: {topic.tone}
{length_rule}

LUẬT GIỌNG KỂ:
{voice}

KHÔNG dùng các motif đã bão hoà:
{banned_text}{avoid_text}

Hãy LÊN DÀN Ý (chưa viết nội dung đầy đủ). Dàn ý gồm:
- "title": tiêu đề TỐI ĐA {TITLE_MAX_CHARS} ký tự, là MỘT CÂU KỂ CHUYỆN ngôi 'Tôi' hoặc câu tình huống,
  Viết Hoa Chữ Cái Đầu Mỗi Từ, theo một trong các công thức:
{formulas}
- "premise": 1 câu (tối đa 30 từ) tóm tình huống gốc của truyện.
- "thumb_text": chữ in lên thumbnail, TỐI ĐA {THUMB_TEXT_MAX_WORDS} chữ — thường chính là tiêu đề hoặc bản rút gọn của nó.
- "thumb_keywords": mảng 1–3 cụm từ cần tô màu nổi bật; mỗi cụm PHẢI là chuỗi con nguyên văn của thumb_text.
- "hook": tối đa {MAX_HOOK_WORDS} từ, cú lật/miếng hài lớn nhất, viết như lời mời nghe. Không lộ cái kết.
- "comment_question": {topic.comment_question_style} Tối đa {MAX_TOPIC_QUESTION_WORDS} từ.
- "short_beats": mảng đúng {SHORT_BEAT_COUNT} chuỗi — mỗi chuỗi mô tả một đoạn buồn cười/sảng nhất của truyện
  (ghi rõ nằm ở chương nào), mỗi đoạn phải TỰ ĐỨNG ĐƯỢC khi cắt riêng làm video ngắn 30–55 giây.
  Đoạn đầu tiên là đoạn sảng nhất (dùng làm mở đầu video).
- "chapters": {chapters_rule}, mỗi chương có "heading" (ngắn gọn) và "summary" (2-3 câu: diễn biến,
  miếng hài, nhịp sảng của chương).{cliff_rule}

QUAN TRỌNG: Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm giải thích:
{{
  "title": "...",
  "premise": "...",
  "thumb_text": "...",
  "thumb_keywords": ["..."],
  "hook": "...",
  "comment_question": "...",
  "short_beats": ["...", "...", "..."],
  "chapters": [
    {{"heading": "...", "summary": "..."}}
  ]
}}
"chapters" là mảng phẳng, mỗi object đúng 2 field "heading" và "summary".
{_JSON_QUOTE_RULE}
"""


def _build_full_chapter_prompt(
    chapter_number: int, total_chapters: int, heading: str, summary: str, topic_mode: bool
) -> str:
    w_lo, w_hi = full_chapter_words_range()
    if chapter_number == 1:
        structure_rule = (
            "- Đây là CHƯƠNG MỞ ĐẦU: câu đầu tiên là tình huống xung đột đang diễn ra, câu thứ "
            "hai là một câu chọc cười. Không chào hỏi, không giới thiệu bản thân, không tả thời tiết.\n"
        )
    elif chapter_number == total_chapters:
        structure_rule = (
            "- Đây là CHƯƠNG KẾT: cú vả mặt lớn nhất, kẻ xấu nhận hậu quả rõ ràng, nhân vật "
            "chính có kết thúc thoả mãn. Không bỏ lửng.\n"
        )
    elif chapter_number == total_chapters - 1:
        structure_rule = "- Chương áp chót: dồn căng thẳng lên đỉnh, chuẩn bị cho cú vả mặt lớn ở chương kết.\n"
    else:
        structure_rule = ""
    voice_rule = TOPIC_CHAPTER_VOICE_RULE if topic_mode else ""
    return f"""Bây giờ hãy viết ĐẦY ĐỦ nội dung Chương {chapter_number}/{total_chapters}: "{heading}".

Tóm tắt diễn biến chương này theo dàn ý đã thống nhất ở trên: {summary}

YÊU CẦU BẮT BUỘC:
{structure_rule}{voice_rule}- Viết đầy đủ cảnh, thoại, nội tâm — KHÔNG tóm tắt.
- Độ dài BẮT BUỘC từ {w_lo} đến {w_hi} từ — không vượt quá {w_hi} từ. Đếm theo TIẾNG
  cách nhau bởi dấu cách ("con gái" là 2 từ, "bà nội tôi" là 3 từ), không đếm theo từ ghép.
- Giữ nhất quán với các chương trước trong cuộc trò chuyện này (tên nhân vật, bối cảnh, mốc thời gian).
- CHỈ trả về văn xuôi của chương, KHÔNG kèm tiêu đề chương, KHÔNG JSON, KHÔNG giải thích.
"""


def build_short_beats_prompt(beat_plans: list[str]) -> str:
    """Hỏi lại NGUYÊN VĂN các đoạn hài/sảng sau khi đã viết xong mọi chương.

    Dàn ý chỉ mô tả đoạn sẽ hay; stage 4/7 cần đúng chữ đã được đọc thành audio
    để dò ra mốc thời gian, nên phải trích từ chính văn bản vừa viết."""
    plans = "\n".join(f"{i}. {p}" for i, p in enumerate(beat_plans, start=1)) or "(tự chọn)"
    return f"""Truyện đã viết xong. Hãy chọn {SHORT_BEAT_COUNT} đoạn buồn cười / sảng nhất trong CÁC CHƯƠNG VỪA VIẾT
(ưu tiên đúng các đoạn đã lên kế hoạch dưới đây, nếu có):
{plans}

Mỗi đoạn:
- TRÍCH NGUYÊN VĂN, liên tục, từ 60 đến 130 từ, copy đúng từng chữ như trong chương (không sửa, không tóm tắt).
- Mở bằng một câu thoại buồn cười hoặc sảng, tự đứng được khi nghe riêng.
- Đoạn thứ nhất là đoạn sảng nhất.

Chỉ trả về DUY NHẤT một JSON: {{"short_beats": ["<đoạn 1>", "<đoạn 2>", "<đoạn 3>"]}}
{_JSON_QUOTE_RULE}
"""


def build_story_outline_prompt(bank, story, fmt: str = "full") -> str:
    """Dàn ý cho một truyện lấy từ kho biên tập sẵn (`data/story_bank.json`).

    Khác `build_topic_outline_prompt`: tiêu đề, hook, câu hỏi bình luận và từ
    khoá thumbnail ĐÃ có sẵn, Gemini không được nghĩ lại — nó chỉ chia chương và
    chọn 3 đoạn cắt Shorts. Truyện thuộc series thì chèn nguyên khối nhân vật để
    tên và tính cách nhất quán giữa các truyện cùng series.
    """
    from scripts.topics import THUMB_TEXT_MAX_WORDS

    if fmt == "full":
        lo, hi = full_words_range()
        c_lo, c_hi = FULL_CHAPTERS_RANGE
        length_rule = (
            f"- Một video FULL {FULL_TARGET_MINUTES[0]}–{FULL_TARGET_MINUTES[1]} phút: "
            f"{_fmt_num(lo)}–{_fmt_num(hi)} từ, {c_lo}–{c_hi} chương "
            f"(khuyến nghị {FULL_TARGET_CHAPTERS})."
        )
        chapters_rule = f"từ {c_lo} đến {c_hi} chương"
    else:
        length_rule = f"- {TOTAL_WORDS_RANGE} từ, đúng {TARGET_CHAPTERS} chương."
        chapters_rule = f"đúng {TARGET_CHAPTERS} chương"

    rules = "\n".join(f"- {r}" for r in bank.writing_rules)

    series_block = ""
    info = bank.series_for(story)
    if info:
        cast = "\n".join(f"  • {ten}: {tinh}" for ten, tinh in (info.get("cast") or {}).items())
        series_block = (
            f"\nSERIES: {story.series} — giữ ĐÚNG tên và tính cách nhân vật dưới đây,"
            " vì khán giả đã nghe các truyện trước của series này.\n"
            f"- Người kể: {info.get('narrator', '')}\n"
            f"- Bối cảnh: {info.get('setting', '')}\n"
            + (f"- Nhân vật:\n{cast}\n" if cast else "")
        )

    if story.outline:
        outline_lines = "\n".join(
            f"  {i}. {line}" for i, line in enumerate(story.outline, start=1)
        )
        chapters_rule = (
            f"ĐÚNG {len(story.outline)} chương, bám SÁT dàn ý đã duyệt dưới đây,"
            f" chương N theo đúng dòng N:\n{outline_lines}"
        )

    return f"""Bạn là biên kịch truyện audio tiếng Việt cho một kênh chuyên truyện HÀI + VẢ MẶT.
Truyện dưới đây ĐÃ được biên tập duyệt. Nhiệm vụ của bạn là chia chương và viết dàn ý,
KHÔNG đổi tiêu đề, KHÔNG đổi tình huống gốc, KHÔNG đổi cú lật.

TIÊU ĐỀ (cố định, chép lại nguyên văn): {story.title}
TÌNH HUỐNG GỐC: {story.premise}
CÚ LẬT: {story.twist}
CÂU MỞ ĐẦU (phải là câu đầu tiên của chương 1, nguyên văn): {story.hook}
{series_block}
{length_rule}

LUẬT VIẾT:
{rules}

Hãy LÊN DÀN Ý (chưa viết nội dung đầy đủ):
- "chapters": {chapters_rule}
  Mỗi chương có "heading" (ngắn gọn) và "summary" (2-3 câu: diễn biến, miếng hài, nhịp sảng).
  Chương 1 bắt đầu thẳng bằng CÂU MỞ ĐẦU ở trên, không chào hỏi, không dẫn nhập.
  Cú lật ở trên phải rơi vào chương gần cuối và là cao trào vả mặt lớn nhất.
- "short_beats": mảng đúng {SHORT_BEAT_COUNT} chuỗi — mỗi chuỗi mô tả một đoạn buồn cười/sảng
  nhất (ghi rõ nằm ở chương nào), mỗi đoạn TỰ ĐỨNG ĐƯỢC khi cắt riêng làm video ngắn 30–55 giây.
  Đoạn đầu tiên là đoạn sảng nhất (dùng làm mở đầu video).
- "thumb_text": chép lại đúng tiêu đề ở trên (tối đa {THUMB_TEXT_MAX_WORDS} chữ).

QUAN TRỌNG: Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm giải thích:
{{
  "title": "{story.title}",
  "thumb_text": "...",
  "short_beats": ["...", "...", "..."],
  "chapters": [
    {{"heading": "...", "summary": "..."}}
  ]
}}
"chapters" là mảng phẳng, mỗi object đúng 2 field "heading" và "summary".
{_JSON_QUOTE_RULE}
"""
