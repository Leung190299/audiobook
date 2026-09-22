import { useEffect, useState } from "react";
import { continueRender, delayRender, staticFile } from "remotion";

export const FONT_FAMILY = "BeVietnamPro, sans-serif";

// Font đóng gói trong repo, nạp qua FontFace API. Phải chặn render bằng
// delayRender cho tới khi font sẵn sàng, nếu không khung hình đầu sẽ render
// bằng font dự phòng rồi mới đổi giữa chừng. Dùng chung cho video dài, tập và
// short -- trước 22/09 chỉ ShortVideo/ShortThumbnail có hook này.
export const useBeVietnamPro = () => {
  const [handle] = useState(() => delayRender("Đang nạp font Be Vietnam Pro"));

  useEffect(() => {
    const font = new FontFace(
      "BeVietnamPro",
      `url(${staticFile("assets/fonts/BeVietnamPro-Black.ttf")}) format("truetype")`
    );
    font
      .load()
      .then((loaded) => {
        document.fonts.add(loaded);
        continueRender(handle);
      })
      .catch(() => {
        // Thiếu font thì vẫn render bằng sans-serif, không làm hỏng cả lượt chạy.
        continueRender(handle);
      });
  }, [handle]);
};
