# images/style.py
#
# Đuôi prompt gắn sau mô tả cảnh, gửi cho FLUX.2-klein 4 bước. Hai điều đã đo được
# trên ảnh thật (tập 04/09) quyết định cách viết ở đây:
#
# - FLUX không có negative prompt, nên "no human faces in close-up" gần như vô hiệu:
#   chương 8 ra ~40 gương mặt nhỏ méo mó. Cách chống duy nhất là TẢ cảnh trống
#   ("empty scene") như một đặc điểm dương tính, rồi mới nhắc "no people" phụ thêm.
# - 4 bước là quá ít để vẽ chi tiết nhỏ (mặt, chữ, tay); nhưng đủ cho ánh sáng, chất
#   liệu và bố cục rộng. Nên đẩy sức mạnh của prompt vào ba thứ đó.
STYLE_SUFFIX = (
    "empty scene with no people, detailed watercolor illustration, soft painterly "
    "texture, warm pastel palette with gentle deep shadows, atmospheric volumetric "
    "light, wide establishing shot, cinematic composition, rich environmental detail, "
    "no text, no logos, no words, no people, no faces"
)
