"""Test tích hợp cho run_daily.sh.

Chạy script thật, nhưng thay `uv run python -m` bằng tests/fake_stage.sh qua biến
AUDIOBOOK_RUNNER. Bắt được đúng loại lỗi tốn kém nhất: regex parse sai, biến nối
nhầm giữa các stage, nhánh lỗi không thoát — những thứ mà bình thường phải chạy
thật 50 phút mới lộ.

Giới hạn đã biết: test này chạy trên `sed` của máy đang chạy test. Trên macOS đó là
BSD sed, trên CI Linux là GNU sed — các pattern trong run_daily.sh viết theo POSIX
ERE nên hợp lệ ở cả hai, nhưng test chỉ thật sự chứng minh cho cái đang chạy.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_DAILY = REPO_ROOT / "run_daily.sh"
FAKE_STAGE = Path(__file__).resolve().parent / "fake_stage.sh"

EXPECTED_SCRIPT = "output/scripts/me_chong_giau_cua-20260813T011000Z.json"
EXPECTED_AUDIO_JSON = "output/audio/me_chong_giau_cua-20260813T012500Z.json"
EXPECTED_IMAGES_JSON = "output/images/me_chong_giau_cua-20260813T013500Z.json"
EXPECTED_VIDEO = "output/video/me_chong_giau_cua-20260813T015000Z.mp4"
EXPECTED_RENAMED = "output/video/me-chong-giau-so-do-truyen-audio.mp4"
EXPECTED_THUMBNAIL = "output/thumbnails/me_chong_giau_cua-20260813T015100Z.png"
EXPECTED_METADATA_JSON = "output/metadata/me_chong_giau_cua-20260813T015200Z.json"
EXPECTED_SHORT_COUNT = "2"


class Run:
    """Kết quả một lượt chạy run_daily.sh trong sandbox tạm."""

    def __init__(self, proc: subprocess.CompletedProcess, root: Path, calls_file: Path):
        self.proc = proc
        self.root = root
        # fake_stage.sh gộp lệnh nhiều dòng về một dòng bằng `tr`, để lại khoảng
        # trắng thừa ở cuối — cắt đi cho so sánh bằng == đọc được dễ hơn.
        self.calls = [
            stripped
            for line in calls_file.read_text(encoding="utf-8").splitlines()
            if (stripped := line.strip())
        ]

    @property
    def exit_code(self) -> int:
        return self.proc.returncode

    @property
    def stdout(self) -> str:
        return self.proc.stdout

    def call_for(self, module: str) -> str | None:
        for line in self.calls:
            if line == module or line.startswith(f"{module} "):
                return line
        return None

    def called(self, module: str) -> bool:
        return any(line.split(" ")[0] == module for line in self.calls)


def _run(tmp_path: Path, args: list[str] | None = None, **env_overrides) -> Run:
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy(RUN_DAILY, root / "run_daily.sh")
    (root / "run_daily.sh").chmod(0o755)

    # TITLE= đọc title từ file metadata JSON thật (dùng cho notify.cli), nên phải
    # dựng sẵn file đó.
    metadata_path = root / EXPECTED_METADATA_JSON
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps({"title": "Mẹ chồng giấu sổ đỏ"}, ensure_ascii=False), encoding="utf-8"
    )

    calls_file = tmp_path / "calls.log"
    calls_file.touch()

    env = {
        **os.environ,
        "AUDIOBOOK_RUNNER": str(FAKE_STAGE),
        "FAKE_LOG": str(calls_file),
    }
    env.update({k: v for k, v in env_overrides.items() if v is not None})

    proc = subprocess.run(
        ["bash", str(root / "run_daily.sh"), *(args or [])],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return Run(proc, root, calls_file)


# --- đường đi thuận lợi -------------------------------------------------------


def test_mac_dinh_dung_video_khong_dang_youtube(tmp_path: Path):
    run = _run(tmp_path)
    assert run.exit_code == 0, run.proc.stderr
    for module in [
        "trend.cli", "scripts.cli", "tts.cli", "images.cli",
        "video.cli", "thumbnail.cli", "metadata.cli", "shorts.cli",
    ]:
        assert run.called(module), f"chưa gọi {module}\n{run.calls}"
    # Đăng YouTube phải là việc tự chọn, không được tự động chạy.
    assert not run.called("upload.cli")


def test_co_co_upload_thi_chay_them_stage_8(tmp_path: Path):
    run = _run(tmp_path, ["--upload"])
    assert run.exit_code == 0, run.proc.stderr
    assert run.called("upload.cli")


def test_y_tuong_va_slug_tu_stage_0_duoc_truyen_sang_stage_1(tmp_path: Path):
    run = _run(tmp_path)
    call = run.call_for("scripts.cli")
    assert "--idea-file output/ideas/me_chong_giau_cua-20260813T010000Z.txt" in call
    assert "--label me_chong_giau_cua" in call


def test_stage_4_nhan_dung_3_duong_dan_theo_dung_thu_tu(tmp_path: Path):
    # Đây là chỗ dễ nhầm nhất: script JSON, TTS JSON, images JSON — không phải .wav/.png.
    run = _run(tmp_path)
    assert run.call_for("video.cli") == (
        f"video.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON} {EXPECTED_IMAGES_JSON}"
    )


def test_stage_2_va_3_deu_nhan_script_cua_stage_1_khong_nham_lan_metadata(tmp_path: Path):
    run = _run(tmp_path)
    assert run.call_for("tts.cli") == f"tts.cli {EXPECTED_SCRIPT}"
    assert run.call_for("images.cli") == f"images.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON}"


def test_stage_6_nhan_video_goc_chu_khong_phai_ten_da_doi(tmp_path: Path):
    # Stage 6 mới là cái đổi tên, nên nó phải nhận tên gốc từ stage 4.
    run = _run(tmp_path)
    assert run.call_for("metadata.cli") == (
        f"metadata.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON} {EXPECTED_VIDEO}"
    )


def test_stage_7_short_nhan_audio_va_images_json(tmp_path: Path):
    # Short cắt theo mốc câu trong audio JSON của stage 2, không cần script hay video.
    run = _run(tmp_path)
    assert run.call_for("shorts.cli") == (
        f"shorts.cli {EXPECTED_AUDIO_JSON} {EXPECTED_IMAGES_JSON}"
    )


def test_short_van_chay_khi_khong_dang_youtube(tmp_path: Path):
    # Nhánh thoát sớm của --no-upload không được nhảy qua stage short.
    run = _run(tmp_path)
    assert run.exit_code == 0
    assert run.called("shorts.cli")


def test_so_phan_short_duoc_ghi_vao_log(tmp_path: Path):
    # Chứng minh run_daily.sh đã parse đúng số phần từ dòng tổng kết của stage 7
    # và ghi vào run.log. Hồi regex sai sẽ không có test nào phát hiện.
    run = _run(tmp_path)
    assert run.exit_code == 0
    log_dirs = list((run.root / "output" / "daily").iterdir())
    assert len(log_dirs) == 1

    run_log = (log_dirs[0] / "run.log").read_text(encoding="utf-8")
    # Phải khớp đúng dòng `log "  Short: $SHORT_COUNT phần trong output/shorts"` do
    # run_daily.sh tự ghép từ biến đã parse — không phải chỉ tìm chuỗi trong
    # run.log: log riêng của stage 7 (chứa nguyên văn "Đã render 2 short vào
    # output/shorts") được cat vào run.log trước khi extract chạy, nên tìm đúng
    # chuỗi đó vẫn khớp kể cả khi regex parse hỏng hoàn toàn. Dòng tóm tắt do
    # run_daily.sh tự ghi ("Short: 2 phần trong ...") không trùng với dòng thô đó,
    # nên assert này chỉ pass khi SHORT_COUNT thật sự được parse ra "2".
    assert f"Short: {EXPECTED_SHORT_COUNT} phần trong output/shorts" in run_log


def test_stage_8_upload_ten_video_da_doi_chu_khong_phai_ten_goc(tmp_path: Path):
    # Tên gốc không còn tồn tại sau stage 6 — dùng nhầm là upload file không có thật.
    run = _run(tmp_path, ["--upload"])
    call = run.call_for("upload.cli")
    assert EXPECTED_RENAMED in call
    assert EXPECTED_VIDEO not in call
    assert f"--thumbnail {EXPECTED_THUMBNAIL}" in call


def test_thong_bao_khi_chi_dung_video_mang_ten_file_khong_mang_link(tmp_path: Path):
    run = _run(tmp_path)
    call = run.call_for("notify.cli")
    assert "success" in call
    assert "Mẹ chồng giấu sổ đỏ" in call  # tiêu đề đọc từ metadata JSON thật
    assert EXPECTED_RENAMED in call
    # Chưa đăng thì không được bịa ra link YouTube.
    assert "--url" not in call


def test_thong_bao_khi_co_upload_mang_them_link_youtube(tmp_path: Path):
    call = _run(tmp_path, ["--upload"]).call_for("notify.cli")
    assert "--url https://youtu.be/FAKE12345" in call


def test_stage_6_khong_doi_ten_thi_dung_lai_ten_goc(tmp_path: Path):
    run = _run(tmp_path, ["--upload"], FAKE_NO_RENAME="1")
    assert run.exit_code == 0
    assert EXPECTED_VIDEO in run.call_for("upload.cli")


# --- các nhánh rẽ -------------------------------------------------------------


def test_trope_chi_dinh_thi_bo_qua_stage_0(tmp_path: Path):
    run = _run(tmp_path, ["--trope", "trong_sinh_bao_thu"])
    assert run.exit_code == 0
    assert not run.called("trend.cli")
    assert run.call_for("scripts.cli") == "scripts.cli trong_sinh_bao_thu"


def test_co_no_upload_cu_van_chay_duoc_cho_tuong_thich(tmp_path: Path):
    run = _run(tmp_path, ["--no-upload"])
    assert run.exit_code == 0
    assert run.called("metadata.cli")
    assert not run.called("upload.cli")


def test_tham_so_la_thi_bao_loi_ngay(tmp_path: Path):
    run = _run(tmp_path, ["--khong-ton-tai"])
    assert run.exit_code == 2
    assert not run.calls


# --- nhánh hỏng ---------------------------------------------------------------


@pytest.mark.parametrize(
    "module,stage_name",
    [
        ("trend.cli", "Stage 0"),
        ("scripts.cli", "Stage 1"),
        ("tts.cli", "Stage 2"),
        ("video.cli", "Stage 4"),
        ("upload.cli", "Stage 8"),
    ],
)
def test_stage_hong_thi_dung_ngay_va_bao_ngay(tmp_path: Path, module, stage_name):
    args = ["--upload"] if module == "upload.cli" else None
    run = _run(tmp_path, args, FAKE_FAIL_MODULE=module)
    assert run.exit_code == 1
    assert stage_name in run.stdout

    failures = [c for c in run.calls if c.startswith("notify.cli failure")]
    assert len(failures) == 1, f"phải bắn đúng một thông báo lỗi, có {len(failures)}\n{run.calls}"
    assert "--detail-file" in failures[0]

    # Stage crash và stage in output lạ là hai kiểu hỏng khác nhau — báo nhầm loại
    # là 9 giờ sáng ngồi mò nhầm chỗ. Đây cũng là cái chốt giữ `exit 1` trong
    # run_stage: bỏ nó đi thì lỗi crash sẽ bị báo thành lỗi parse.
    assert "không parse được output" not in failures[0], (
        f"stage crash bị báo nhầm thành lỗi parse: {failures[0]}"
    )

    # Không được chạy tiếp stage sau khi đã hỏng.
    order = ["trend.cli", "scripts.cli", "tts.cli", "images.cli",
             "video.cli", "thumbnail.cli", "metadata.cli", "shorts.cli", "upload.cli"]
    for later in order[order.index(module) + 1:]:
        assert not run.called(later), f"vẫn chạy {later} sau khi {module} hỏng"


def test_stage_chay_xong_nhung_in_output_la_thi_van_dung_lai(tmp_path: Path):
    # Đây là kiểu hỏng âm thầm: stage exit 0, nhưng đổi định dạng print() nên
    # regex không khớp. Nếu không chặn, các stage sau nhận đường dẫn rỗng.
    run = _run(tmp_path, FAKE_GARBAGE_MODULE="tts.cli")
    assert run.exit_code == 1
    assert "Không đọc được đường dẫn" in run.stdout
    assert not run.called("images.cli")

    failure_call = next((c for c in run.calls if c.startswith("notify.cli failure")), None)
    assert failure_call is not None
    assert "không parse được output" in failure_call


def test_stage_7_short_hong_khong_lam_dung_luot_chay(tmp_path: Path):
    # Stage 7 giờ là tính toán thuần (cắt file theo mốc câu, không gọi Gemini)
    # nhưng vẫn có thể hỏng vì lý do khác (Remotion, props sai...). Video dài,
    # thumbnail, metadata SEO đã xong hết trước đó nên short hỏng không được
    # làm cả lượt chạy báo thất bại.
    run = _run(tmp_path, FAKE_FAIL_MODULE="shorts.cli")
    assert run.exit_code == 0, run.proc.stderr
    assert "Stage 7" in run.stdout
    assert "CẢNH BÁO" in run.stdout
    # Lệnh dựng lại tay phải dùng audio JSON của stage 2, không phải script JSON.
    assert f"shorts.cli \"{EXPECTED_AUDIO_JSON}\"" in run.stdout

    assert not any(c.startswith("notify.cli failure") for c in run.calls)
    assert any(c.startswith("notify.cli success") for c in run.calls)


def test_stage_7_short_output_la_khong_lam_dung_luot_chay(tmp_path: Path):
    # Kiểu hỏng âm thầm của stage 7 (exit 0, output không parse được) cũng
    # không được chặn lượt chạy — khác hẳn quy tắc của các stage khác.
    run = _run(tmp_path, FAKE_GARBAGE_MODULE="shorts.cli")
    assert run.exit_code == 0, run.proc.stderr

    assert not any(c.startswith("notify.cli failure") for c in run.calls)
    assert any(c.startswith("notify.cli success") for c in run.calls)


def test_co_upload_va_short_hong_thi_van_chay_stage_8(tmp_path: Path):
    # Stage 7 non-fatal: nếu short hỏng nhưng có --upload, stage 8 phải chạy.
    # Đây là test cho commit design này — short hỏng không được dừng toàn bộ
    # vì video dài, thumbnail, metadata đã xong.
    run = _run(tmp_path, ["--upload"], FAKE_FAIL_MODULE="shorts.cli")
    assert run.exit_code == 0, run.proc.stderr
    assert "Stage 7" in run.stdout
    assert "CẢNH BÁO" in run.stdout

    # Upload phải chạy dù short hỏng.
    assert run.called("upload.cli")
    # Báo thành công, không báo lỗi.
    assert not any(c.startswith("notify.cli failure") for c in run.calls)
    assert any(c.startswith("notify.cli success") for c in run.calls)


# --- log ----------------------------------------------------------------------


def test_moi_stage_ghi_log_rieng_de_lan_lai_khi_hong(tmp_path: Path):
    run = _run(tmp_path)
    log_dirs = list((run.root / "output" / "daily").iterdir())
    assert len(log_dirs) == 1

    files = sorted(p.name for p in log_dirs[0].iterdir())
    assert files == [
        "00-trend.log", "01-script.log", "02-tts.log", "03-images.log",
        "04-video.log", "05-thumbnail.log", "06-metadata.log", "07-short.log",
        "run.log",
    ]

    run_log = (log_dirs[0] / "run.log").read_text(encoding="utf-8")
    assert "me_chong_giau_cua" in run_log
    assert EXPECTED_RENAMED in run_log
