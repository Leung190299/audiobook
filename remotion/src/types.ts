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
  // Các trường dưới chỉ có khi props do episodes/props_builder.py dựng (một
  // TẬP 15-20 phút). video/props_builder.py (bản full) không đặt -> undefined,
  // MainVideo coi như 0/rỗng và render y như trước.
  episodeLabel?: string; // "TẬP 1/3", góc trên bên phải
  hookText?: string; // câu hook, hiện trong cold open
  coldOpenSeconds?: number; // độ dài cold open ở đầu (chương giả index 0)
  outroSeconds?: number; // card kết sau khi hết tiếng
  outroTitle?: string;
  outroText?: string;
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
