import React from "react";
import { AbsoluteFill, Audio, staticFile, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { ChapterBackground } from "./ChapterBackground";

const CROSSFADE_SECONDS = 0.5;

export const MainVideo: React.FC<VideoProps> = ({ audioPath, chapters }) => {
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {chapters.map((chapter, i) => (
        <ChapterBackground
          key={chapter.index}
          chapter={chapter}
          startFrame={Math.round(chapter.startSeconds * fps)}
          endFrame={Math.round(chapter.endSeconds * fps)}
          crossfadeFrames={crossfadeFrames}
          panDirection={i % 2 === 0 ? "in" : "out"}
        />
      ))}
      <Avatar />
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
