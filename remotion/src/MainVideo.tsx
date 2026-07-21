import React from "react";
import { AbsoluteFill, Audio, staticFile } from "remotion";
import type { VideoProps } from "./types";

export const MainVideo: React.FC<VideoProps> = ({ audioPath }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
