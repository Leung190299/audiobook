import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { SceneBackground } from "./SceneBackground";
import { Waveform } from "./Waveform";
import { Caption } from "./Caption";
import { FONT_FAMILY, useBeVietnamPro } from "./fonts";

// Cảnh báo nội dung AI. Nói cả "hư cấu" lẫn "do AI tạo": truyện kể ngôi
// "tôi" về chuyện nhà rất đời thường, người xem dễ tin là có thật.
const AI_NOTICE = "Truyện hư cấu • Nội dung do AI tạo";

// Dissolve giữa hai cảnh. Dài hơn khoảng nghỉ 0,5s giữa chương (gap_seconds ở
// config/voice.yaml) là cố ý: ảnh tan dần qua ranh giới chương nhìn mềm hơn
// là cắt đúng lúc tiếng ngắt.
const CROSSFADE_SECONDS = 1.0;

export const MainVideo: React.FC<VideoProps> = ({
  audioPath,
  chapters,
  episodeLabel,
  hookText,
  coldOpenSeconds = 0,
  outroSeconds = 0,
  outroTitle,
  outroText,
}) => {
  useBeVietnamPro();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);
  const seconds = frame / fps;

  const currentChapter = chapters.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );
  const lastChapter = chapters[chapters.length - 1];
  const contentEnd = lastChapter ? lastChapter.endSeconds : 0;
  const inColdOpen = coldOpenSeconds > 0 && seconds < coldOpenSeconds;
  const inOutro = outroSeconds > 0 && seconds >= contentEnd;

  // Trải mọi cảnh của mọi chương thành một dãy, đánh số liên tục để chọn kiểu
  // chuyển động luân phiên trên toàn tập chứ không reset mỗi chương.
  const scenes = chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({ chapterIndex: chapter.index, scene }))
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {scenes.map(({ chapterIndex, scene }, i) => {
        // Lấy mốc bắt đầu của cảnh KẾ TIẾP làm endFrame, không phải endSeconds
        // của chính cảnh này: giữa hai chương có khoảng nghỉ tiếng 0,5s (scene
        // N kết thúc ở T, scene N+1 bắt đầu ở T+0,5), nên với endFrame cũ cả
        // hai lớp đều mờ nửa chừng quanh T+0,25 (~6% đen lộ ra). Giữ lớp trước
        // đục kín qua hết khoảng nghỉ đó; cảnh cuối cùng kéo qua cả card kết
        // (nếu có) để nền vẫn còn dưới card thay vì tắt đen.
        const next = scenes[i + 1];
        const endSeconds = next
          ? next.scene.startSeconds
          : scene.endSeconds + outroSeconds;
        return (
          <SceneBackground
            key={`${chapterIndex}-${scene.number}`}
            scene={scene}
            startFrame={Math.round(scene.startSeconds * fps)}
            endFrame={Math.round(endSeconds * fps)}
            crossfadeFrames={crossfadeFrames}
            motionIndex={i}
          />
        );
      })}
      {/* Vignette tĩnh: tối nhẹ bốn góc để ảnh có chiều sâu và chữ dễ đọc hơn. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)",
          pointerEvents: "none",
        }}
      />
      <Avatar />
      {audioPath ? <Waveform audioPath={audioPath} /> : null}
      {currentChapter && !inColdOpen ? (
        <div
          style={{
            position: "absolute",
            top: 190,
            left: 24,
            color: "#fff",
            fontStyle: "italic",
            fontSize: 20,
          }}
        >
          {currentChapter.heading}
        </div>
      ) : null}
      {episodeLabel ? (
        <div
          style={{
            position: "absolute",
            top: 20,
            right: 24,
            color: "#FFD84D",
            fontFamily: FONT_FAMILY,
            fontWeight: 900,
            fontSize: 26,
            letterSpacing: 2,
            textShadow: "0 3px 10px rgba(0,0,0,0.85)",
          }}
        >
          {episodeLabel}
        </div>
      ) : null}
      {inColdOpen && hookText ? (
        // Cold open: câu hook đè lên đoạn cao trào, người xem biết ngay truyện
        // này về cái gì trước khi vào chương 1.
        <div
          style={{
            position: "absolute",
            top: 230,
            left: "10%",
            right: "10%",
            textAlign: "center",
            color: "#FFD84D",
            fontFamily: FONT_FAMILY,
            fontWeight: 900,
            fontSize: 44,
            lineHeight: 1.15,
            textShadow: "0 4px 14px rgba(0,0,0,0.9)",
          }}
        >
          {hookText}
        </div>
      ) : null}
      {inColdOpen ? (
        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: 0,
            right: 0,
            textAlign: "center",
            color: "rgba(255,255,255,0.82)",
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 22,
            textShadow: "0 2px 8px rgba(0,0,0,0.9)",
          }}
        >
          {AI_NOTICE}
        </div>
      ) : null}
      {!inOutro ? <Caption chapters={chapters} /> : null}
      {inOutro ? (
        <AbsoluteFill
          style={{
            backgroundColor: "rgba(0,0,0,0.85)",
            justifyContent: "center",
            alignItems: "center",
            padding: 60,
            gap: 28,
          }}
        >
          <div
            style={{
              color: "#fff",
              fontFamily: FONT_FAMILY,
              fontWeight: 900,
              fontSize: 40,
              lineHeight: 1.2,
              textAlign: "center",
            }}
          >
            {outroTitle}
          </div>
          {(outroText ?? "").split("\n").map((line, i) => (
            <div
              key={i}
              style={{
                color: i === 0 && (outroText ?? "").includes("\n") ? "#fff" : "#FFD84D",
                fontFamily: FONT_FAMILY,
                fontWeight: 700,
                fontSize: 30,
                lineHeight: 1.3,
                textAlign: "center",
              }}
            >
              {line}
            </div>
          ))}
          <div
            style={{
              color: "rgba(255,255,255,0.75)",
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 24,
              textAlign: "center",
              marginTop: 8,
            }}
          >
            {AI_NOTICE}
          </div>
        </AbsoluteFill>
      ) : null}
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
