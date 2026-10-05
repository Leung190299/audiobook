import React from "react";
import { AbsoluteFill, Audio, staticFile, useVideoConfig } from "remotion";
import type { VideoProps } from "./types";
import { BackgroundVideo } from "./BackgroundVideo";
import { BrandedLayout } from "./BrandedLayout";
import { SceneBackground } from "./SceneBackground";
import { useBeVietnamPro } from "./fonts";

// Dissolve giữa hai cảnh ảnh (chỉ dùng khi không có video nền). Dài hơn khoảng
// nghỉ 0,5s giữa chương (gap_seconds ở config/voice.yaml) là cố ý: ảnh tan dần
// qua ranh giới chương nhìn mềm hơn là cắt đúng lúc tiếng ngắt.
const CROSSFADE_SECONDS = 1.0;

// Video dài kiểu "video thủ công ở giữa, hai tấm thương hiệu hai bên" (05/10).
//
// Khung hình tĩnh từ đầu tới cuối: KHÔNG phụ đề, tên chương, avatar, sóng âm,
// chữ hook đầu tập hay card kết. Bỏ theo format tham khảo đang chạy tốt (2,38
// triệu view, 38 phút) -- video giữa tự giữ mắt người xem, người cần phụ đề tự
// bật phụ đề tự động của YouTube. Cảnh báo "truyện hư cấu, do AI tạo" nằm cố
// định ở tấm bên phải (BrandPanel).
//
// hookText, coldOpenSeconds, outroTitle, outroText, episodeLabel vẫn có trong
// props (episodes/props_builder.py còn ghi) nhưng không vẽ nữa. Đoạn cold open
// vẫn PHÁT tiếng -- nó là phần dựng audio, chỉ bỏ chữ đè lên hình.
export const MainVideo: React.FC<VideoProps> = ({
  audioPath,
  chapters,
  outroSeconds = 0,
  backgroundVideo,
  backgroundVideoSeconds = 0,
  backgroundVideoAspect,
  channelName,
}) => {
  useBeVietnamPro();
  const { fps } = useVideoConfig();
  const crossfadeFrames = Math.round(CROSSFADE_SECONDS * fps);

  // Trải mọi cảnh của mọi chương thành một dãy, đánh số liên tục để chọn kiểu
  // chuyển động luân phiên trên toàn tập chứ không reset mỗi chương.
  const scenes = chapters.flatMap((chapter) =>
    chapter.scenes.map((scene) => ({ chapterIndex: chapter.index, scene }))
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <BrandedLayout
        // Ảnh cảnh của stage 3 là khổ 16:9; thiếu tỉ lệ thì BrandedLayout cũng
        // coi như 16:9 và chặn ô giữa ở 66% bề ngang.
        aspect={backgroundVideo ? backgroundVideoAspect : undefined}
        channelName={channelName}
      >
        {backgroundVideo ? (
          <BackgroundVideo src={backgroundVideo} seconds={backgroundVideoSeconds} />
        ) : (
          scenes.map(({ chapterIndex, scene }, i) => {
            // Lấy mốc bắt đầu của cảnh KẾ TIẾP làm endFrame, không phải
            // endSeconds của chính cảnh này: giữa hai chương có khoảng nghỉ
            // tiếng 0,5s, nên với endFrame cũ cả hai lớp đều mờ nửa chừng quanh
            // ranh giới (~6% đen lộ ra). Cảnh cuối kéo qua cả đoạn kết để nền
            // không tắt đen khi tiếng đã hết.
            const next = scenes[i + 1];
            const endSeconds = next ? next.scene.startSeconds : scene.endSeconds + outroSeconds;
            return (
              <SceneBackground
                key={`${chapterIndex}-${scene.number}`}
                scene={scene}
                startFrame={Math.round(scene.startSeconds * fps)}
                endFrame={Math.round(endSeconds * fps)}
                crossfadeFrames={crossfadeFrames}
                motionIndex={i}
              />
            );
          })
        )}
      </BrandedLayout>
      {audioPath ? <Audio src={staticFile(audioPath)} /> : null}
    </AbsoluteFill>
  );
};
