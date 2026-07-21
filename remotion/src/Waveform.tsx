import React from "react";
import { staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";

interface WaveformProps {
  audioPath: string;
}

// @remotion/media-utils's visualizeAudio requires numberOfSamples such that
// numberOfSamples * 2 is a power of two, or it throws
// `TypeError: The argument "bars" must be a power of two.` (verified in
// node_modules/@remotion/media-utils/dist/esm/index.mjs getVisualization()).
// 8 is the smallest value that satisfies this while keeping a compact bar count.
const BAR_COUNT = 8;

export const Waveform: React.FC<WaveformProps> = ({ audioPath }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const audioData = useAudioData(staticFile(audioPath));

  if (!audioData) {
    return null;
  }

  const amplitudes = visualizeAudio({
    fps,
    frame,
    audioData,
    numberOfSamples: BAR_COUNT,
  });

  return (
    <div style={{ position: "absolute", top: 130, left: 24, display: "flex", gap: 4 }}>
      {amplitudes.map((amplitude, i) => (
        <div
          key={i}
          style={{
            width: 6,
            height: Math.max(4, amplitude * 40),
            backgroundColor: "#fff",
            borderRadius: 3,
          }}
        />
      ))}
    </div>
  );
};
