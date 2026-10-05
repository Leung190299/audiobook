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
// 1920x1080 từ 05/10 (trước là 1024x576). Nguồn Douyin cao 1024-1280px, khung
// 576px vứt đi hơn nửa chi tiết dọc của video giữa; YouTube cũng cấp codec tốt
// hơn (VP9/AV1) cho bản tải lên từ 1080p. Render chậm hơn ~33% (đo 05/10: 8s
// so với 6s cho 10s video), bù lại đã bỏ ~30 phút sinh ảnh ở stage 3.
const WIDTH = 1920;
const HEIGHT = 1080;

const SHORT_WIDTH = 1080;
const SHORT_HEIGHT = 1920;

const calculateMetadata = async ({ props }: { props: VideoProps }) => {
  const lastChapter = props.chapters[props.chapters.length - 1];
  // Tập (episodes/) có thêm card kết sau khi hết chương; bản full không có.
  const durationInSeconds =
    (lastChapter ? lastChapter.endSeconds : 0) + (props.outroSeconds ?? 0);
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
