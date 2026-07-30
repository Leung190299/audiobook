# Thiết kế: đổi TTS engine OmniVoice → VieNeu-TTS

**Ngày**: 2026-07-30
**Trạng thái**: Đã duyệt, sẵn sàng lập kế hoạch triển khai

## Bối cảnh & mục tiêu

Module TTS hiện tại ([docs/superpowers/specs/2026-07-21-tts-module-design.md](2026-07-21-tts-module-design.md)) dùng [OmniVoice](https://github.com/k2-fsa/OmniVoice), chạy CPU-only trên máy vận hành (MPS crash đã xác nhận ở thiết kế trước). Thực tế sản xuất cho thấy OmniVoice trên CPU rất chậm: ~12 phút hiệu dụng/chương, ~3.2 giờ cho 1 truyện 16 chương — buộc phải chạy song song tối đa 2 tiến trình để không vượt quá thời gian chấp nhận được, kéo theo rủi ro OOM (máy 16GB RAM, có lúc chỉ còn ~4.5GB free) và một lớp bug đã phát hiện thực tế: `tts/merge_cli.py` ghép nhầm audio giữa 2 truyện khác nhau chia sẻ cùng thư mục `output/audio/chapters/` (đã vá, xem `tts/merge_cli.py` + `tests/tts/test_merge_cli.py` trên `master`).

Người vận hành yêu cầu đổi sang [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) (Apache-2.0, 2.2k+ sao). Bản build hiện tại (v3 Turbo) chạy **torch-free qua ONNX Runtime trên CPU**, 48kHz, có sẵn 14 giọng dựng sẵn (built-in voices) phủ 3 miền Bắc/Trung/Nam, hỗ trợ 3 phong cách đọc (tự nhiên/tin tức/kể chuyện).

**Đo thực tế trên máy vận hành** (trước khi viết spec này, qua `uv run --with vieneu`):
- 1 câu ngắn (7.6s audio): RTF 0.292, 2.22s xử lý.
- 1 chương thật 865 từ (220.3s ≈ 3.67 phút audio, lấy từ `output/scripts/trong_sinh_mat_the-*.json` chương 1): RTF 0.136, **29.93 giây xử lý** — nhanh hơn ~24x so với thời gian đọc thật, và nhanh hơn ~24x so với tốc độ OmniVoice từng đo (~12 phút/chương thật, tức chậm hơn thời gian đọc thật).
- Không dùng PyTorch/GPU — cài đặt tối giản (`pip install vieneu`) không kéo theo torch, loại bỏ hẳn lớp rủi ro crash MPS/PyTorch đã gặp với OmniVoice (và đã né tương tự khi chuyển sang mflux cho module ảnh).

Với tốc độ mới, 16 chương chạy **tuần tự trong 1 tiến trình** ước tính chỉ ~8 phút — không còn cần chạy song song, không còn cần chia sẻ thư mục theo chương, không còn cần bước ghép (merge) riêng.

## 1. Quyết định thiết kế

- **Giọng đọc**: dùng giọng dựng sẵn **"Ngọc Linh"** (Nữ · Bắc · phong cách kể chuyện — `doc_truyen`), lấy từ danh sách 14 giọng thật đã liệt kê qua `vieneu.list_preset_voices()`. Khớp với giọng nữ đang dùng hiện tại (`config/voice.yaml` cũ: "female, moderate pitch, young adult"). **Không dùng voice cloning** dù VieNeu-TTS hỗ trợ clone từ `config/voices/female_ngochuyen.mp3` — theo tài liệu chính thức, cloning/denoise bắt buộc chạy qua PyTorch (GPU/MPS) engine, đúng lớp rủi ro crash đã gặp với OmniVoice trên máy này. Giọng dựng sẵn chạy được trên CPU/ONNX torch-free, không có rủi ro này. File `config/voices/female_ngochuyen.mp3` giữ nguyên trên đĩa (không xoá) nhưng không còn được tham chiếu bởi code.
- **Phiên bản model**: **v3 Turbo, backend ONNX (CPU), ép rõ ràng** qua `Vieneu(backend="onnx")` thay vì để auto-detect — nhất quán với nguyên tắc "không phụ thuộc PyTorch/MPS" đã áp dụng cho mflux.
- **Đơn giản hoá kiến trúc chạy**: bỏ hẳn chế độ per-chapter (`tts.cli --chapter N`) và `tts/merge_cli.py`. `tts.cli` giờ luôn nhận 1 file script JSON, load model 1 lần, lồng tiếng tuần tự tất cả chương trong quy trình hiện có, xuất thẳng 1 file audio hoàn chỉnh — không còn khái niệm "audio theo chương nằm chung thư mục giữa các truyện", nên loại bỏ hẳn lớp bug cross-trope đã gặp, không chỉ vá triệu chứng.
- **Sample rate**: đổi mặc định trong `config/voice.yaml` từ 24000 → **48000** (VieNeu-TTS v3 Turbo xuất 48kHz cố định). Giá trị này chỉ dùng để ghi WAV và tính timestamp/thời lượng — không có chỗ nào trong `video/`, `remotion/`, `metadata/` giả định cứng 24kHz (đã grep xác nhận; `remotion/src/Root.tsx`'s `sampleRate: 24000` chỉ là default prop, không được `Waveform.tsx` hay bất kỳ component nào đọc lại để tính toán).
- **Phong cách đọc**: `style: "doc_truyen"` (kể chuyện) — khớp bản chất nội dung (audiobook truyện), có sẵn cho mọi giọng dựng sẵn.
- **Emotion cues** (`[cười]`, `[thở dài]`, `[hắng giọng]`): tính năng thử nghiệm (experimental) của VieNeu-TTS — **ngoài phạm vi**, không tự động chèn vào text kịch bản.
- **Model load**: giữ nguyên nguyên tắc cũ — load 1 lần, tái dùng cho mọi chương trong 1 lần chạy CLI.

## 2. Kiến trúc

```
tts/
├── __init__.py
├── voice_profile.py       # đọc config/voice.yaml -> VoiceProfile (tên giọng, phong cách, target LUFS, sample rate, gap giây)
├── synthesizer.py          # wrap VieNeu-TTS: synthesize_chapter(chapter, model, voice_profile) -> audio np.ndarray @48kHz
├── audio_postprocess.py    # KHÔNG ĐỔI — chuẩn hoá loudness (pyloudnorm) + nối chương + tính timestamp, agnostic với engine
├── storage.py               # KHÔNG ĐỔI — lưu file .wav + .json
└── cli.py                   # entrypoint: nhận đường dẫn script JSON, chạy toàn bộ tuần tự, in kết quả
```

`tts/merge_cli.py` và `tests/tts/test_merge_cli.py` bị **xoá**.

**Luồng xử lý** (không đổi về hình dạng so với thiết kế cũ, chỉ đổi bước 2):

```
[File JSON kịch bản]
   → 1. Load VieNeu-TTS model 1 lần: Vieneu(backend="onnx")
   → 2. Với mỗi chương (tuần tự): gọi model.infer(text=chapter.text,
        voice=voice_profile.voice, style=voice_profile.style)
        → audio np.ndarray @ 48kHz cho chương đó
   → 3. Chuẩn hoá loudness từng đoạn audio chương về target LUFS (không đổi)
   → 4. Nối các đoạn audio theo đúng thứ tự chương, chèn khoảng lặng (không đổi)
   → 5. Ghi timestamp bắt đầu/kết thúc từng chương (không đổi)
   → 6. Lưu .wav + .json vào output/audio/ (không đổi)
```

**Cấu hình** (`config/voice.yaml`):

```yaml
voice: "Ngọc Linh"
style: "doc_truyen"
target_lufs: -16.0
sample_rate: 48000
gap_seconds: 0.5
```

**`tts/voice_profile.py`**: `VoiceProfile` đổi trường — bỏ `instruction`, `ref_audio_path`; thêm `voice: str`, `style: str`. Giữ `target_lufs`, `sample_rate`, `gap_seconds`.

**`tts/synthesizer.py`**: `synthesize_chapter(chapter, model, voice_profile)` gọi `model.infer(text=chapter.text, voice=voice_profile.voice, style=voice_profile.style)`. VieNeu-TTS trả thẳng `np.ndarray` (khác OmniVoice trả sequence cần `result[0]`) — đơn giản hoá logic đọc kết quả. Vẫn bọc mọi exception từ model thành `SynthesisError` kèm số chương/tiêu đề, và validate kiểu trả về là array-like trước khi `np.asarray(..., dtype=np.float32)`.

**`tts/cli.py`**: `_load_model()` đổi thành:
```python
def _load_model():
    from vieneu import Vieneu
    return Vieneu(backend="onnx")
```
Bỏ `--chapter` argument, `CHAPTER_OUTPUT_DIR`, `ChapterNotFoundError`, tham số `chapter_index` của `_run()`.

**`pyproject.toml`**: bỏ `omnivoice>=0.1.0`, `torch>=2.0.0` (đã xác nhận không nơi nào khác trong repo import torch ngoài `tts/cli.py`); thêm `vieneu` (phiên bản mới nhất tại thời điểm triển khai).

## 3. Testing & vận hành

- **Không load model VieNeu-TTS thật trong test tự động** — giữ nguyên nguyên tắc cũ, dùng fake model có `.infer(text, voice, style) -> np.ndarray` trong test.
- Cập nhật `tests/tts/test_synthesizer.py`, `tests/tts/test_cli.py`, `tests/tts/test_voice_profile.py` theo field/interface mới (voice/style thay instruction/ref_audio_path; fake model `.infer()` trả thẳng ndarray thay vì sequence).
- Xoá `tests/tts/test_merge_cli.py` cùng với `merge_cli.py`.
- `tests/tts/test_audio_postprocess.py`, `tests/tts/test_storage.py` không cần đổi — các test này tự truyền `sample_rate=24000` làm giá trị input độc lập cho hàm thuần tuý, không phụ thuộc giá trị mặc định trong `config/voice.yaml`.
- **Smoke test thủ công** (cuối kế hoạch triển khai): chạy `tts.cli` thật với 1 script JSON đã có sẵn (toàn bộ chương, không còn cần `--chapter`), nghe thử audio hoàn chỉnh xác nhận chất lượng giọng "Ngọc Linh" + phong cách kể chuyện, đo thời gian chạy thật so với ước tính ~8 phút/16 chương, xác nhận không có lỗi ở điểm nối chương.

## 4. Tài liệu cần cập nhật

`.claude/skills/generating-audiobook-video/SKILL.md`:
- Xoá mục "Parallel TTS (stage 2), real findings" (không còn `--chapter`/song song/merge).
- Cập nhật timing thực tế stage 2: từ "~3.2 giờ cho 16 chương, CPU-only" → ước tính mới dựa trên smoke test thật (~8 phút, cần xác nhận lại bằng số đo thật khi chạy production).
- Xoá cảnh báo RAM/OOM đặc thù OmniVoice ("chạy tối đa 2 tiến trình song song").
- Cập nhật phần mô tả stage 2 để phản ánh: 1 lệnh `tts.cli <script_path>` duy nhất, không còn 2 chế độ.
- Note: torch-free, không còn rủi ro MPS/PyTorch cho TTS.

## 5. Rủi ro & lưu ý

- **Chất lượng giọng "Ngọc Linh" cho nội dung dài (16 chương liên tục)**: mới xác nhận qua đo tốc độ và 1 đoạn ngắn, chưa nghe thử toàn bộ 1 truyện dài — smoke test thủ công ở cuối kế hoạch triển khai sẽ xác nhận. Nếu chất lượng không đạt, có thể đổi sang 1 trong 13 giọng còn lại chỉ bằng cách sửa `config/voice.yaml` (không cần đổi code).
- **RTF đo được (0.136–0.292) là trên đoạn ngắn/1 chương** — chưa đo full 16 chương liên tục trong 1 tiến trình (khả năng có overhead/leak khi lặp nhiều lần chưa được kiểm chứng). Smoke test triển khai sẽ đo thời gian thật cho toàn bộ script.
- **VieNeu-TTS là dự án đang phát triển nhanh** (v3 Turbo ghi rõ "early access", roadmap còn "v3 full release" chưa ra) — API `vieneu.infer()`/`list_preset_voices()` có thể đổi ở các phiên bản sau. Không ghim version cụ thể trong spec này; `pyproject.toml` dùng constraint mở, chấp nhận rủi ro breaking change ở lần nâng cấp sau (ngoài phạm vi xử lý ở đây).
- **License**: Apache-2.0, dùng thương mại được, không có điều khoản đặc biệt nào phát hiện khác với OmniVoice.
- **Dữ liệu audio cũ (24kHz, từ OmniVoice) đã tồn tại trong `output/audio/`**: không bị ảnh hưởng, không cần migrate — mỗi file tự chứa `sample_rate` riêng trong metadata JSON, các bước sau (video/metadata) đọc giá trị này từ file chứ không giả định cố định.

## Ngoài phạm vi (không giải quyết trong bản thiết kế này)

- Voice cloning (kể cả nếu sau này chuyển sang chạy PyTorch/GPU để dùng được tính năng này).
- Emotion cues (`[cười]`, `[thở dài]`, `[hắng giọng]`).
- Podcast/Conversation mode nhiều giọng.
- Streaming inference (`infer_stream`) — không cần cho pipeline batch hiện tại.
- Nâng cấp lên VieNeu-TTS v3 full khi ra mắt chính thức.
- Xoá `config/voices/female_ngochuyen.mp3` khỏi đĩa hoặc dọn file audio 24kHz cũ trong `output/audio/`.
