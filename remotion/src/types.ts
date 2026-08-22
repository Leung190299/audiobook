export interface ChapterProps {
  index: number;
  heading: string;
  startSeconds: number;
  endSeconds: number;
  imagePath: string;
  // Mốc câu giữ nguyên trục thời gian toàn tập (không quy về gốc chương) --
  // xem Caption.tsx, nơi so trực tiếp với `seconds` toàn cục.
  sentences: { text: string; startSeconds: number; endSeconds: number }[];
}

export interface VideoProps {
  trope: string;
  title: string;
  audioPath: string;
  sampleRate: number;
  chapters: ChapterProps[];
}

export interface ShortCaption {
  text: string;
  startSeconds: number;
  endSeconds: number;
}

export interface ShortProps {
  trope: string;
  title: string;
  audioPath: string;
  imagePath: string;
  hookText: string;
  captions: ShortCaption[];
  audioDurationSeconds: number;
  ctaSeconds: number;
  ctaText: string;
}
