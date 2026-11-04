import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { ChapterProps } from "./types";

interface CaptionProps {
  chapters: ChapterProps[];
}

export const Caption: React.FC<CaptionProps> = ({ chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;

  const chapter = chapters.find((c) => seconds >= c.startSeconds && seconds < c.endSeconds);
  if (!chapter) {
    return null;
  }

  // Giữ nguyên phụ đề của câu trước trong khoảng nghỉ giữa hai câu thay vì tắt
  // hẳn: dùng "startSeconds gần nhất đã qua" chứ không so cả startSeconds lẫn
  // endSeconds, giống hệt ShortVideo.tsx và vì cùng lý do -- nếu không chữ sẽ
  // chớp tắt trong khoảng nghỉ giữa các câu.
  const activeSentence = [...chapter.sentences]
    .reverse()
    .find((s) => seconds >= s.startSeconds);

  if (!activeSentence) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        left: "10%",
        right: "10%",
        textAlign: "center",
        color: "#fff",
        fontSize: 28,
        padding: "8px 16px",
        backgroundColor: "rgba(0,0,0,0.55)",
        borderRadius: 12,
      }}
    >
      {activeSentence.text}
    </div>
  );
};
