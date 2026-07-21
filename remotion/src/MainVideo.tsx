import React from "react";
import { AbsoluteFill, Audio } from "remotion";
import type { VideoProps } from "./types";

// Remotion loads the composition inside a locally served page; any `src` that
// isn't already a URL is resolved relative to that server's origin, which
// 404s for bare absolute filesystem paths (e.g. "/tmp/foo.wav"). Prefixing
// with "file://" lets the browser load it directly, which is enough for
// Studio preview. `npx remotion render`'s asset-extraction step (used to mux
// the real audio bytes into the output) only accepts http(s) URLs, though
// (see https://www.remotion.dev/docs/miscellaneous/absolute-paths) -- so
// whatever invokes the render for real audiobook inputs must serve
// audioPath/imagePath over HTTP (e.g. a local static file server, or by
// copying into the bundle's public/ folder) before passing them in as props.
const toAssetSrc = (path: string): string => {
  if (/^(https?:\/\/|file:\/\/|data:|blob:)/.test(path)) {
    return path;
  }
  return `file://${path}`;
};

export const MainVideo: React.FC<VideoProps> = ({ audioPath }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {audioPath ? <Audio src={toAssetSrc(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
