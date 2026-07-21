import React from "react";
import { Composition } from "remotion";
import type { AnyZodObject } from "remotion";
import { MainVideo } from "./MainVideo";
import type { VideoProps } from "./types";

// Composition's generic constraint requires an indexable Props type; VideoProps
// itself has no index signature, so widen it just for the generic argument.
type CompositionVideoProps = VideoProps & Record<string, unknown>;

const FPS = 30;
const WIDTH = 1024;
const HEIGHT = 576;

const calculateMetadata = async ({ props }: { props: VideoProps }) => {
  const lastChapter = props.chapters[props.chapters.length - 1];
  const durationInSeconds = lastChapter ? lastChapter.endSeconds : 0;
  return {
    durationInFrames: Math.max(1, Math.round(durationInSeconds * FPS)),
  };
};

const defaultProps: CompositionVideoProps = {
  trope: "",
  title: "",
  audioPath: "",
  sampleRate: 24000,
  chapters: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition<AnyZodObject, CompositionVideoProps>
      id="MainVideo"
      component={MainVideo}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      durationInFrames={1}
      calculateMetadata={calculateMetadata}
      defaultProps={defaultProps}
    />
  );
};
