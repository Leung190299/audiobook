"""Biến tín hiệu trend thô thành một ý tưởng truyện gốc, dùng được cho scripts.cli."""

from __future__ import annotations

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


def build_idea_prompt(signals: TrendSignals, recent_titles: list[str]) -> str:
    feed_blocks = []
    for name, titles in signals.feeds.items():
        lines = "\n".join(f"- {t}" for t in titles)
        feed_blocks.append(f"### {name}\n{lines}")
    feeds_text = "\n\n".join(feed_blocks) or "(không lấy được nguồn nào)"

    trends_text = "\n".join(f"- {t}" for t in signals.google_trends) or "(không có dữ liệu)"
    avoid_text = "\n".join(f"- {t}" for t in recent_titles) or "(chưa có)"

    return f"""Bạn là biên tập nội dung cho một kênh YouTube truyện audio tiếng Việt
(thể loại: trọng sinh, báo thù, vả mặt, tâm lý gia đình, drama hôn nhân — khán giả
nữ 25-55 tuổi, nghe khi làm việc nhà hoặc trước khi ngủ).

Dưới đây là tín hiệu hôm nay.

[A] TIÊU ĐỀ BÁO MỚI NHẤT ở các mục tâm sự / đời sống / pháp luật — nguồn chính:

{feeds_text}

[B] Từ khoá đang lên trên Google Trends Việt Nam — chỉ là chất liệu phụ:
{trends_text}

[C] Các truyện kênh đã làm gần đây — TUYỆT ĐỐI không lặp lại motif, tên nhân vật,
hay cấu trúc twist của những truyện này:
{avoid_text}

NHIỆM VỤ: Đề xuất MỘT ý tưởng truyện HOÀN TOÀN HƯ CẤU cho tập hôm nay.

RÀNG BUỘC BẮT BUỘC:
- Nhóm [A] là tín hiệu quan trọng nhất. Đọc để nhận ra dạng xung đột nào đang được
  người Việt quan tâm lúc này (mâu thuẫn mẹ chồng nàng dâu, tranh chấp tài sản,
  ngoại tình, lừa đảo, bất công nơi làm việc...) rồi xây một câu chuyện MỚI quanh
  dạng xung đột đó.
- TUYỆT ĐỐI KHÔNG kể lại, không phóng tác, không dựa vào bất kỳ vụ việc cụ thể nào
  trong [A]. Chỉ mượn DẠNG xung đột, không mượn tình tiết. Không dùng người thật,
  tên thật, địa danh gắn với vụ việc thật, hay thương hiệu thật.
- Nhóm [B] phần lớn là thể thao và tin quốc tế, không dùng được — cứ bỏ qua, đừng
  cố nhét vào.
- Không chuyển thể, dịch, hay mô phỏng sát nội dung tiểu thuyết/phim đã có.
- Ý tưởng phải đủ sức kéo dài 16 chương (10.000-13.000 từ): có tuyến nhân vật phản
  diện rõ, ít nhất hai lần lật kèo, và một kết thúc thoả mãn.

Chỉ trả về DUY NHẤT một khối JSON hợp lệ, không kèm giải thích nào khác:
{{
  "slug": "<định danh ngắn không dấu, chữ thường, dùng gạch dưới, tối đa 4 từ, ví dụ: me_chong_giau_cua>",
  "title_hint": "<tiêu đề gợi ý dạng câu hook giật, tiếng Việt có dấu>",
  "trend_hook": "<1-2 câu: bám vào dạng xung đột nào và vì sao hợp thời điểm hiện tại>",
  "idea": "<8-12 câu mô tả trọn vẹn: bối cảnh, nhân vật chính và động cơ, phản diện, mâu thuẫn mở màn, hai cú lật kèo, cao trào, và kết thúc>"
}}"""


def _parse_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise IdeaGenerationError(
            f"Không parse được JSON ý tưởng từ Gemini: {exc}\n"
            f"Phản hồi thô: {raw_text[:500]!r}"
        ) from exc


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

    try:
        response = await client.generate_content(build_idea_prompt(signals, recent_titles))
    except (GeminiError, APIError, AuthError) as exc:
        raise IdeaGenerationError(f"Gemini lỗi khi sinh ý tưởng: {exc}") from exc

    data = _parse_json_response(response.text)
    try:
        idea_text = data["idea"].strip()
        title_hint = data["title_hint"].strip()
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
