# Giám đốc kênh, đợt 1: gói `director`, skill hai phiên, launchd, chế độ chỉ-báo-cáo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi sáng 08:00 và chiều 17:30 một phiên `claude -p` chạy nền đọc số hai kênh, ghi quyết định và báo cáo Telegram; chưa gọi nhà máy (chế độ chỉ-báo-cáo) cho tới khi đợt 2 xong.

**Architecture:** Gói Python `director/` làm phần tất định (kéo Analytics, trạng thái kênh, khóa ngày, sổ thay đổi) và in ra tệp JSON/Markdown; skill `channel-director` là quy trình cho phiên Claude; `scripts/director.sh` bọc `claude -p` cho launchd. Mọi thứ ghi vào `output/director/<ngày>/`.

**Tech Stack:** Python 3.13 (`.venv` của repo, `uv run`), google-api-python-client (youtubeAnalytics v2, youtube v3), pytest, bash 3.2, launchd, Claude Code CLI (`claude -p`).

**Spec:** `docs/superpowers/specs/2026-11-28-daily-director-design.md`

## Global Constraints

- Không gọi YouTube/Analytics thật trong test (`tests/conftest.py` chặn); hàm nào gọi API phải nhận đối tượng dịch vụ qua tham số.
- Không đọc, in hay commit `.env`, `config/youtube_*.json`, `kit/.youtube_token_*.json`.
- Múi giờ kênh: `Asia/Ho_Chi_Minh` (+07:00); "ngày" của khóa và thư mục là ngày theo giờ này.
- Kênh chính id `UCeTcL2zuJ1wpeZ1d35onDWA` (khóa `main`), kênh phụ `UCHGq5frLQ39iR5ZR_VLgf0Q` (khóa `xomque`).
- Nhịp khởi điểm: main `AUDIOBOOK_RELEASE_WEEKDAYS` (hiện `2,6`), xomque biến mới `AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE` mặc định `0,3,5` (0 = Thứ Hai).
- Phiên Claude: `--dangerously-skip-permissions`, `--add-dir /Users/lee/Project/Apps/lemo`, `--max-turns 60` (sáng) / `120` (chiều), `--output-format text`; không phiên nào quá một giờ.
- Chế độ chỉ-báo-cáo: tồn tại tệp `output/director/CHI-BAO-CAO` thì phiên sáng không được gọi nhà máy.
- Commit tiếng Việt, kết bằng dòng `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; làm trên nhánh `feat/director-1` tách từ `feat/stickman-pipeline`, không `_transfer/`.

## Review Focus

1. Token kênh chính hết hạn (`invalid_grant`) lúc 08:00: `director.report` vẫn ghi so-lieu cho kênh còn lại và mục `loi` nêu "token main hỏng, chạy `uv run python -m upload.auth`"; không có traceback. (Test ở Task 3.)
2. Token kênh phụ thiếu quyền Analytics: báo cáo ghi "xomque chưa có quyền yt-analytics.readonly, chạy `kit/stick login xomque --force`" và vẫn liệt kê video hẹn giờ của kênh đó từ `da-dang.json`. (Test ở Task 3 và 4.)
3. Phiên chạy lúc 23:50 → 00:10 vắt qua nửa đêm: thư mục ngày và khóa lấy theo thời điểm bắt đầu, truyền vào mọi hàm; không gọi `date.today()` rải rác. (Test ở Task 1.)
4. `.env` thiếu biến nhịp hoặc ghi sai (`"a,9"`): dùng mặc định và ghi cảnh báo, không chết. (Test ở Task 4.)
5. `claude` không có trong PATH của launchd hoặc thoát mã khác 0: `director.sh` ghi log, gửi Telegram "phiên sáng hỏng, mã N" và thoát mã 1; không treo. (Test ở Task 6.)

---

### Task 1: Khung gói `director` và khóa một video mỗi ngày

**Files:**
- Create: `director/__init__.py`, `director/paths.py`, `director/lock.py`
- Test: `tests/director/__init__.py`, `tests/director/test_lock.py`

**Interfaces:**
- Produces: `director.paths.DIRECTOR_DIR: Path` (= `ROOT/output/director`), `director.paths.day_dir(day: date, base: Path = DIRECTOR_DIR) -> Path` (tạo `base/YYYY-MM-DD`), `director.paths.today(now: datetime | None = None) -> date` (giờ +07:00), `director.lock.acquire(day: date, base: Path = DIRECTOR_DIR) -> bool` (ghi `da-goi-nha-may` chứa ISO time; đã có thì False), `director.lock.is_locked(day, base) -> bool`, CLI `python -m director.lock [--check] [--date YYYY-MM-DD]` (mã 0 = vừa khóa / đang khóa với `--check`, 3 = chưa khóa khi `--check`).

- [ ] **Step 1: Viết test**

```python
def test_today_theo_gio_viet_nam():
    # 23:30 UTC ngày 27 là 06:30 ngày 28 giờ VN
    assert today(datetime(2026, 11, 27, 23, 30, tzinfo=timezone.utc)) == date(2026, 11, 28)

def test_acquire_chi_mot_lan(tmp_path):
    assert acquire(date(2026, 11, 28), tmp_path) is True
    assert acquire(date(2026, 11, 28), tmp_path) is False
    assert is_locked(date(2026, 11, 28), tmp_path) and not is_locked(date(2026, 11, 29), tmp_path)

def test_cli_check(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lock, "DIRECTOR_DIR", tmp_path)
    assert lock.main(["--check", "--date", "2026-11-28"]) == 3
    assert lock.main(["--date", "2026-11-28"]) == 0
    assert lock.main(["--check", "--date", "2026-11-28"]) == 0
```

- [ ] **Step 2: Chạy test, phải fail vì chưa có module**

Run: `uv run pytest tests/director/test_lock.py -v` → Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Viết `director/paths.py` và `director/lock.py` theo Interfaces**

`main(argv) -> int` dùng `argparse`; `__main__` gọi `sys.exit(main(sys.argv[1:]))`. Mặc định đường dẫn giải ở lúc gọi (`base = base or DIRECTOR_DIR`), không bind ở chữ ký (bài học conftest).

- [ ] **Step 4: Chạy test, phải pass**

Run: `uv run pytest tests/director -v` → Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add director tests/director
git commit -m "feat(director): khung gói và khóa một video mỗi ngày"
```

### Task 2: Sổ thay đổi cấu hình

**Files:**
- Create: `director/changelog.py`
- Test: `tests/director/test_changelog.py`

**Interfaces:**
- Produces: `director.changelog.record(file: str, reason: str, old: str, new: str, *, now: datetime | None = None, log: Path | None = None) -> str` (dòng vừa ghi; mặc định `DIRECTOR_DIR/thay-doi.log`; định dạng một dòng TSV: `ISO-time \t file \t reason \t old \t new`, xuống dòng trong old/new thay bằng `\\n`), CLI `python -m director.changelog --file F --reason R --old O --new N`.

- [ ] **Step 1: Viết test**

```python
def test_record_ghi_mot_dong_tsv(tmp_path):
    line = record("config/keywords.yaml", "thêm hạt giống", "", "mẹ kế\nvay tiền", now=datetime(2026,11,28,8,0,tzinfo=VN), log=tmp_path/"l.log")
    assert line.split("\t") == ["2026-11-28T08:00:00+07:00", "config/keywords.yaml", "thêm hạt giống", "", "mẹ kế\\nvay tiền"]
    assert (tmp_path/"l.log").read_text(encoding="utf-8") == line + "\n"
```

- [ ] **Step 2: Chạy test, fail** → `uv run pytest tests/director/test_changelog.py -v`
- [ ] **Step 3: Viết `director/changelog.py`** (append, tạo thư mục nếu thiếu)
- [ ] **Step 4: Chạy test, pass**
- [ ] **Step 5: Commit** `git commit -m "feat(director): sổ thay đổi cấu hình"`

### Task 3: Kéo số liệu Analytics hai kênh

**Files:**
- Create: `director/report.py`
- Test: `tests/director/test_report.py`

**Interfaces:**
- Consumes: `upload.auth.load_credentials()`, `upload.auth.has_scope(ANALYTICS_SCOPE)`, `upload.release.load_index()` (video kênh chính), `kit/login.py` `credentials("xomque")` (nạp bằng `sys.path.insert(0, STICK_KIT)` với `STICK_KIT = os.environ.get("STICK_KIT") or ROOT.parent / "lemo/stickman/kit"`), `da-dang.json` của kênh phụ (`glob("*/upload/xomque/da-dang.json")` trong `STICK_KIT.parent`).
- Produces:
  - `director.report.ChannelData = dict` với khóa: `channel`, `videos: list[dict]` (mỗi video: `video_id, title, published_at, views_7d, minutes_7d, avg_view_seconds_7d, avg_view_pct_7d, views_28d, subs_28d, traffic_7d: dict[str,int]`), `totals_7d`, `totals_28d`, `loi: list[str]`.
  - `fetch_channel(analytics, channel: str, video_ids: list[str], end: date, *, days7: int = 7, days28: int = 28) -> ChannelData` (analytics = đối tượng có `.reports().query(**kw).execute()`; gộp theo `dimensions="video"` và `insightTrafficSourceType`, lọc `video==id1,id2,...` theo lô 50).
  - `credentials_for(channel: str)` → `google.oauth2.credentials.Credentials` hoặc raise `ReportError(msg)` với câu chỉ cách sửa đúng như Review Focus 1–2.
  - `video_ids_for(channel: str) -> list[tuple[str, str]]` (id, title) từ index.jsonl (main) hoặc da-dang.json (xomque).
  - `render_markdown(data: list[ChannelData], end: date) -> str` (bảng mỗi kênh: 10 video mới nhất, tổng 7/28 ngày, mục Lỗi).
  - `main(argv) -> int`: `--date`, `--out DIR` (mặc định `day_dir(today())`); ghi `so-lieu.json`, `so-lieu.md`; in `Số liệu: <path>`; mã 0 kể cả khi một kênh lỗi (lỗi nằm trong `loi`), mã 1 chỉ khi không ghi được tệp.

- [ ] **Step 1: Viết test với analytics giả**

```python
class FakeAnalytics:  # trả hàng theo metrics/dimensions truyền vào
    def __init__(self, rows): self.rows = rows; self.calls = []
    def reports(self): return self
    def query(self, **kw): self.calls.append(kw); return self
    def execute(self): return {"rows": self.rows}

def test_fetch_channel_gop_7_va_28_ngay():
    fa = FakeAnalytics([["abc", 10, 55.0, 130.0, 41.5, 2]])
    d = fetch_channel(fa, "main", ["abc"], end=date(2026, 11, 27))
    v = d["videos"][0]
    assert v["video_id"] == "abc" and v["views_7d"] == 10 and v["avg_view_seconds_7d"] == 130.0
    assert any(c["startDate"] == "2026-11-20" for c in fa.calls) and any(c["startDate"] == "2026-10-30" for c in fa.calls)

def test_credentials_for_main_thieu_quyen_analytics(monkeypatch):
    monkeypatch.setattr(report, "has_scope", lambda s: False)
    with pytest.raises(ReportError, match="upload.auth"):
        credentials_for("main")

def test_main_mot_kenh_hong_van_ghi_file(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "credentials_for", lambda ch: (_ for _ in ()).throw(ReportError("token main hỏng")) if ch == "main" else object())
    monkeypatch.setattr(report, "build_analytics", lambda creds: FakeAnalytics([]))
    monkeypatch.setattr(report, "video_ids_for", lambda ch: [])
    assert report.main(["--date", "2026-11-28", "--out", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "so-lieu.json").read_text(encoding="utf-8"))
    assert "token main hỏng" in data[0]["loi"][0] and data[1]["channel"] == "xomque"
```

- [ ] **Step 2: Chạy test, fail**
- [ ] **Step 3: Viết `director/report.py`** theo Interfaces; `build_analytics(creds)` = `googleapiclient.discovery.build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)`; metrics 7 ngày: `views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained`; 28 ngày: `views,subscribersGained`; nguồn xem: `dimensions="video,insightTrafficSourceType"`.
- [ ] **Step 4: Chạy test, pass**: `uv run pytest tests/director -v`
- [ ] **Step 5: Chạy thật một lần (không trong test)**: `uv run python -m director.report --out /tmp/claude-501/.../scratchpad/dir-thu` → Expected: in `Số liệu: …/so-lieu.md`; kênh xomque có dòng lỗi thiếu quyền (chưa đăng nhập lại), kênh main có số. Không dán số vào commit.
- [ ] **Step 6: Commit** `git commit -m "feat(director): kéo số liệu Analytics hai kênh"`

### Task 4: Trạng thái kênh: tối trống, nhịp, bàn giao

**Files:**
- Create: `director/state.py`
- Test: `tests/director/test_state.py`

**Interfaces:**
- Consumes: `upload.release.load_index`, `upload.uploader.list_status(credentials, video_ids: list[str]) -> dict[str, dict]` (status từng video theo id), `director.report.credentials_for`, `video_ids_for`.
- Produces:
  - `channel_weekdays(channel: str, env: Mapping[str, str] | None = None) -> set[int]` (main: `AUDIOBOOK_RELEASE_WEEKDAYS`, xomque: `AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE`; sai/thiếu → mặc định `{2,6}` / `{0,3,5}` và trả thêm cảnh báo qua `warnings: list[str]` tham số tùy chọn).
  - `taken_evenings(statuses: dict[str, dict]) -> set[date]` (video `private` có `publishAt` → ngày giờ VN).
  - `next_free_evening(channel: str, taken: set[date], now: datetime, weekdays: set[int], window_days: int = 7, hour: int = 20) -> datetime | None` (tối gần nhất ≥ hôm nay 20:00 nếu `now` trước 18:00, không thì từ mai; đúng thứ; chưa bị chiếm; None nếu hết cửa sổ).
  - `State = dict`: `{"cap_nhat": iso, "kenh": {"main": {"toi_da_chiem": [...], "toi_trong_ke_tiep": iso|None, "nhip": [..]}, "xomque": {...}}, "lan_cuoi": {"kenh": str|None, "ngay": iso|None}, "thu_nghiem": [], "ban_giao": {}}`.
  - `refresh(now: datetime, *, youtube_for: Callable[[str], Any], env=None) -> State` (youtube_for(channel) trả dịch vụ v3; lỗi từng kênh ghi `loi` trong mục kênh đó), `load(path=None) -> State`, `save(state, path=None)`; CLI `python -m director.state --refresh | --show`, in `Trạng thái: <path>`.

- [ ] **Step 1: Viết test**

```python
def test_channel_weekdays_sai_thi_mac_dinh():
    w = []
    assert channel_weekdays("xomque", {"AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE": "a,9"}, warnings=w) == {0, 3, 5} and w

def test_next_free_evening_bo_qua_toi_da_chiem():
    now = datetime(2026, 11, 28, 8, 0, tzinfo=VN)           # thứ Bảy
    taken = {date(2026, 11, 28)}
    assert next_free_evening("xomque", taken, now, {0, 3, 5}) == datetime(2026, 11, 30, 20, 0, tzinfo=VN)

def test_next_free_evening_sau_18h_khong_lay_hom_nay():
    now = datetime(2026, 11, 28, 18, 30, tzinfo=VN)
    assert next_free_evening("xomque", set(), now, {5}).date() == date(2026, 12, 5)

def test_refresh_kenh_hong_van_co_kenh_kia(monkeypatch):
    def yt(ch):
        if ch == "main": raise RuntimeError("invalid_grant")
        return FakeYouTube({"v1": {"privacyStatus": "private", "publishAt": "2026-11-29T13:00:00Z"}})
    monkeypatch.setattr(state, "video_ids_for", lambda ch: [("v1", "t")])
    s = refresh(datetime(2026, 11, 28, 8, 0, tzinfo=VN), youtube_for=yt)
    assert "invalid_grant" in s["kenh"]["main"]["loi"][0]
    assert s["kenh"]["xomque"]["toi_da_chiem"] == ["2026-11-29"]
```

- [ ] **Step 2: Chạy test, fail**
- [ ] **Step 3: Viết `director/state.py`**; `FakeYouTube` trong test chỉ cần `videos().list(part, id).execute()` → `{"items": [{"id", "status"}]}`.
- [ ] **Step 4: Chạy test, pass**
- [ ] **Step 5: Commit** `git commit -m "feat(director): trạng thái kênh, tối trống và nhịp từng kênh"`

### Task 5: Token kênh phụ xin thêm quyền Analytics

**Files:**
- Modify: `/Users/lee/Project/Apps/lemo/stickman/kit/login.py` (`SCOPES`, docstring, `--check`)
- Test: chạy tay (kit không có test; không gọi API trong test của repo audiobook)

**Interfaces:**
- Produces: `SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl", "https://www.googleapis.com/auth/yt-analytics.readonly"]`; `kit/stick login xomque --check` in "thiếu quyền: yt-analytics.readonly → chạy kit/stick login xomque --force" khi token cũ thiếu; `credentials(key)` nạp token cũ vẫn chạy được cho Data API (không bắt phải có đủ scope khi chỉ đăng video).

- [ ] **Step 1: Sửa `SCOPES` và `--check`** (đối chiếu `granted` với `SCOPES`, in từng scope thiếu).
- [ ] **Step 2: Kiểm tay**: `cd /Users/lee/Project/Apps/lemo/stickman && kit/stick login xomque --check` → Expected: in thiếu `yt-analytics.readonly` (token hiện chỉ có force-ssl), mã thoát 1, KHÔNG mở trình duyệt.
- [ ] **Step 3: Ghi vào báo cáo cho người dùng**: việc cần họ làm là `kit/stick login xomque --force` (bấm đồng ý cả quyền Analytics). Không tự chạy.

### Task 6: Skill `channel-director` và `scripts/director.sh`

**Files:**
- Create: `.claude/skills/channel-director/SKILL.md`, `.claude/skills/channel-director/prompt-sang.md`, `.claude/skills/channel-director/prompt-chieu.md`, `scripts/director.sh`
- Test: `tests/test_director_sh.py`, `tests/fake_claude.sh`

**Interfaces:**
- Consumes: Task 1–4 CLI (`python -m director.report`, `python -m director.state --refresh`, `python -m director.lock --check`), `notify.cli text --text`.
- Produces: `scripts/director.sh sang|chieu` → chạy `caffeinate -i claude -p "$(cat <prompt>)" --dangerously-skip-permissions --add-dir /Users/lee/Project/Apps/lemo --max-turns <60|120> --output-format text` từ `REPO_ROOT`, ghi `output/director/<ngày>/claude-<sang|chieu>.log`, mã thoát của claude; `CLAUDE_BIN` (mặc định tìm trong PATH, rồi `$HOME/.local/bin/claude`, `/opt/homebrew/bin/claude`); nạp nvm/PATH như `run_daily.sh`; khi claude thiếu hoặc mã ≠ 0: gửi `notify.cli text --text "Phiên <sang|chieu> hỏng, mã N, xem <log>"` và thoát 1.
- Nội dung `prompt-sang.md` (thứ tự bắt buộc, tiếng Việt): 1) `uv run python -m director.report` và `--state --refresh`, đọc hai tệp ra; 2) viết `quyet-dinh.json` theo lược đồ `{"ngay", "kenh": "main|xomque|nghi", "ly_do", "toi_phat": iso|null, "truyen": {"id": int|null, "phrase": str|null}, "brief": {"huong_ke": str, "luat_tieu_de": str, "luat_bia": str}, "viec_can_nguoi_dung": [..]}`; 3) nếu có tệp `output/director/CHI-BAO-CAO` HOẶC `kenh == "nghi"` thì KHÔNG gọi nhà máy; ngược lại (đợt 2 mới bật) gọi `python -m director.lock` rồi `run_daily.sh` nền; 4) viết `bao-cao-sang.md` và gửi Telegram ≤ 10 dòng bằng `uv run python -m notify.cli text --text "..."`. Rào cản chép từ spec mục "Rào cản" (không xóa, không `--allow-second`, không đổi cài đặt kênh, chỉ sửa tệp trong danh sách, commit `director:`). Thứ Hai: mục "Kiểm kênh tuần" ghi "đợt 5 mới làm".
- Nội dung `prompt-chieu.md`: đọc `quyet-dinh.json`; nếu không có nhà máy hôm nay → ghi `bao-cao.md` "nghỉ" và thoát; ngược lại (đợt 2) làm theo spec bước 5–7. Trong đợt 1 nêu rõ là chưa có việc.
- `SKILL.md`: mô tả, khi nào dùng, sơ đồ hai phiên, đường dẫn tệp, lược đồ JSON, rào cản, cách kiểm tay (`scripts/director.sh sang` rồi đọc log).

- [ ] **Step 1: Viết `tests/fake_claude.sh`** (ghi toàn bộ tham số vào `$FAKE_CLAUDE_LOG`, in "fake ok", thoát theo `$FAKE_CLAUDE_EXIT` mặc định 0) và test:

```python
def test_director_sh_goi_claude_dung_tham_so(tmp_path, monkeypatch):
    env = {**os.environ, "PATH": f"{FAKE_BIN}:{os.environ['PATH']}", "FAKE_CLAUDE_LOG": str(tmp_path/"args"), "DIRECTOR_OUT": str(tmp_path), "DIRECTOR_NO_CAFFEINATE": "1"}
    r = subprocess.run(["bash", "scripts/director.sh", "sang"], cwd=ROOT, env=env, capture_output=True, text=True)
    args = (tmp_path/"args").read_text()
    assert r.returncode == 0 and "--dangerously-skip-permissions" in args and "--max-turns 60" in args and "--add-dir /Users/lee/Project/Apps/lemo" in args
    assert "director.report" in args          # prompt sáng được nhúng
    assert (tmp_path / date.today().isoformat() / "claude-sang.log").exists()

def test_director_sh_claude_loi_thi_bao_telegram(tmp_path):
    env = {..., "FAKE_CLAUDE_EXIT": "2", "DIRECTOR_NOTIFY": str(tmp_path/"notify")}   # director.sh ghi lệnh notify vào tệp này thay vì gọi thật khi biến có
    r = subprocess.run(["bash", "scripts/director.sh", "chieu"], ...)
    assert r.returncode == 1 and "mã 2" in (tmp_path/"notify").read_text()
```

- [ ] **Step 2: Chạy test, fail**
- [ ] **Step 3: Viết `scripts/director.sh`** (bash 3.2, `set -u`, `DIRECTOR_OUT` mặc định `output/director`, `DIRECTOR_NO_CAFFEINATE` bỏ caffeinate trong test, `DIRECTOR_NOTIFY` ghi lệnh thay vì gọi) và ba tệp skill.
- [ ] **Step 4: Chạy test, pass**: `uv run pytest tests/test_director_sh.py -v`
- [ ] **Step 5: Chạy thật chế độ chỉ-báo-cáo**: `touch output/director/CHI-BAO-CAO && bash scripts/director.sh sang` → Expected: `output/director/<hôm nay>/{so-lieu.md,quyet-dinh.json,bao-cao-sang.md,claude-sang.log}` có nội dung; Telegram nhận một tin; không có `da-goi-nha-may`. Đọc `bao-cao-sang.md` và sửa prompt nếu nội dung lệch.
- [ ] **Step 6: Commit** `git commit -m "feat(director): skill channel-director hai phiên và scripts/director.sh"`

### Task 7: launchd hai phiên và lượt dự phòng 10:30

**Files:**
- Create: `launchd/com.lee.channel.director-sang.plist` (08:00), `launchd/com.lee.channel.director-chieu.plist` (17:30), `scripts/daily_fallback.sh`
- Modify: `launchd/com.lee.audiobook.daily.plist` (09:00 → 10:30, chạy `scripts/daily_fallback.sh`), `docs/DAILY_AUTOMATION.md` (mục mới "Giám đốc kênh"), `.env.example` (`AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE`)
- Test: `tests/test_daily_fallback.py` (chạy `scripts/daily_fallback.sh` với `RUN_DAILY` giả trỏ tới `tests/fake_stage.sh`-kiểu script ghi tham số)

**Interfaces:**
- Produces: `scripts/daily_fallback.sh`: thoát 0 không làm gì nếu `python -m director.lock --check` trả 0 (đã gọi nhà máy) HOẶC hôm nay không thuộc `AUDIOBOOK_RELEASE_WEEKDAYS`; ngược lại `python -m director.lock` rồi `run_daily.sh --upload` (biến `RUN_DAILY` để test thay bằng script giả).

- [ ] **Step 1: Viết test**: (a) có khóa → không gọi run_daily; (b) không khóa, đúng thứ → gọi với `--upload` và tạo khóa; (c) sai thứ → không gọi.
- [ ] **Step 2: Chạy test, fail**
- [ ] **Step 3: Viết script và plist** (plist sao chép khuôn của `com.lee.audiobook.daily.plist`: caffeinate, WorkingDirectory, log riêng `output/director/launchd-<sang|chieu>.{out,err}.log`, LANG/LC_ALL).
- [ ] **Step 4: Chạy test, pass**; `plutil -lint launchd/*.plist` → OK.
- [ ] **Step 5: Cài lịch (cần người dùng hoặc quyền hệ thống)**: ghi vào `docs/DAILY_AUTOMATION.md` ba lệnh:

```bash
launchctl unload ~/Library/LaunchAgents/com.lee.audiobook.shorts.plist
cp launchd/com.lee.audiobook.daily.plist launchd/com.lee.channel.director-*.plist ~/Library/LaunchAgents/ && launchctl unload ~/Library/LaunchAgents/com.lee.audiobook.daily.plist; launchctl load ~/Library/LaunchAgents/com.lee.audiobook.daily.plist ~/Library/LaunchAgents/com.lee.channel.director-sang.plist ~/Library/LaunchAgents/com.lee.channel.director-chieu.plist
launchctl list | grep com.lee
```

Chạy nếu được phép; bị từ chối thì để người dùng chạy và ghi rõ trong báo cáo cuối.
- [ ] **Step 6: Commit** `git commit -m "feat(director): launchd hai phiên và lượt dự phòng 10:30"`

### Task 8: Hai ngày chỉ-báo-cáo, PR

**Files:**
- Modify: `.claude/skills/generating-audiobook-video/SKILL.md` (một đoạn trỏ sang `channel-director`), bộ nhớ dự án (`memory/stickman-pipeline-2711.md` hoặc tệp mới `director-dot-1.md`)

- [ ] **Step 1: Đảm bảo `output/director/CHI-BAO-CAO` tồn tại** (đợt 1 luôn chỉ báo cáo).
- [ ] **Step 2: Chạy toàn bộ test**: `uv run pytest -q` → Expected: tất cả pass (hiện 845 + mới).
- [ ] **Step 3: Push và mở PR** `feat/director-1` ← `feat/stickman-pipeline`, mô tả: mục tiêu, cách kiểm (đọc `output/director/<ngày>/bao-cao-sang.md` hai sáng liên tiếp), việc cần người dùng (đăng nhập lại kênh phụ với quyền Analytics; nạp launchd nếu chưa), kết bằng `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Không merge.
- [ ] **Step 4: Sau hai sáng**: đọc hai `bao-cao-sang.md`, ghi nhận xét vào PR (số có đúng không, quyết định có hợp lý không) trước khi lập kế hoạch đợt 2.
