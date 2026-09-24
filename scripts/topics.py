# scripts/topics.py
"""Registry 3 chủ đề trọng tâm của kênh (spec 24/09/2026).

Một chủ đề = một "dòng sản phẩm": cùng kiểu nhân vật chính, cùng giọng kể, cùng
màu thumbnail, cùng playlist. Id dùng làm khoá ở mọi nơi: CLI (`--topic`),
manifest stage 4, playlist stage 8, báo cáo KPI.

Vì sao 3 chủ đề này (phân tích đối thủ 24/09): các kênh đang thắng (Dứa Audio,
Mê Cung Audio) toàn hit là video FULL một truyện, giọng hài + vả mặt, nữ chính
ngôi "tôi" mỏ hỗn. Ba chủ đề dưới cùng giọng đó nhưng bối cảnh Việt Nam và né
các mảng đã bão hoà (xem SATURATED_MOTIFS).

Xoay vòng theo ngày: `AUDIOBOOK_TOPIC_ROTATION` trong .env, 7 id cách nhau dấu
phẩy, phần tử thứ i dùng cho thứ (i+1) trong tuần (0 = thứ Hai). Sau 14 ngày,
chủ đề kém nhất bị giảm tần suất bằng cách sửa đúng biến này.

    uv run python -m scripts.topics              # in bảng chủ đề
    uv run python -m scripts.topics auto         # in id của hôm nay
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date

# Cặn bão hoà trên thị trường truyện audio Việt 09/2026 -- cấm ở mọi chủ đề.
SATURATED_MOTIFS: tuple[str, ...] = (
    "cá mặn hậu cung",
    "tiệm vàng mã / cõi âm / buôn bán với người chết",
    "hệ thống thất đức / hệ thống nhiệm vụ",
    "ảnh đế, ảnh hậu, showbiz, giới giải trí",
    "xem bói cho hào môn / thầy bói nhà giàu",
)

# Luật giọng chung cho cả 3 chủ đề (stage 1 chèn nguyên văn vào prompt).
VOICE_RULES: tuple[str, ...] = (
    "Kể ở ngôi thứ nhất 'tôi' xuyên suốt.",
    "Câu đầu tiên của truyện là một tình huống xung đột đang diễn ra, câu thứ hai "
    "là một câu chọc cười. KHÔNG chào hỏi, KHÔNG giới thiệu bản thân, KHÔNG 'ngày xưa'.",
    "Mỗi chương có ít nhất 1 'miếng hài' (thoại mỏ hỗn, so sánh bất ngờ, tự giễu) và "
    "1 nhịp 'sảng' (kẻ xấu bị bẽ mặt nhỏ ngay trong chương).",
    "Cao trào vả mặt lớn nhất đặt ở chương cuối của mạch truyện.",
    "Không bạo lực chi tiết, không khiêu gợi, không đặt nhân vật vị thành niên vào "
    "tình huống người lớn.",
)

VIETNAM_ONLY_RULE = (
    "Tên người, địa danh, món ăn, phong tục đều là của VIỆT NAM (vd: Hằng, Tuấn, bác "
    "Cả, dì Út; Nam Định, Thủ Đức; bánh chưng, giỗ đầu, mâm cỗ). TUYỆT ĐỐI không dùng "
    "tên, địa danh hay bối cảnh Trung Quốc."
)

# Công thức tiêu đề chung (spec §1). Ví dụ đi kèm để Gemini bắt chước nhịp câu.
TITLE_MAX_CHARS = 60
THUMB_TEXT_MAX_WORDS = 12


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    protagonist: str
    settings: tuple[str, ...]
    title_formulas: tuple[str, ...]
    tone: str
    comment_question_style: str
    # (nền pastel, màu từ khoá 1, màu từ khoá 2) -- hex "#RRGGBB"
    thumb_palette: tuple[str, str, str]
    mascot_pose_hints: tuple[str, ...]
    playlist_env: str
    hashtags: tuple[str, str]
    vietnam_only: bool = True
    banned_motifs: tuple[str, ...] = field(default=SATURATED_MOTIFS)


TOPICS: dict[str, Topic] = {
    "ho_hang_viet": Topic(
        id="ho_hang_viet",
        name="Họ hàng cực phẩm, tôi mỏ hỗn xử đẹp",
        protagonist="nữ 25–35 tuổi, tỉnh táo, mỏ hỗn, không nhịn ai nhưng không ác",
        settings=(
            "Tết về quê, cả họ tra hỏi lương thưởng và chuyện lấy chồng",
            "đám giỗ ông nội, bác Cả đòi chia lại đất hương hoả",
            "đám cưới quê, họ hàng đòi tiền mừng gấp đôi",
            "cô dì vay tiền mua đất rồi 'quên' trả",
            "họ hàng so sánh con cái trong mâm cỗ Rằm tháng Giêng",
            "bố mẹ bị họ hàng ép đứng tên sổ đỏ hộ",
            "anh họ mượn xe đi đám cưới rồi đâm hỏng",
            "mợ út lập nhóm Zalo gia đình để đòi quỹ họ",
            "bà nội thiên vị cháu đích tôn khi chia vàng",
            "họ hàng kéo lên thành phố ở nhờ cả tháng ăn chực",
            "chị dâu mượn danh nghĩa tôi đi vay nóng",
            "cả họ góp tiền xây nhà thờ họ nhưng bác trưởng ôm quỹ",
        ),
        title_formulas=(
            "[Kẻ cực phẩm] + [đòi X], + [tôi làm Y] — vd 'Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn'",
            "[Tình huống] + [hành động bất ngờ của tôi] — vd 'Tết Về Quê Bị Hỏi Lương, Tôi Đưa Luôn Sao Kê'",
        ),
        tone="hài 70% / vả mặt 30%",
        comment_question_style=(
            "Câu hỏi CHỌN PHE có đúng 2 lựa chọn đánh số, đặt người nghe vào đúng tình "
            "huống họ hàng trong truyện. Dạng: 'Nếu là bạn, bạn có <X> không? 1 = <A>, 2 = <B>'."
        ),
        thumb_palette=("#FFE3C2", "#E4312B", "#1E7A46"),
        mascot_pose_hints=(
            "arms crossed with a smug side-eye",
            "holding a red envelope with a sly grin",
            "pointing forward, mouth open mid-roast",
        ),
        playlist_env="YOUTUBE_PLAYLIST_HO_HANG",
        hashtags=("#hohangcucpham", "#truyenhai"),
    ),
    "nghe_la_hong_bien": Topic(
        id="nghe_la_hong_bien",
        name="Nghề lạ đời thường, ngày ngày hóng biến",
        protagonist="người làm nghề dịch vụ ở Việt Nam, ngôi 'tôi', quan sát giỏi, miệng lanh",
        settings=(
            "chủ nhà trọ mười phòng mười drama",
            "tài xế xe ôm công nghệ chạy ca đêm",
            "chủ tiệm giặt ủi nhặt được bí mật trong túi áo khách",
            "chủ tiệm cầm đồ đầu hẻm",
            "giúp việc theo giờ cho nhà giàu",
            "livestream bán hàng online bị đối thủ chơi xấu",
            "shipper giao đơn cho khách bom hàng",
            "thợ dọn nhà thuê theo giờ",
            "thợ sửa điện thoại thấy tin nhắn lạ",
            "bảo vệ chung cư ca đêm",
            "chủ quán bún đầu ngõ nghe hết chuyện phố",
            "nhân viên trông xe siêu thị",
        ),
        title_formulas=(
            "[Tình huống/nghề] + [hành động bất ngờ của tôi] — vd 'Tôi Làm Chủ Trọ, Mười Phòng Mười Drama'",
            "[Nghề] + [phát hiện bất ngờ] — vd 'Giặt Đồ Thuê, Tôi Tìm Thấy Sổ Đỏ Trong Túi Áo'",
        ),
        tone="hài 60% / phá án – lật kèo 40%",
        comment_question_style=(
            "Câu hỏi CHỌN PHE 2 lựa chọn đánh số về cách xử lý của nhân vật 'tôi' hoặc "
            "đoán thủ phạm. Dạng: 'Nếu là bạn, bạn có <X> không? 1 = <A>, 2 = <B>'."
        ),
        thumb_palette=("#CDEBFF", "#FF6B00", "#7A2FD0"),
        mascot_pose_hints=(
            "peeking from behind a door with wide curious eyes",
            "holding a magnifying glass with a cheeky grin",
            "gasping with both hands on cheeks",
        ),
        playlist_env="YOUTUBE_PLAYLIST_NGHE_LA",
        hashtags=("#nghela", "#honbien"),
    ),
    "bo_me_trong_sinh": Topic(
        id="bo_me_trong_sinh",
        name="Bố mẹ trọng sinh, không nhịn con bất hiếu",
        protagonist="mẹ hoặc bố 55–65 tuổi (hoặc mẹ chồng), ngôi 'tôi', từng hy sinh cả đời cho con",
        settings=(
            "trọng sinh về đúng ngày các con họp bàn chia nhà",
            "trọng sinh về lúc con trai định đưa tôi vào viện dưỡng lão",
            "trọng sinh về ngày con dâu đòi tôi đứng tên vay ngân hàng",
            "trọng sinh về lúc sắp bán ruộng lo đám cưới cho con",
            "trọng sinh về ngày con gái xin tiền mua nhà cho nhà chồng",
            "trọng sinh về ngày nghỉ hưu, sổ lương hưu bị con giữ",
            "trọng sinh về lúc bị gọi lên thành phố trông cháu không công",
            "trọng sinh về ngày chồng cũ và con cùng ép ký giấy từ bỏ tài sản",
            "trọng sinh về lúc con trai út đòi tiền làm ăn lần thứ năm",
            "trọng sinh về ngày mừng thọ 60, các con chỉ đến để chia vàng",
            "trọng sinh về lúc bị bắt bán nhà quê cho con trả nợ",
        ),
        title_formulas=(
            "Trọng Sinh + [tuổi/thời điểm], + [quyết định ngược] — vd 'Trọng Sinh Năm 60 Tuổi, Tôi Không Chia Nhà Nữa'",
            "[Con bất hiếu làm X], + [kiếp này tôi làm Y] — vd 'Con Đưa Tôi Vào Viện Dưỡng Lão, Kiếp Này Tôi Đi Du Lịch'",
        ),
        tone="ấm áp 50% / vả mặt 50%, kết có hậu (người mẹ/bố sống cho mình, con biết hối)",
        comment_question_style=(
            "Câu hỏi CHỌN PHE 2 lựa chọn đánh số về quyết định của người mẹ/bố. Dạng: "
            "'Nếu là bạn, bạn có <X> không? 1 = <A>, 2 = <B>'."
        ),
        thumb_palette=("#E6F5D0", "#D6336C", "#1C6DD0"),
        mascot_pose_hints=(
            "wearing sunglasses and holding a suitcase, carefree",
            "holding a land title booklet close to chest, determined",
            "sipping tea calmly with a knowing smile",
        ),
        playlist_env="YOUTUBE_PLAYLIST_BO_ME",
        hashtags=("#trongsinh", "#bomegia"),
        vietnam_only=False,
    ),
}

DEFAULT_ROTATION = (
    "ho_hang_viet",
    "nghe_la_hong_bien",
    "ho_hang_viet",
    "bo_me_trong_sinh",
    "nghe_la_hong_bien",
    "ho_hang_viet",
    "bo_me_trong_sinh",
)


class TopicError(Exception):
    pass


def get_topic(topic_id: str) -> Topic:
    try:
        return TOPICS[topic_id]
    except KeyError:
        raise TopicError(
            f"Không có chủ đề '{topic_id}'. Chủ đề hợp lệ: {', '.join(TOPICS)} hoặc 'auto'."
        ) from None


def parse_rotation(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return DEFAULT_ROTATION
    ids = tuple(part.strip() for part in raw.split(",") if part.strip())
    for topic_id in ids:
        get_topic(topic_id)
    if not ids:
        return DEFAULT_ROTATION
    return ids


def topic_for_date(day: date, rotation: tuple[str, ...] | None = None) -> str:
    """Chủ đề của một ngày: rotation[thứ trong tuần], thứ Hai = 0. Rotation ngắn
    hơn 7 thì lặp vòng (vd 3 phần tử = mỗi ngày một chủ đề xoay đều)."""
    rotation = rotation or parse_rotation(os.getenv("AUDIOBOOK_TOPIC_ROTATION"))
    return rotation[day.weekday() % len(rotation)]


def resolve_topic(value: str, day: date | None = None) -> Topic:
    if value == "auto":
        return get_topic(topic_for_date(day or date.today()))
    return get_topic(value)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(resolve_topic(argv[0]).id)
        return
    for topic in TOPICS.values():
        print(f"{topic.id:20} {topic.name}  [{topic.tone}]  playlist: ${topic.playlist_env}")


if __name__ == "__main__":
    main()
