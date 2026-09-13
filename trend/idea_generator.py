"""Biến tín hiệu trend thô thành một ý tưởng truyện gốc, dùng được cho scripts.cli."""

from __future__ import annotations

import asyncio
import json
import os
import re
import unicodedata
from dataclasses import dataclass

from gemini_webapi import GeminiClient
from gemini_webapi.exceptions import APIError, AuthError, GeminiError

from trend.sources import TrendSignals


class IdeaGenerationError(Exception):
    pass


@dataclass
class StoryIdea:
    slug: str
    title_hint: str
    trend_hook: str
    idea: str

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title_hint": self.title_hint,
            "trend_hook": self.trend_hook,
            "idea": self.idea,
        }


MAX_SLUG_CHARS = 40


def slugify(raw: str, fallback: str = "trend") -> str:
    """ASCII slug dùng làm tên file — cùng quy ước gạch dưới với trope id.

    Cùng cách bỏ dấu như metadata/filename.py (NFD rồi loại dấu thanh), khác ở
    ký tự nối: trope id dùng `_`, còn slug tên file video dùng `-`.
    """
    normalized = unicodedata.normalize("NFD", raw.strip())
    without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    # "đ"/"Đ" là chữ cái riêng, NFD không tách được nên phải thay tay.
    without_accents = without_accents.replace("Đ", "D").replace("đ", "d")
    slug = re.sub(r"[^a-z0-9]+", "_", without_accents.lower()).strip("_")
    return slug[:MAX_SLUG_CHARS].rstrip("_") or fallback


# Các khuôn kể chuyện kênh dùng được. Liệt kê ra để Gemini CHỌN có ý thức thay vì
# mặc định trọng sinh: 22/22 tập từ 08/08 đến 13/09 đều mở đầu "Trọng sinh tôi mặc
# kệ…", trong khi 8 kênh đối thủ đo ngày 07/09 đang chạy thiên kim thật, trà xanh,
# tiếng lòng, mỏ hỗn/cá mặn -- không kênh nào lấy trọng sinh làm khuôn chính.
STORY_FRAMES = [
    "Thiên kim thật trở về: con gái bị tráo/thất lạc về nhà giàu, lột mặt con nuôi trà xanh",
    "Vả mặt trà xanh/tiểu tam: kẻ giả tạo chọc nhầm người, bị lật mặt trước cả nhà",
    "Tiếng lòng bị nghe thấy: cả nhà nghe được suy nghĩ thật của nữ chính, quay xe",
    "Mỏ hỗn / cá mặn: nữ chính bốp chát, lười biếng nhưng lại được cả hào môn cưng",
    "Hợp đồng hôn nhân / gả thay / hôn ước từ bé: cưới vì điều kiện, yêu vì bất ngờ",
    "Ly hôn xong mới phất: bị coi thường, rời đi, thành công, chồng cũ hối hận",
    "Hào môn sủng vợ: thái tử gia/sếp tổng lạnh lùng với đời, nghiện vợ",
    "Hiện thực gia đình không kỳ ảo: mẹ chồng, tài sản, ngoại tình -- thắng bằng mưu trí",
    "Trọng sinh / xuyên không: sống lại hoặc xuyên về, biết trước mà lật ngược thế cờ",
]

# Tên khuôn xuyên không dùng trong thông báo cấm -- phải khớp đúng một mục ở trên.
TIME_TRAVEL_FRAME = STORY_FRAMES[-1]

# Từ khoá nhận diện khuôn xuyên không trong tiêu đề đã làm (lịch sử chỉ lưu tiêu
# đề, không lưu khuôn, nên phải đoán từ chữ).
TIME_TRAVEL_MARKERS = (
    "trọng sinh", "xuyên không", "xuyên về", "sống lại", "trở về quá khứ",
    "quay về quá khứ", "kiếp trước", "một đời nữa",
)

# Số tập gần nhất xét khi cấm: 3 => khuôn xuyên không tối đa 1 trong 4 tập.
BAN_WINDOW = 3


def uses_time_travel(title: str) -> bool:
    lowered = title.lower()
    return any(marker in lowered for marker in TIME_TRAVEL_MARKERS)


def banned_frames(recent_titles: list[str], window: int = BAN_WINDOW) -> list[str]:
    """Khuôn nào đã dùng trong `window` tập gần nhất thì hôm nay cấm.

    Chỉ áp cho xuyên không vì đó là khuôn duy nhất bị lạm dụng tới mức 22/22.
    Cấm theo cửa sổ trượt chứ không cấm hẳn: người dùng muốn "ít" chứ không
    phải "không bao giờ".
    """
    if any(uses_time_travel(t) for t in recent_titles[-window:]):
        return [TIME_TRAVEL_FRAME]
    return []


def clean_title(raw: str) -> str:
    """Bóc vỏ bọc kiểu kênh đối thủ khỏi tiêu đề.

    Khi prompt bắt đầu cho Gemini xem tiêu đề kênh đối thủ để học khuôn, nó chép
    luôn cả cách đóng gói: "[Truyện Audio Full] | ... | Vả Mặt Audio". Lên kênh
    mình thì thành quảng cáo cho đối thủ. Tách theo "|" hoặc "||", bỏ các mảnh
    là nhãn chung hoặc tên kênh, giữ mảnh dài nhất -- chính là câu hook.
    """
    pieces = [piece.strip() for piece in re.split(r"\|{1,2}", raw) if piece.strip()]
    if len(pieces) <= 1:
        return raw.strip()
    def is_wrapper(piece: str) -> bool:
        lowered = piece.lower().strip("[] ")
        return (
            lowered.startswith("truyện audio")
            or lowered.endswith("audio")
            or lowered in {"truyện full", "audio full"}
        )
    content = [piece for piece in pieces if not is_wrapper(piece)]
    return max(content or pieces, key=len).strip("[] ").strip()


def build_idea_prompt(signals: TrendSignals, recent_titles: list[str]) -> str:
    # Tách kênh YouTube khỏi báo: hai nguồn này trả lời hai câu hỏi khác nhau.
    # Báo cho biết XUNG ĐỘT nào đang được bàn; kênh đối thủ cho biết KHUÔN kể
    # chuyện nào đang kéo view. Trước đây gộp chung và bảo "chỉ mượn dạng xung
    # đột", nên khuôn đang hot chưa bao giờ được dùng làm khuôn.
    news_blocks, channel_blocks = [], []
    for name, titles in signals.feeds.items():
        lines = "\n".join(f"- {t}" for t in titles)
        block = f"### {name}\n{lines}"
        (channel_blocks if name.startswith("Kênh YouTube") else news_blocks).append(block)
    news_text = "\n\n".join(news_blocks) or "(không lấy được nguồn nào)"
    channels_text = "\n\n".join(channel_blocks) or "(không lấy được kênh nào)"

    trends_text = "\n".join(f"- {t}" for t in signals.google_trends) or "(không có dữ liệu)"

    # Chỉ đưa 8 tiêu đề gần nhất. Đưa 15 cái cùng một mở đầu là dạy mẫu cho
    # Gemini bắt chước, dù có ghi "tránh" bên trên.
    avoid_text = "\n".join(f"- {t}" for t in recent_titles[-8:]) or "(chưa có)"

    frames_text = "\n".join(f"{i}. {f}" for i, f in enumerate(STORY_FRAMES, start=1))
    banned = banned_frames(recent_titles)
    if banned:
        ban_text = "CẤM hôm nay (đã dùng trong 3 tập gần nhất):\n" + "\n".join(
            f"- {f}" for f in banned
        )
    else:
        ban_text = "Hôm nay KHÔNG bị cấm khuôn nào -- nhưng vẫn phải khác 8 tập gần nhất."

    return f"""Bạn là biên tập nội dung cho một kênh YouTube truyện audio tiếng Việt
(drama gia đình và ngôn tình hiện đại -- khán giả nữ 25-55 tuổi, nghe khi làm việc
nhà hoặc trước khi ngủ).

Dưới đây là tín hiệu hôm nay.

[A] TIÊU ĐỀ BÁO MỚI NHẤT ở các mục tâm sự / đời sống / pháp luật -- cho biết
XUNG ĐỘT nào đang được người Việt bàn tán:

{news_text}

[B] TIÊU ĐỀ MỚI NHẤT của các kênh truyện audio đang kéo view -- cho biết KHUÔN kể
chuyện và cách đặt tiêu đề nào đang hợp thị hiếu. Mượn khuôn và giọng tiêu đề,
KHÔNG mượn cốt truyện:

{channels_text}

[C] Từ khoá Google Trends -- chất liệu phụ, phần lớn không dùng được:
{trends_text}

[D] 8 tập gần nhất kênh đã làm. Chúng mở đầu gần giống nhau -- đó là LỖI đang cần
sửa, không phải phong cách để noi theo:
{avoid_text}

KHUÔN KỂ CHUYỆN có thể chọn (chọn đúng MỘT):
{frames_text}

{ban_text}

NHIỆM VỤ: Đề xuất MỘT ý tưởng truyện HOÀN TOÀN HƯ CẤU cho tập hôm nay.

RÀNG BUỘC BẮT BUỘC:
- Chọn khuôn từ danh sách trên, ưu tiên khuôn đang thấy nhiều trong [B]; không
  được chọn khuôn bị cấm.
- Lấy XUNG ĐỘT từ [A]: đọc để nhận ra dạng mâu thuẫn đang được quan tâm (mẹ chồng
  nàng dâu, tranh chấp tài sản, ngoại tình, lừa đảo, bất công nơi làm việc...)
  rồi xây câu chuyện MỚI quanh dạng xung đột đó, đặt trong khuôn đã chọn.
- TUYỆT ĐỐI KHÔNG kể lại, phóng tác, hay dựa vào bất kỳ vụ việc cụ thể nào trong
  [A]. Chỉ mượn DẠNG xung đột. Không dùng người thật, tên thật, địa danh gắn với
  vụ việc thật, thương hiệu thật.
- Tiêu đề KHÔNG ĐƯỢC BẮT ĐẦU BẰNG "Trọng sinh", "Xuyên không", hay 3 từ đầu của
  bất kỳ tiêu đề nào trong [D]. Hook phải là TÌNH HUỐNG (ai làm gì, bị gì), không
  phải nhãn thể loại.
- Tiêu đề là văn bản thuần: KHÔNG chép vỏ bọc của kênh khác như
  "[Truyện Audio Full]", "Truyện Audio ||", dấu "|" -- và TUYỆT ĐỐI không có
  tên kênh nào.
- Không chuyển thể, dịch, hay mô phỏng sát nội dung tiểu thuyết/phim đã có.
- Ý tưởng phải đủ sức kéo dài 16 chương (10.000-13.000 từ): có tuyến phản diện
  rõ, ít nhất hai lần lật kèo, và một kết thúc thoả mãn.

Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm giải thích nào khác:
{{
  "slug": "<định danh ngắn không dấu, chữ thường, dùng gạch dưới, tối đa 4 từ, ví dụ: thien_kim_lang_chai>",
  "title_hint": "<tiêu đề dạng câu hook giật, tiếng Việt có dấu, mở đầu bằng tình huống>",
  "trend_hook": "<1-2 câu: chọn khuôn nào, bám dạng xung đột nào trong [A], vì sao hợp lúc này>",
  "idea": "<8-12 câu mô tả trọn vẹn: bối cảnh, nhân vật chính và động cơ, phản diện, mâu thuẫn mở màn, hai cú lật kèo, cao trào, và kết thúc>"
}}"""


def _parse_json_response(raw_text: str) -> dict:
    """Đọc JSON từ phản hồi Gemini, chịu được các kiểu trả lời lỗi thường gặp:
    code fence, ký tự điều khiển nằm trong chuỗi, nhiều khối JSON dính liền
    nhau, hoặc văn bản thừa bao quanh khối JSON."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()

    # 1) Parse trực tiếp; strict=False chấp nhận ký tự điều khiển trong chuỗi.
    try:
        data = json.loads(text, strict=False)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2) Nhiều khối JSON dính nhau / văn bản thừa: thử từng khối {...} phẳng.
    for match in re.finditer(r"\{[^{}]*\}", text):
        try:
            data = json.loads(match.group(0), strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "idea" in data and "title_hint" in data:
            return data

    # 3) Cứu vãn từng field khi JSON hỏng nặng (chuỗi bị cắt cụt giữa chừng).
    fields: dict = {}
    for key in ("slug", "title_hint", "trend_hook", "idea"):
        m = re.search(r'"' + key + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if not m:
            continue
        try:
            fields[key] = json.loads('"' + m.group(1) + '"', strict=False)
        except json.JSONDecodeError:
            fields[key] = m.group(1)
    if fields.get("idea") and fields.get("title_hint"):
        return fields

    raise IdeaGenerationError(
        "Không parse được JSON ý tưởng từ Gemini: phản hồi không chứa khối JSON hợp lệ\n"
        f"Phản hồi thô: {raw_text[:500]!r}"
    )


async def generate_idea(
    signals: TrendSignals,
    recent_titles: list[str],
    client: "GeminiClient | None" = None,
) -> StoryIdea:
    if client is None:
        client = GeminiClient(
            os.environ["SECURE_1PSID"],
            os.environ["SECURE_1PSIDTS"],
        )
        await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)

    prompt = build_idea_prompt(signals, recent_titles)
    reinforcement = (
        "\n\nLƯU Ý QUAN TRỌNG: Đây là yêu cầu SÁNG TÁC TRUYỆN HƯ CẤU giải trí"
        " lành mạnh thuộc thể loại drama gia đình, hoàn toàn không liên quan tới"
        " người thật việc thật và không yêu cầu bất kỳ thông tin nhạy cảm nào."
        " Đừng từ chối; hãy trả về đúng MỘT khối JSON theo mẫu ở trên."
    )
    data: dict | None = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.generate_content(
                prompt if attempt == 0 else prompt + reinforcement
            )
        except (GeminiError, APIError, AuthError) as exc:
            last_error = IdeaGenerationError(f"Gemini lỗi khi sinh ý tưởng: {exc}")
            await asyncio.sleep(3)
            continue
        try:
            data = _parse_json_response(response.text)
            break
        except IdeaGenerationError as exc:
            # Gemini từ chối hoặc trả về rác — thử lại với lời nhắc hư cấu.
            last_error = exc
            await asyncio.sleep(3)
            continue
    if data is None:
        raise last_error if last_error else IdeaGenerationError(
            "Gemini không trả về ý tưởng nào sau 3 lượt thử"
        )
    try:
        idea_text = data["idea"].strip()
        title_hint = clean_title(data["title_hint"])
    except (KeyError, AttributeError, TypeError) as exc:
        raise IdeaGenerationError(
            f"Ý tưởng thiếu field bắt buộc: {exc}\nDữ liệu nhận được: {data!r}"
        ) from exc

    if not idea_text:
        raise IdeaGenerationError("Gemini trả về field 'idea' rỗng")

    return StoryIdea(
        slug=slugify(str(data.get("slug") or title_hint)),
        title_hint=title_hint,
        trend_hook=str(data.get("trend_hook") or "").strip(),
        idea=idea_text,
    )
