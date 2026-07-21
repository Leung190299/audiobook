# scripts/prompts.py
SYSTEM_PROMPT = """Bạn là biên kịch chuyên viết truyện audio tiếng Việt cho kênh YouTube.
Nhiệm vụ: sáng tác một truyện HOÀN TOÀN GỐC (nguyên tác của bạn), lấy cảm hứng từ
motif/trope được cung cấp — KHÔNG được chuyển thể, dịch, hay mô phỏng sát nội dung
của bất kỳ tiểu thuyết/tác phẩm có sẵn nào. Nhân vật, tên riêng, tình tiết cụ thể
phải do bạn tự sáng tạo.

Yêu cầu:
- Độ dài: 5.000–8.000 từ tiếng Việt.
- Chia thành đúng 8 chương, mỗi chương có tiêu đề ngắn gọn.
- Văn phong ưu tiên thoại và diễn biến tâm lý nhân vật hơn là mô tả thị giác thuần
  tuý, vì người nghe không nhìn màn hình khi nghe.
- Có cao trào rõ ràng và kết thúc thoả mãn (không bỏ lửng trừ khi được yêu cầu).
- Không dùng tên nhân vật, địa danh, hoặc chi tiết cốt truyện trùng với tác phẩm nổi
  tiếng nào đang tồn tại.
"""


def build_outline_prompt(trope_name: str, trope_description: str) -> str:
    return f"""{SYSTEM_PROMPT}

Motif: {trope_name}
Mô tả motif: {trope_description}

Hãy LÊN DÀN Ý (outline) cho truyện gốc theo motif trên — CHƯA viết nội dung đầy đủ, chỉ
lên kế hoạch. Dàn ý gồm:
- Tiêu đề truyện (dạng câu hook giật).
- Đúng 8 chương, mỗi chương có: tiêu đề ngắn gọn, và tóm tắt 2-3 câu về diễn biến
  chính, nhân vật xuất hiện, và cảm xúc/xung đột trung tâm của chương đó. Đảm bảo mạch
  truyện xuyên suốt có cao trào rõ ràng ở các chương cuối và kết thúc thoả mãn.

QUAN TRỌNG: Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm bất kỳ giải thích hay
văn bản nào khác ngoài JSON, đúng theo cấu trúc sau — "chapters" PHẢI là một mảng gồm
CHÍNH XÁC 8 object phẳng (không được lồng mảng con, không được bọc thêm object cha
nào khác), mỗi object chỉ có đúng 2 field "heading" và "summary" dạng chuỗi văn bản:
{{
  "title": "<tiêu đề truyện>",
  "chapters": [
    {{"heading": "<tiêu đề chương 1>", "summary": "<tóm tắt chương 1>"}},
    {{"heading": "<tiêu đề chương 2>", "summary": "<tóm tắt chương 2>"}}
  ]
}}
"""


def build_chapter_prompt(
    chapter_number: int, total_chapters: int, heading: str, summary: str
) -> str:
    return f"""Bây giờ hãy viết ĐẦY ĐỦ nội dung Chương {chapter_number}/{total_chapters}: "{heading}".

Tóm tắt diễn biến chương này theo dàn ý đã thống nhất ở trên: {summary}

YÊU CẦU BẮT BUỘC:
- Viết đầy đủ cảnh, thoại giữa các nhân vật, diễn biến nội tâm chi tiết — KHÔNG tóm tắt.
- Độ dài BẮT BUỘC từ 700 đến 900 từ. Nếu thấy nội dung sắp hết trước khi đủ, hãy mở
  rộng bằng thêm thoại, thêm miêu tả cảm xúc/suy nghĩ nhân vật, thêm chi tiết bối cảnh.
- Giữ nhất quán với các chương trước đó trong cuộc trò chuyện này (tên nhân vật, bối
  cảnh, mạch cảm xúc, mốc thời gian).
- CHỈ trả về nội dung văn xuôi của chương, KHÔNG kèm tiêu đề chương, KHÔNG kèm JSON,
  KHÔNG kèm giải thích hay bình luận nào khác ngoài nội dung truyện.
"""
