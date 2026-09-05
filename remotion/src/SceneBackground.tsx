import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import type { SceneProps } from "./types";

// Bốn kiểu chuyển động luân phiên theo thứ tự cảnh trên toàn tập, để hai cảnh
// liền nhau không bao giờ lặp cùng một hướng.
const MOTIONS = [
  { scale: [1.06, 1.16], panX: [-2.5, 2.5] },
  { scale: [1.16, 1.06], panX: [2.5, -2.5] },
  { scale: [1.06, 1.16], panX: [2.5, -2.5] },
  { scale: [1.16, 1.06], panX: [-2.5, 2.5] },
] as const;

interface SceneBackgroundProps {
  scene: SceneProps;
  startFrame: number;
  endFrame: number;
  crossfadeFrames: number;
  motionIndex: number; // thứ tự cảnh toàn tập, chọn kiểu trong MOTIONS
}

export const SceneBackground: React.FC<SceneBackgroundProps> = ({
  scene,
  startFrame,
  endFrame,
  crossfadeFrames,
  motionIndex,
}) => {
  const frame = useCurrentFrame();
  const motion = MOTIONS[motionIndex % MOTIONS.length];

  // Hiện dần TRƯỚC startFrame và mờ dần SAU endFrame: cảnh sau nằm trên cảnh
  // trước (thứ tự map trong MainVideo) nên đoạn hiện dần chính là dissolve.
  const opacity = interpolate(
    frame,
    [startFrame - crossfadeFrames, startFrame, endFrame, endFrame + crossfadeFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Scale tối thiểu 1,06 để pan ±2,5% không bao giờ lộ mép đen.
  const scale = interpolate(frame, [startFrame, endFrame], [...motion.scale], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const panX = interpolate(frame, [startFrame, endFrame], [...motion.panX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      <Img
        src={staticFile(scene.imagePath)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translateX(${panX}%) scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
