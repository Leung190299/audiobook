import React from "react";
import { Img, staticFile, useVideoConfig } from "remotion";
import { FONT_FAMILY } from "./fonts";

// Bảng màu lấy từ logo kênh (remotion/public/avatar.png): nền kem ấm, chữ nâu
// đậm như viền logo, điểm nhấn san hô như dải ruy băng "TRUYỆN".
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

const DEFAULT_CHANNEL = "Audio Truyện";

// Linh vật kênh, tách nền trong suốt (scripts/cutout_sticker.py). Trên + dưới
// mỗi tấm như format tham khảo; tư thế khác nhau để hai tấm không giống hệt.
const MASCOT = {
  left: { top: "remotion/public/mascot-wave.png", bottom: "remotion/public/mascot-cool.png" },
  right: { top: "remotion/public/mascot-read.png", bottom: "remotion/public/mascot-cool.png" },
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
  channelName?: string; // CHANNEL_NAME trong .env
}

// Một tấm nền thương hiệu hai bên video giữa. Bố cục mỗi tấm: linh vật trên,
// thẻ chữ giữa, linh vật dưới. Trái mời đăng ký, phải nhắc tên kênh và cảnh báo
// nội dung AI -- mỗi bên một việc để người xem không đọc trùng.
//
// Mọi kích thước tỉ lệ theo bề rộng tấm: tấm rộng 174px (video ngang) hay
// 350px (video dọc) đều cân, không bên nào trống trơn hay chật chữ.
export const BrandPanel: React.FC<BrandPanelProps> = ({ side, width, channelName }) => {
  const { height } = useVideoConfig();
  // Các mốc chặn dưới đo trên khung 576px; nhân theo tỉ lệ khung để lên 1080p
  // bố cục y hệt chứ không ra chữ bé tí giữa tấm nền to.
  const k = height / 576;
  // Co theo CẢ chiều cao, không chỉ bề rộng: tấm bên video dọc rộng 350px,
  // co theo bề rộng thì linh vật 210px + 164px cộng tên kênh và thẻ chữ vượt
  // 576px -- ếch kính râm góc dưới bên phải bị cắt mất nửa người.
  const mascot = clamp(Math.min(width * 0.62, height * 0.3), 90 * k, 210 * k);
  const font = clamp(width * 0.075, 12 * k, 22 * k);
  const nameFont = clamp(width * 0.115, 18 * k, 36 * k);
  const [head, ...rest] = (channelName || DEFAULT_CHANNEL).trim().split(/\s+/);
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
      {side === "left" ? (
        <Card tone="accent" font={font} k={k}>
          Đăng ký kênh
          <br />
          truyện mới 20h mỗi tối
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: font * 0.7, width: "100%" }}>
          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 900,
              fontSize: nameFont,
              lineHeight: 1.05,
              color: BRAND.ink,
              textAlign: "center",
            }}
          >
            {head}
            {rest.length ? (
              <>
                <br />
                <span style={{ color: BRAND.accent }}>{rest.join(" ")}</span>
              </>
            ) : null}
          </div>
          <Card font={font} k={k}>
            <div style={{ color: BRAND.accent, fontSize: font * 1.08 }}>{AI_NOTICE_HEAD}</div>
            {AI_NOTICE_BODY}
          </Card>
        </div>
      )}
      <Img
        src={staticFile(art.bottom)}
        style={{ width: mascot * 0.78, height: mascot * 0.78, objectFit: "contain" }}
      />
    </div>
  );
};
