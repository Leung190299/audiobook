import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, staticFile, useVideoConfig } from "remotion";

interface BackgroundVideoProps {
  src: string; // đường dẫn tương đối repo, đã tiền xử lý về cao 576px (episodes/backgrounds.py)
  seconds: number; // thời lượng video nguồn, để biết khi nào quay lại đầu
}

// Video nền lặp suốt tập, nằm trong ô giữa của BrandedLayout. Không phủ tối:
// khung hình không còn phụ đề để phải dìm nền cho dễ đọc.
// Nguồn ngắn (5-16 phút) hơn hẳn một tập (~45 phút)
// nên phải lặp. Tiếng đã bỏ ở bước tiền xử lý; `muted` ở đây chỉ để chắc chắn.
export const BackgroundVideo: React.FC<BackgroundVideoProps> = ({ src, seconds }) => {
  const { fps } = useVideoConfig();
  // Loop đòi tối thiểu 1 khung; thời lượng 0 đã bị chặn ở Python nhưng giữ cho
  // chắc kẻo props viết tay làm vỡ cả lượt render.
  const loopFrames = Math.max(1, Math.round(seconds * fps));
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Loop durationInFrames={loopFrames}>
        <OffthreadVideo
          src={staticFile(src)}
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </Loop>
    </AbsoluteFill>
  );
};
