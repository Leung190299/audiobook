import React from "react";
import {
  AbsoluteFill,
  Audio,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SceneBackground } from "./SceneBackground";
import type { ShortProps } from "./types";
import { FONT_FAMILY, useBeVietnamPro } from "./fonts";

// Hook chỉ hiện ở đầu video — sau đó nhường chỗ cho phụ đề.
const HOOK_SECONDS = 3;
// Dissolve giữa hai cảnh, cùng giá trị với MainVideo.tsx.
const CROSSFADE_SECONDS = 1.0;


export const ShortVideo: React.FC<ShortProps> = ({
  title,
  audioPath,
  scenes,
  hookText,
  captions,
  audioDurationSeconds,
  ctaText,
}) => {
  useBeVietnamPro();

  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const seconds = frame / fps;
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);

  const inCta = seconds >= audioDurationSeconds;
  // Giữ nguyên phụ đề của câu trước trong khoảng nghỉ 0.15s giữa hai câu (xem
  // sentence_gap_seconds ở config/voice.yaml) thay vì tắt hẳn: dùng "startSeconds gần
  // nhất đã qua" chứ không so cả startSeconds lẫn endSeconds, nếu không chữ sẽ
  // chớp tắt khoảng chục lần mỗi short. inCta ở trên đã lo việc ẩn phụ đề khi
  // sang card CTA.
  const activeCaption = [...captions]
    .reverse()
    .find((c) => seconds >= c.startSeconds);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {scenes.map((scene, i) => {
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
            {ctaText}
          </div>
        </AbsoluteFill>
      ) : null}

      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
