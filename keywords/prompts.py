"""Prompt sinh một bản ghi kho (title/hook/premise/twist...) từ một cụm từ khóa."""

from __future__ import annotations

from scripts.prompts import MAX_HOOK_WORDS, MAX_QUESTION_WORDS, _JSON_QUOTE_RULE
from scripts.topics import TOPICS

TITLE_MAX_CHARS = 60
PREMISE_WORDS = (150, 220)
BANNED_TITLE_STARTS = ("tôi", "trọng sinh", "cô út")


def _topics_block() -> str:
    return "\n".join(f"- {tid}: {t.name}; nhân vật chính: {t.protagonist}" for tid, t in TOPICS.items())


def build_keyword_story_prompt(
    phrase: str, evidence: list[str], rules: list[str], avoid_titles: list[str]
) -> str:
    ev = "\n".join(f"  - {e}" for e in evidence) or "  (chưa kênh nào làm cụm này -- cơ hội từ khóa mới)"
    avoid = "\n".join(f"  - {t}" for t in avoid_titles[-15:]) or "  (trống)"
    lo, hi = PREMISE_WORDS
    return f"""Bạn là biên tập viên kho truyện của một kênh YouTube truyện audio tiếng Việt chuyên
HÀI + VẢ MẶT gia đình, họ hàng, đời thường. Người xem đang gõ tìm cụm này trên YouTube:

TỪ KHÓA: {phrase}

Video của kênh khác đang có view tốt với cụm này (chỉ để biết người xem muốn gì, KHÔNG
được chép tình tiết hay tên):
{ev}

Hãy tạo MỘT truyện mới hoàn toàn mang đúng cụm từ khóa đó, trả về đúng một JSON:
{{
  "topic": "<một trong các id dưới>",
  "title": "<tiêu đề>",
  "hook": "<câu đầu tiên của chương 1>",
  "premise": "<tình huống gốc>",
  "twist": "<cú lật và cao trào>",
  "comment_question": "<câu hỏi bình luận>",
  "thumb_keywords": ["<cụm 2-4 chữ nằm nguyên văn trong title>"]
}}

Chủ đề (topic) hợp lệ:
{_topics_block()}

LUẬT BẮT BUỘC:
- title: tối đa {TITLE_MAX_CHARS} ký tự, viết hoa chữ đầu mỗi từ, PHẢI chứa các từ chính của TỪ KHÓA
  (người xem gõ gì thì tên truyện có chữ đó), dạng '<kẻ xấu theo quan hệ gia đình> + <hành vi
  quá đáng cụ thể>, <tôi đáp trả bằng một hành động/vật thể>'. Nhân vật chính xưng 'Tôi' trong
  tiêu đề, KHÔNG đặt tên riêng ('Chị Lan') vào tiêu đề; mọi từ phải là từ tiếng Việt thông dụng,
  đọc to lên nghe xuôi. KHÔNG mở đầu bằng 'Tôi', 'Trọng Sinh' hay 'Cô Út'. Không trùng các tên đã có:
{avoid}
- hook: tối đa {MAX_HOOK_WORDS} từ, là câu đầu tiên của chương 1: một câu thoại gắt đang diễn ra
  (có thể thêm 3-8 từ dẫn trước dấu hai chấm), dùng nháy đơn bên trong.
- premise: {lo}-{hi} từ, ngôi thứ ba kể về nhân vật 'tôi' có tên, tuổi, nghề, địa danh Việt Nam
  cụ thể; kẻ xấu gọi bằng quan hệ gia đình + hành vi quá đáng; 'tôi' đáp trả bằng giấy tờ,
  tiền, hoặc một hành động công khai. Viết cho MỘT video 35-45 phút, không chia tập.
- twist: {lo}-{hi} từ, bí mật/cú lật ở các chương gần cuối, cao trào vả mặt bằng bằng chứng
  (không bạo lực), kết có hậu hoặc ấm, có số liệu cụ thể (tiền, số lần, ngày) và một câu kết lắng.
- comment_question: tối đa {MAX_QUESTION_WORDS} từ, hỏi người nghe chọn phe, dạng '... 1 = ..., 2 = ...'.
- thumb_keywords: đúng 1 cụm 2-4 chữ xuất hiện nguyên văn trong title.
- Luật viết của kênh:
{chr(10).join(f"  - {r}" for r in rules)}
- Tên người, địa danh, món ăn Việt Nam; không bối cảnh Trung Quốc; không ma/kinh dị; không
  khiêu gợi; không bạo lực gia đình chi tiết; không đưa trẻ vị thành niên vào tình huống người lớn.
{_JSON_QUOTE_RULE}
"""


def build_keyword_story_retry_prompt(problems: list[str]) -> str:
    lines = "\n".join(f"- {p}" for p in problems)
    return f"""Bản vừa rồi chưa đạt:
{lines}

Sửa đúng các điểm trên, giữ nguyên những phần đã đạt, và trả về lại DUY NHẤT một JSON
đầy đủ các trường như trước (topic, title, hook, premise, twist, comment_question, thumb_keywords).
{_JSON_QUOTE_RULE}
"""


def build_keyword_story_edit_prompt(phrase: str, draft_json: str, recent_premises: list[str]) -> str:
    """Biên tập lần hai (10/11): bản nháp đạt luật nhưng mỏng hơn kho biên tập tay
    (ít số liệu, cú lật giải quyết nhanh, lặp địa danh). Yêu cầu đào sâu, giữ nguyên
    tiêu đề và từ khóa."""
    lo, hi = PREMISE_WORDS
    used = "\n".join(f"  - {p}" for p in recent_premises[-6:]) or "  (chưa có)"
    return f"""Bạn là biên tập viên kỳ cựu của kênh. Dưới đây là bản nháp truyện cho từ khóa '{phrase}':

{draft_json}

Hãy BIÊN TẬP LẦN HAI, trả về lại DUY NHẤT một JSON đủ các trường như trên. "title" chỉ sửa
khi có chữ vô nghĩa, có tên riêng, hoặc vế sau không còn đúng hành động của 'tôi' ở cao trào sau khi
biên tập (vế đầu giữ từ khóa; vẫn ≤ {TITLE_MAX_CHARS} ký tự, nhân vật chính xưng 'Tôi'); "thumb_keywords" là 1 cụm 2-4 chữ nằm nguyên văn trong title cuối.
Được sửa mọi trường còn lại. Yêu cầu nâng chất:
- SỐ LIỆU CỤ THỂ: mỗi mốc xung đột có con số thật (tiền theo triệu/tỷ đồng, số năm, số lần,
  ngày tháng, diện tích) để người nghe tin; ít nhất 5 con số trong premise + twist.
- NHÂN VẬT PHỤ: thêm 1-2 nhân vật phụ có tên và vai trò rõ (người đứng về phía 'tôi' bất ngờ,
  kẻ phụ họa cho kẻ xấu, người làm chứng); tên Việt, khác nhau, không trùng tên nhân vật chính.
- CÚ LẬT HAI LỚP: lớp 1 là bằng chứng 'tôi' đã chuẩn bị sẵn; lớp 2 là sự thật lớn hơn mà
  chính 'tôi' cũng chỉ biết ở cao trào (một người thứ ba, một tờ giấy, một đoạn ghi âm).
  Kẻ xấu nhận hậu quả cụ thể (mất gì, phải làm gì), không chỉ 'cúi đầu xấu hổ'.
- MIẾNG HÀI: ít nhất một chi tiết hài hoặc mỏ hỗn trong premise để đúng giọng kênh.
- KẾT LẮNG: câu cuối twist là một hình ảnh/câu thoại nhỏ, ấm, không giảng đạo lý.
- KHÔNG lặp bối cảnh, địa danh, nghề của các truyện gần đây dưới đây; chọn tỉnh/thành và nghề khác:
{used}
- premise và twist mỗi phần {lo}-{hi} từ; hook tối đa {MAX_HOOK_WORDS} từ và tên riêng trong hook
  phải khớp truyện; comment_question tối đa {MAX_QUESTION_WORDS} từ dạng '... 1 = ..., 2 = ...'.
{_JSON_QUOTE_RULE}
"""
