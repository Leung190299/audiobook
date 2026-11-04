import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, staticFile } from "remotion";
import type { ShortProps } from "./types";
import { FONT_FAMILY, useBeVietnamPro } from "./fonts";

// Composition ảnh tĩnh cho ảnh bìa của từng phần short. YouTube Shorts tự lấy
// khung hình trong video làm ảnh bìa, không nhận ảnh tải lên -- ảnh này phục
// vụ việc chọn khung thủ công, đăng chéo sang nền tảng khác, và trường hợp một
// phần bị xếp thành video thường (xem shorts/cli.py).
export const ShortThumbnail: React.FC<ShortProps> = ({
  title,
  imagePath,
  hookText,
  partLabel,
  backgroundVideo,
}) => {
  useBeVietnamPro();

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {/* Ảnh tĩnh: không zoom, animation vô nghĩa vì chỉ có một khung hình.
            Có video nền (đã bỏ stage 3, không còn ảnh) thì chụp khung đầu của
            chính video đó. */}
        {backgroundVideo ? (
          <OffthreadVideo
            src={staticFile(backgroundVideo)}
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <Img
            src={staticFile(imagePath)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        )}
      </AbsoluteFill>

      {/* Gradient đậm hơn ShortVideo.tsx: ảnh bìa phải đọc được chữ khi thu nhỏ
          bằng ngón tay cái trong danh sách feed, không có lợi thế "xem vài
          giây" như video. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.25) 28%, rgba(0,0,0,0.35) 62%, rgba(0,0,0,0.92) 100%)",
        }}
      />

      {/* partLabel: thứ đầu tiên người xem cần thấy để biết mình đang ở phần
          mấy của series -- đặt trên cùng, chữ lớn, tương phản mạnh. */}
      <div
        style={{
          position: "absolute",
          top: 90,
          left: 60,
          right: 60,
          textAlign: "center",
          color: "#FFD84D",
          fontFamily: FONT_FAMILY,
          fontSize: 76,
          lineHeight: 1.1,
          letterSpacing: 2,
          textShadow: "0 6px 18px rgba(0,0,0,0.85)",
        }}
      >
        {partLabel}
      </div>

      {/* hookText: tiêu đề chương, điểm nhấn chính giữa ảnh. */}
      <div
        style={{
          position: "absolute",
          top: 780,
          left: 60,
          right: 60,
          textAlign: "center",
          color: "#fff",
          fontFamily: FONT_FAMILY,
          fontSize: 92,
          lineHeight: 1.2,
          textShadow: "0 6px 18px rgba(0,0,0,0.85)",
        }}
      >
        {hookText}
      </div>

      {/* title: tên tập, cỡ nhỏ ở đáy, một dòng, cắt bớt nếu tràn -- chỉ để
          tham khảo, không phải điểm nhấn của ảnh bìa. */}
      <div
        style={{
          position: "absolute",
          bottom: 70,
          left: 60,
          right: 60,
          textAlign: "center",
          color: "rgba(255,255,255,0.85)",
          fontFamily: FONT_FAMILY,
          fontSize: 40,
          lineHeight: 1.2,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {title}
      </div>
    </AbsoluteFill>
  );
};
