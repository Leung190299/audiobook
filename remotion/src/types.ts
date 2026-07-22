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
