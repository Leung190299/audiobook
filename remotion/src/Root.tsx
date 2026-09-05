import React from "react";
import { Composition } from "remotion";
import type { AnyZodObject } from "remotion";
import { MainVideo } from "./MainVideo";
import { ShortThumbnail } from "./ShortThumbnail";
import { ShortVideo } from "./ShortVideo";
import type { ShortProps, VideoProps } from "./types";

// Composition's generic constraint requires an indexable Props type; VideoProps
// itself has no index signature, so widen it just for the generic argument.
type CompositionVideoProps = VideoProps & Record<string, unknown>;
type CompositionShortProps = ShortProps & Record<string, unknown>;

const FPS = 30;
const WIDTH = 1024;
const HEIGHT = 576;

const SHORT_WIDTH = 1080;
const SHORT_HEIGHT = 1920;

const calculateMetadata = async ({ props }: { props: VideoProps }) => {
  const lastChapter = props.chapters[props.chapters.length - 1];
  const durationInSeconds = lastChapter ? lastChapter.endSeconds : 0;
  return {
    durationInFrames: Math.max(1, Math.round(durationInSeconds * FPS)),
  };
};

const calculateShortMetadata = async ({ props }: { props: ShortProps }) => {
  const durationInSeconds = props.audioDurationSeconds + props.ctaSeconds;
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

const defaultShortProps: CompositionShortProps = {
  trope: "",
  title: "",
  audioPath: "",
  imagePath: "",
  scenes: [],
  hookText: "",
  partLabel: "",
  captions: [],
  audioDurationSeconds: 0,
  ctaSeconds: 4,
  ctaText: "",
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
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
      <Composition<AnyZodObject, CompositionShortProps>
        id="ShortVideo"
        component={ShortVideo}
        fps={FPS}
        width={SHORT_WIDTH}
        height={SHORT_HEIGHT}
        durationInFrames={1}
        calculateMetadata={calculateShortMetadata}
        defaultProps={defaultShortProps}
      />
      <Composition<AnyZodObject, CompositionShortProps>
        id="ShortThumbnail"
        component={ShortThumbnail}
        fps={FPS}
        width={SHORT_WIDTH}
        height={SHORT_HEIGHT}
        durationInFrames={1}
        defaultProps={defaultShortProps}
      />
    </>
  );
};
