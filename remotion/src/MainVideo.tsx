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
      {scenes.map(({ chapterIndex, scene }, i) => {
        // Lấy mốc bắt đầu của cảnh KẾ TIẾP làm endFrame, không phải endSeconds
        // của chính cảnh này: giữa hai chương có khoảng nghỉ tiếng 0,5s (scene
        // N kết thúc ở T, scene N+1 bắt đầu ở T+0,5), nên với endFrame cũ cả
        // hai lớp đều mờ nửa chừng quanh T+0,25 (~6% đen lộ ra). Giữ lớp trước
        // đục kín qua hết khoảng nghỉ đó; cảnh cuối cùng của tập không có cảnh
        // kế tiếp nên vẫn dùng endSeconds của chính nó. Kéo dài pan/zoom thêm
        // 0,5s trên một cảnh ~50s là không nhận ra bằng mắt.
        const next = scenes[i + 1];
        const endSeconds = next ? next.scene.startSeconds : scene.endSeconds;
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
