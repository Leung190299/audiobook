import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { SceneBackground } from "./SceneBackground";
import { Waveform } from "./Waveform";
import { Caption } from "./Caption";

// Dissolve giữa hai cảnh. Dài hơn khoảng nghỉ 0,5s giữa chương (gap_seconds ở
// config/voice.yaml) là cố ý: ảnh tan dần qua ranh giới chương nhìn mềm hơn
// là cắt đúng lúc tiếng ngắt.
const CROSSFADE_SECONDS = 1.0;

export const MainVideo: React.FC<VideoProps> = ({ audioPath, chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);
  const seconds = frame / fps;

  const currentChapter = chapters.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );

  // Trải mọi cảnh của mọi chương thành một dãy, đánh số liên tục để chọn kiểu
  // chuyển động luân phiên trên toàn tập chứ không reset mỗi chương.
  const scenes = chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({ chapterIndex: chapter.index, scene }))
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {scenes.map(({ chapterIndex, scene }, i) => (
        <SceneBackground
          key={`${chapterIndex}-${scene.number}`}
          scene={scene}
          startFrame={Math.round(scene.startSeconds * fps)}
          endFrame={Math.round(scene.endSeconds * fps)}
          crossfadeFrames={crossfadeFrames}
          motionIndex={i}
        />
      ))}
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
      {currentChapter ? (
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
      <Caption chapters={chapters} />
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
