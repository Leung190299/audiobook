export interface ChapterProps {
  index: number;
  heading: string;
  text: string;
  startSeconds: number;
  endSeconds: number;
  imagePath: string;
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
