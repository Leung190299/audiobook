import React from "react";
import {
  AbsoluteFill,
  Audio,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BackgroundVideo } from "./BackgroundVideo";
import { SceneBackground } from "./SceneBackground";
import type { ShortProps } from "./types";
import { FONT_FAMILY, useBeVietnamPro } from "./fonts";

// Hook chỉ hiện ở đầu video. Từ 08/11 Short KHÔNG burn phụ đề nữa (như video
// dài): người xem bật phụ đề tự động của YouTube/TikTok; props.captions vẫn được
// stage 7 gửi lên (shorts/props_builder.py) nhưng không vẽ.
const HOOK_SECONDS = 3;
// Dissolve giữa hai cảnh, cùng giá trị với MainVideo.tsx.
const CROSSFADE_SECONDS = 1.0;


export const ShortVideo: React.FC<ShortProps> = ({
  title,
  audioPath,
  scenes,
  hookText,
  audioDurationSeconds,
  ctaText,
  backgroundVideo,
  backgroundVideoSeconds = 0,
}) => {
  useBeVietnamPro();

  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const seconds = frame / fps;
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);

  const inCta = seconds >= audioDurationSeconds;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {/* Video nền phủ kín khung dọc 1080x1920 (ưu tiên video dọc, vừa
            khít). Không có thì dựng bằng dãy ảnh cảnh của stage 3 như cũ. */}
        {backgroundVideo ? (
          <BackgroundVideo src={backgroundVideo} seconds={backgroundVideoSeconds} />
        ) : null}
        {backgroundVideo ? null : scenes.map((scene, i) => {
          const next = scenes[i + 1];
          // Cảnh cuối kéo dài hết composition: nền vẫn còn dưới card CTA thay
          // vì tắt đen đúng lúc audio hết. Mốc cảnh đã quy về gốc phần.
          const endFrame = next
            ? Math.round(next.startSeconds * fps)
            : durationInFrames;
          return (
            <SceneBackground
              key={scene.number}
              scene={scene}
              startFrame={Math.round(scene.startSeconds * fps)}
              endFrame={endFrame}
              crossfadeFrames={crossfadeFrames}
              motionIndex={i}
            />
          );
        })}
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
            {ctaText}
          </div>
        </AbsoluteFill>
      ) : null}

      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
