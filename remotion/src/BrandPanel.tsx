import React from "react";
import { Img, staticFile, useVideoConfig } from "remotion";
import { FONT_FAMILY } from "./fonts";

// Bảng màu ấm hợp với bộ sticker ếch nón lá: nền kem, chữ nâu đậm như nét viền
// sticker, điểm nhấn san hô.
export const BRAND = {
  panel: "#F8E6D2",
  card: "#FFFAF3",
  ink: "#4A2C1A",
  accent: "#D9705C",
} as const;

// Cảnh báo nội dung AI nằm cố định trên khung hình suốt tập. Nói cả "hư cấu"
// lẫn "do AI tạo": truyện kể ngôi "tôi" về chuyện nhà rất đời thường, người
// nghe dễ tin là có thật. Để chữ tự xuống dòng: ngắt cứng từng dòng thì ở tấm
// hẹp (video ngang) vỡ thành "giọng / đọc / ... do AI / tạo".
export const AI_NOTICE_HEAD = "Truyện hư cấu";
export const AI_NOTICE_BODY = "Nội dung, giọng đọc và hình ảnh do AI tạo";

// Sticker linh vật của kênh, cắt từ bảng sticker (scripts/cut_sticker_sheet.py).
// Trái lo việc mời đăng ký: biển "Đừng quên đăng ký nhé!" + "Like nhé!". Phải
// lo nhận diện: logo "AUDIO TRUYỆN" (có sẵn tên kênh, nên không viết tên kênh
// bằng chữ nữa) + ếch đeo tai nghe đọc truyện.
const MASCOT = {
  left: { top: "remotion/public/sticker-dang-ky.png", bottom: "remotion/public/sticker-like.png" },
  right: { top: "remotion/public/sticker-logo.png", bottom: "remotion/public/sticker-nghe-truyen.png" },
} as const;

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

const Card: React.FC<{
  children: React.ReactNode;
  tone?: "card" | "accent";
  font: number;
  k: number;
}> = ({ children, tone = "card", font, k }) => (
  <div
    style={{
      backgroundColor: tone === "accent" ? BRAND.accent : BRAND.card,
      color: tone === "accent" ? BRAND.card : BRAND.ink,
      border: `${2 * k}px solid ${BRAND.ink}`,
      borderRadius: font * 0.8,
      padding: `${font * 0.55}px ${font * 0.65}px`,
      fontFamily: FONT_FAMILY,
      fontWeight: 800,
      fontSize: font,
      lineHeight: 1.25,
      textAlign: "center",
      width: "84%",
      boxShadow: `0 ${3 * k}px 0 ${BRAND.ink}`,
    }}
  >
    {children}
  </div>
);

interface BrandPanelProps {
  side: "left" | "right";
  width: number;
}

// Một tấm nền thương hiệu hai bên video giữa. Bố cục mỗi tấm: sticker trên,
// thẻ chữ giữa, sticker dưới. Trái mời đăng ký, phải là logo kênh và cảnh báo
// nội dung AI -- mỗi bên một việc để người xem không đọc trùng.
//
// Mọi kích thước tỉ lệ theo bề rộng tấm: tấm rộng 174px (video ngang) hay
// 350px (video dọc) đều cân, không bên nào trống trơn hay chật chữ.
export const BrandPanel: React.FC<BrandPanelProps> = ({ side, width }) => {
  const { height } = useVideoConfig();
  // Các mốc chặn dưới đo trên khung 576px; nhân theo tỉ lệ khung để lên 1080p
  // bố cục y hệt chứ không ra chữ bé tí giữa tấm nền to.
  const k = height / 576;
  // Co theo CẢ chiều cao, không chỉ bề rộng: tấm bên video dọc rộng ~650px ở
  // 1080p, co theo bề rộng thì hai sticker cộng thẻ chữ vượt chiều cao khung và
  // sticker dưới bị cắt mất nửa.
  const mascot = clamp(Math.min(width * 0.82, height * 0.34), 90 * k, 210 * k);
  const font = clamp(width * 0.075, 12 * k, 22 * k);
  const art = MASCOT[side];

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        bottom: 0,
        [side]: 0,
        width,
        backgroundColor: BRAND.panel,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-evenly",
        padding: `${font}px 0`,
      }}
    >
      <Img src={staticFile(art.top)} style={{ width: mascot, height: mascot, objectFit: "contain" }} />
      <Card tone={side === "left" ? "accent" : "card"} font={font} k={k}>
        {side === "left" ? (
          <>
            Truyện mới
            <br />
            20h mỗi tối
          </>
        ) : (
          <>
            <div style={{ color: BRAND.accent, fontSize: font * 1.08 }}>{AI_NOTICE_HEAD}</div>
            {AI_NOTICE_BODY}
          </>
        )}
      </Card>
      <Img
        src={staticFile(art.bottom)}
        style={{ width: mascot * 0.9, height: mascot * 0.9, objectFit: "contain" }}
      />
    </div>
  );
};
