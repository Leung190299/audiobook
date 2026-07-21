import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { Avatar } from "./Avatar";
import { ChapterBackground } from "./ChapterBackground";
import { Waveform } from "./Waveform";
import { Caption } from "./Caption";

// Must match gap_seconds in config/voice.yaml; audio chapter gaps depend on this.
const CROSSFADE_SECONDS = 0.5;

export const MainVideo: React.FC<VideoProps> = ({ audioPath, chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);
  const seconds = frame / fps;

  const currentChapter = chapters.find(
    (c) => seconds >= c.startSeconds && seconds < c.endSeconds
  );

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
