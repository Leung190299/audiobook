# scripts/prompts.py
from episodes.plan import EPISODE_COUNT, cliffhanger_chapters, plan_episodes

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


def build_outline_prompt(trope_name: str, trope_description: str) -> str:
    cliff_list = ", ".join(str(c) for c in CLIFFHANGER_CHAPTERS)
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
    chapter_number: int, total_chapters: int, heading: str, summary: str
) -> str:
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
