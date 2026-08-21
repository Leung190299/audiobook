import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { ShortProps } from "./types";

// Hook chỉ hiện ở đầu video — sau đó nhường chỗ cho phụ đề.
const HOOK_SECONDS = 3;
const FONT_FAMILY = "BeVietnamPro, sans-serif";

// Font đóng gói trong repo, nạp qua FontFace API. Phải chặn render bằng
// delayRender cho tới khi font sẵn sàng, nếu không khung hình đầu sẽ render
// bằng font dự phòng rồi mới đổi giữa chừng.
const useBeVietnamPro = () => {
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

export const ShortVideo: React.FC<ShortProps> = ({
  title,
  audioPath,
  imagePath,
  hookText,
  captions,
  audioDurationSeconds,
}) => {
  useBeVietnamPro();

  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const seconds = frame / fps;

  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.08], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const inCta = seconds >= audioDurationSeconds;
  const activeCaption = captions.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={staticFile(imagePath)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${zoom})`,
          }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.15) 30%, rgba(0,0,0,0.25) 60%, rgba(0,0,0,0.9) 100%)",
        }}
      />

      {!inCta && seconds < HOOK_SECONDS ? (
        <div
          style={{
            position: "absolute",
            top: 160,
            left: 60,
            right: 60,
            textAlign: "center",
            color: "#FFD84D",
            fontFamily: FONT_FAMILY,
            fontSize: 84,
            lineHeight: 1.15,
            textShadow: "0 6px 18px rgba(0,0,0,0.85)",
          }}
        >
          {hookText}
        </div>
      ) : null}

      {!inCta && activeCaption ? (
        <div
          style={{
            position: "absolute",
            bottom: 320,
            left: 60,
            right: 60,
            textAlign: "center",
            color: "#fff",
            fontFamily: FONT_FAMILY,
            fontSize: 62,
            lineHeight: 1.25,
            padding: "24px 28px",
            backgroundColor: "rgba(0,0,0,0.55)",
            borderRadius: 24,
          }}
        >
          {activeCaption.text}
        </div>
      ) : null}

      {inCta ? (
        <AbsoluteFill
          style={{
            backgroundColor: "rgba(0,0,0,0.88)",
            justifyContent: "center",
            alignItems: "center",
            padding: 80,
            gap: 48,
          }}
        >
          <div
            style={{
              color: "#fff",
              fontFamily: FONT_FAMILY,
              fontSize: 72,
              lineHeight: 1.2,
              textAlign: "center",
            }}
          >
            {title}
          </div>
          <div
            style={{
              color: "#FFD84D",
              fontFamily: FONT_FAMILY,
              fontSize: 64,
              textAlign: "center",
            }}
          >
            Nghe full trên kênh
          </div>
        </AbsoluteFill>
      ) : null}

      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
