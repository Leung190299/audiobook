import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { BrandPanel } from "./BrandPanel";

// Bố cục kiểu "video thủ công ở giữa, hai tấm thương hiệu hai bên" (tham khảo
// format các kênh truyện audio đang chạy tốt, 05/10/2026). Khung hình tĩnh từ
// đầu tới cuối: không phụ đề, không tên chương, không sóng âm -- để video giữa
// tự giữ mắt người xem.

// Ô giữa rộng tối đa 66% bề ngang (như format tham khảo). Video ngang bị chặn ở
// đây và cắt bớt hai mép.
const MAX_CENTER_RATIO = 0.66;
// Hẹp nhất bằng video dọc 9:16 vừa khít chiều cao, để tấm bên không phình quá
// nửa khung.
const MIN_CENTER_RATIO = 9 / 16;

// Bề rộng ô giữa theo khổ video nguồn. Video dọc (phần lớn video Douyin) hiện
// trọn vẹn không cắt, hai tấm bên rộng ra; ép khổ dọc vào ô gần vuông như
// format tham khảo là cắt mất nửa hình.
export const centerWidthFor = (aspect: number | undefined, width: number, height: number): number => {
  const a = aspect && aspect > 0 ? aspect : 16 / 9;
  const lo = Math.round(height * MIN_CENTER_RATIO);
  const hi = Math.round(width * MAX_CENTER_RATIO);
  const w = Math.min(hi, Math.max(lo, Math.round(height * a)));
  return w - (w % 2); // chẵn cho hai tấm bên chia đều từng điểm ảnh
};

interface BrandedLayoutProps {
  aspect?: number; // rộng/cao của nội dung giữa; thiếu thì coi như 16:9
  channelName?: string;
  children: React.ReactNode; // nội dung ô giữa: video nền hoặc dãy ảnh cảnh
}

export const BrandedLayout: React.FC<BrandedLayoutProps> = ({ aspect, channelName, children }) => {
  const { width, height } = useVideoConfig();
  const center = centerWidthFor(aspect, width, height);
  const side = (width - center) / 2;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: side,
          width: center,
          overflow: "hidden",
        }}
      >
        {children}
      </div>
      <BrandPanel side="left" width={side} channelName={channelName} />
      <BrandPanel side="right" width={side} channelName={channelName} />
    </AbsoluteFill>
  );
};
