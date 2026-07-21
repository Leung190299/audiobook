import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import type { ChapterProps } from "./types";

interface CaptionProps {
  chapters: ChapterProps[];
}

const CHUNK_CHAR_BUDGET = 80;

function splitIntoChunks(text: string): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const chunks: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > CHUNK_CHAR_BUDGET && current) {
      chunks.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) {
    chunks.push(current);
  }
  return chunks;
}

export const Caption: React.FC<CaptionProps> = ({ chapters }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;

  const chapter = chapters.find((c) => seconds >= c.startSeconds && seconds < c.endSeconds);
  if (!chapter) {
    return null;
  }

  const chunks = splitIntoChunks(chapter.text);
  const totalChars = chunks.reduce((sum, c) => sum + c.length, 0) || 1;
  const chapterDuration = chapter.endSeconds - chapter.startSeconds;

  let cursor = chapter.startSeconds;
  let activeChunk: string | null = null;
  for (const chunk of chunks) {
    const chunkDuration = (chunk.length / totalChars) * chapterDuration;
    if (seconds >= cursor && seconds < cursor + chunkDuration) {
      activeChunk = chunk;
      break;
    }
    cursor += chunkDuration;
  }

  if (!activeChunk) {
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
      {activeChunk}
    </div>
  );
};
