export interface SceneProps {
  number: number;
  // Trục thời gian do bên dùng quyết định: ChapterProps.scenes giữ trục toàn tập
  // (giống mốc câu), ShortProps.scenes quy về gốc phần -- xem comment ở hai chỗ đó.
  startSeconds: number;
  endSeconds: number;
  imagePath: string;
}

export interface ChapterProps {
  index: number;
  heading: string;
  startSeconds: number;
  endSeconds: number;
  // Mỗi chương nhiều cảnh ~50s, phủ kín chương (stage 3 đảm bảo).
  scenes: SceneProps[];
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
  // Cảnh giao với phần, mốc QUY VỀ GỐC PHẦN (audio short đã cắt). Cảnh đầu
  // startSeconds = 0. Khác ChapterProps.scenes của video dài (trục toàn tập).
  scenes: SceneProps[];
  hookText: string;
  partLabel: string; // ví dụ "PHẦN 7/32", hiển thị trên ảnh bìa
  captions: ShortCaption[];
  audioDurationSeconds: number;
  ctaSeconds: number;
  ctaText: string;
}
