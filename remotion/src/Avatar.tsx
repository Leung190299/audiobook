import React from "react";
import { Img, staticFile } from "remotion";

export const Avatar: React.FC = () => {
  return (
    <div
      style={{
        position: "absolute",
        top: 24,
        left: 24,
        width: 96,
        height: 96,
        borderRadius: "50%",
        overflow: "hidden",
      }}
    >
      <Img
        src={staticFile("remotion/public/avatar.png")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
    </div>
  );
};
