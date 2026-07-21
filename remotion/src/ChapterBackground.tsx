import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import type { ChapterProps } from "./types";

interface ChapterBackgroundProps {
  chapter: ChapterProps;
  startFrame: number;
  endFrame: number;
  crossfadeFrames: number;
  panDirection: "in" | "out";
}

export const ChapterBackground: React.FC<ChapterBackgroundProps> = ({
  chapter,
  startFrame,
  endFrame,
  crossfadeFrames,
  panDirection,
}) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(
    frame,
    [startFrame - crossfadeFrames, startFrame, endFrame, endFrame + crossfadeFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const scale = interpolate(
    frame,
    [startFrame, endFrame],
    panDirection === "in" ? [1, 1.15] : [1.15, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <Img
        src={staticFile(chapter.imagePath)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
