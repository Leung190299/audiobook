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
EXPECTED_MANIFEST = "output/episodes/me_chong_giau_cua-20260813T015000Z-episodes.json"
EXPECTED_RENAMED = "output/episodes/me-chong-giau-so-do-tap-1.mp4"
EXPECTED_THUMBNAIL = "output/thumbnails/me_chong_giau_cua-20260813T015100Z.png"
EXPECTED_METADATA_INDEX = "output/metadata/me_chong_giau_cua-20260813T015000Z-episodes.json"
EXPECTED_SHORTS_PREFIX = "output/shorts/me_chong_giau_cua-20260813T015300Z"
EXPECTED_SHORT_COUNT = "2"
EXPECTED_FULL_MANIFEST = "output/episodes/me_chong_giau_cua-20260813T015000Z-full.json"
EXPECTED_FULL_INDEX = "output/metadata/me_chong_giau_cua-20260813T015000Z-full.json"
EXPECTED_FULL_RENAMED = "output/episodes/me-chong-giau-so-do.mp4"

# Các test dưới phần "đường đi thuận lợi" viết cho dây chuyền 22/09 (bắt trend +
# 3 tập). Từ 24/09 mặc định là chủ đề xoay vòng + FULL, nên _run() tự thêm hai
# cờ này cho chúng; test của chế độ mới gọi _run(..., legacy=False).
LEGACY_ARGS = ["--trend", "--format", "episodes"]


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


def _run(
    tmp_path: Path,
    args: list[str] | None = None,
    legacy: bool = True,
    dotenv: str | None = None,
    **env_overrides,
) -> Run:
    args = list(args or [])
    if legacy and not {"--trope", "--topic", "--khong-ton-tai"} & set(args):
        args = LEGACY_ARGS + args
    elif legacy and "--trope" in args:
        args = ["--format", "episodes"] + args
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy(RUN_DAILY, root / "run_daily.sh")
    (root / "run_daily.sh").chmod(0o755)
    if dotenv is not None:
        (root / ".env").write_text(dotenv, encoding="utf-8")

    # TITLE= đọc title từ file metadata JSON thật (dùng cho notify.cli), nên phải
    # dựng sẵn file đó.
    for index in (EXPECTED_METADATA_INDEX, EXPECTED_FULL_INDEX):
        metadata_path = root / index
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(
            json.dumps({"story_title": "Mẹ chồng giấu sổ đỏ", "episodes": []}, ensure_ascii=False),
            encoding="utf-8",
        )

    calls_file = tmp_path / "calls.log"
    calls_file.touch()

    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("AUDIOBOOK_")},
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
        "episodes.cli", "thumbnail.cli", "metadata.cli", "shorts.cli",
    ]:
        assert run.called(module), f"chưa gọi {module}\n{run.calls}"
    # Đăng YouTube phải là việc tự chọn, không được tự động chạy.
    assert not run.called("upload.episodes_cli")


def test_co_co_upload_thi_chay_them_stage_8(tmp_path: Path):
    run = _run(tmp_path, ["--upload"])
    assert run.exit_code == 0, run.proc.stderr
    assert run.called("upload.episodes_cli")


def test_y_tuong_va_slug_tu_stage_0_duoc_truyen_sang_stage_1(tmp_path: Path):
    run = _run(tmp_path)
    call = run.call_for("scripts.cli")
    assert "--idea-file output/ideas/me_chong_giau_cua-20260813T010000Z.txt" in call
    assert "--label me_chong_giau_cua" in call


def test_stage_4_nhan_dung_3_duong_dan_theo_dung_thu_tu(tmp_path: Path):
    # Đây là chỗ dễ nhầm nhất: script JSON, TTS JSON, images JSON — không phải .wav/.png.
    run = _run(tmp_path)
    assert run.call_for("episodes.cli") == (
        f"episodes.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON} {EXPECTED_IMAGES_JSON} --format episodes"
    )


def test_stage_2_va_3_deu_nhan_script_cua_stage_1_khong_nham_lan_metadata(tmp_path: Path):
    run = _run(tmp_path)
    assert run.call_for("tts.cli") == f"tts.cli {EXPECTED_SCRIPT}"
    assert run.call_for("images.cli") == f"images.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON}"


def test_stage_5_va_6_nhan_manifest_cua_stage_4(tmp_path: Path):
    run = _run(tmp_path)
    assert run.call_for("thumbnail.cli") == (
        f"thumbnail.cli {EXPECTED_SCRIPT} --episodes {EXPECTED_MANIFEST}"
    )
    assert run.call_for("metadata.cli") == (
        f"metadata.cli {EXPECTED_SCRIPT} --episodes {EXPECTED_MANIFEST}"
    )


def test_stage_7_short_nhan_audio_va_images_json(tmp_path: Path):
    # Short cắt theo mốc câu trong audio JSON của stage 2, không cần script hay video.
    run = _run(tmp_path)
    assert run.call_for("shorts.cli") == (
        f"shorts.cli {EXPECTED_AUDIO_JSON} {EXPECTED_IMAGES_JSON} --script {EXPECTED_SCRIPT}"
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
    assert f"Short: {EXPECTED_SHORT_COUNT} trích đoạn trong output/shorts" in run_log
    assert "Tập: 3 tập trong output/episodes" in run_log


def test_stage_8_upload_nhan_danh_sach_tap_va_prefix_short(tmp_path: Path):
    run = _run(tmp_path, ["--upload"])
    call = run.call_for("upload.episodes_cli")
    assert call == f"upload.episodes_cli {EXPECTED_METADATA_INDEX} --shorts-prefix {EXPECTED_SHORTS_PREFIX}"


def test_short_hong_thi_upload_khong_co_prefix_short(tmp_path: Path):
    run = _run(tmp_path, ["--upload"], FAKE_FAIL_MODULE="shorts.cli")
    assert run.call_for("upload.episodes_cli") == f"upload.episodes_cli {EXPECTED_METADATA_INDEX}"


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


def test_stage_6_khong_doi_ten_thi_coi_nhu_hong(tmp_path: Path):
    # Chế độ tập luôn đổi tên; thiếu dòng đó là stage 6 in sai định dạng.
    run = _run(tmp_path, ["--upload"], FAKE_NO_RENAME="1")
    assert run.exit_code == 1
    assert not run.called("upload.episodes_cli")


# --- các nhánh rẽ -------------------------------------------------------------


def test_trope_chi_dinh_thi_bo_qua_stage_0(tmp_path: Path):
    run = _run(tmp_path, ["--trope", "trong_sinh_bao_thu"])
    assert run.exit_code == 0
    assert not run.called("trend.cli")
    assert run.call_for("scripts.cli") == "scripts.cli trong_sinh_bao_thu --format episodes"


def test_co_no_upload_cu_van_chay_duoc_cho_tuong_thich(tmp_path: Path):
    run = _run(tmp_path, ["--no-upload"])
    assert run.exit_code == 0
    assert run.called("metadata.cli")
    assert not run.called("upload.episodes_cli")


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
        ("episodes.cli", "Stage 4"),
        ("upload.episodes_cli", "Stage 8"),
    ],
)
def test_stage_hong_thi_dung_ngay_va_bao_ngay(tmp_path: Path, module, stage_name):
    args = ["--upload"] if module == "upload.episodes_cli" else None
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
             "episodes.cli", "thumbnail.cli", "metadata.cli", "shorts.cli", "upload.episodes_cli"]
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
    assert run.called("upload.episodes_cli")
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
        "04-episodes.log", "05-thumbnail.log", "06-metadata.log", "07-short.log",
        "run.log",
    ]

    run_log = (log_dirs[0] / "run.log").read_text(encoding="utf-8")
    assert "me_chong_giau_cua" in run_log
    assert EXPECTED_RENAMED in run_log


# --- 24/09/2026: chủ đề + định dạng FULL (mặc định mới) ------------------------


def test_mac_dinh_la_topic_auto_va_full_khong_bat_trend(tmp_path: Path):
    run = _run(tmp_path, legacy=False)
    assert run.exit_code == 0, run.proc.stderr + run.stdout
    assert not run.called("trend.cli")
    assert run.call_for("scripts.cli") == "scripts.cli --topic auto --format full"
    assert run.call_for("episodes.cli") == (
        f"episodes.cli {EXPECTED_SCRIPT} {EXPECTED_AUDIO_JSON} {EXPECTED_IMAGES_JSON} --format full"
    )
    assert run.call_for("thumbnail.cli") == f"thumbnail.cli {EXPECTED_SCRIPT} --episodes {EXPECTED_FULL_MANIFEST}"
    assert run.call_for("metadata.cli") == f"metadata.cli {EXPECTED_SCRIPT} --episodes {EXPECTED_FULL_MANIFEST}"
    assert not run.called("upload.episodes_cli")
    notify = run.call_for("notify.cli")
    assert "success" in notify and EXPECTED_FULL_RENAMED in notify
    assert "--slug ho_hang_viet" in notify  # id chủ đề thật, không phải "auto"
    run_log = next((run.root / "output" / "daily").iterdir()) / "run.log"
    text = run_log.read_text(encoding="utf-8")
    assert "Chủ đề hôm nay: ho_hang_viet" in text
    assert "Full: 1 video trong output/episodes" in text


def test_topic_auto_format_full_co_upload(tmp_path: Path):
    run = _run(tmp_path, ["--topic", "auto", "--format", "full", "--upload"], legacy=False)
    assert run.exit_code == 0, run.proc.stderr + run.stdout
    assert run.call_for("upload.episodes_cli") == (
        f"upload.episodes_cli {EXPECTED_FULL_INDEX} --shorts-prefix {EXPECTED_SHORTS_PREFIX}"
    )
    assert "--url https://youtu.be/FAKEFULL1" in run.call_for("notify.cli")


def test_topic_chi_dinh_va_format_tu_env(tmp_path: Path):
    run = _run(tmp_path, ["--topic", "bo_me_trong_sinh"], legacy=False,
               AUDIOBOOK_FORMAT="episodes", FAKE_TOPIC="bo_me_trong_sinh")
    assert run.exit_code == 0, run.proc.stderr + run.stdout
    assert run.call_for("scripts.cli") == "scripts.cli --topic bo_me_trong_sinh --format episodes"
    assert run.call_for("episodes.cli").endswith("--format episodes")
    assert "--slug bo_me_trong_sinh" in run.call_for("notify.cli")


def test_env_audiobook_topic_thay_auto(tmp_path: Path):
    run = _run(tmp_path, legacy=False, AUDIOBOOK_TOPIC="nghe_la_hong_bien")
    assert run.call_for("scripts.cli") == "scripts.cli --topic nghe_la_hong_bien --format full"


def test_full_khong_doi_ten_thi_coi_nhu_hong(tmp_path: Path):
    run = _run(tmp_path, ["--upload"], legacy=False, FAKE_NO_RENAME="1")
    assert run.exit_code == 1
    assert not run.called("upload.episodes_cli")


@pytest.mark.parametrize(
    "args",
    [["--format", "dai"], ["--topic", "ho_hang_viet", "--trend"], ["--trope", "x", "--topic", "auto"]],
)
def test_co_sai_hoac_xung_dot_thi_bao_loi_ngay(tmp_path: Path, args):
    run = _run(tmp_path, args, legacy=False)
    assert run.exit_code == 2
    assert not run.calls


def test_doc_format_va_topic_tu_file_env(tmp_path: Path):
    run = _run(
        tmp_path,
        legacy=False,
        dotenv='SECURE_1PSID=x\nAUDIOBOOK_FORMAT=episodes  # chia tập\nAUDIOBOOK_TOPIC="nghe_la_hong_bien"\n',
        FAKE_TOPIC="nghe_la_hong_bien",
    )
    assert run.exit_code == 0, run.proc.stderr + run.stdout
    assert run.call_for("scripts.cli") == "scripts.cli --topic nghe_la_hong_bien --format episodes"
