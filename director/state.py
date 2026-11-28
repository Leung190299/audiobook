"""Trạng thái hai kênh cho giám đốc: tối đã chiếm, tối trống kế tiếp, nhịp từng kênh, lần đăng gần nhất, sổ thử nghiệm, bàn giao sáng→chiều.

    python -m director.state --refresh      đọc API hai kênh, ghi output/director/trang-thai.json, in "Trạng thái: <path>"
    python -m director.state --show         in tệp hiện có
Lỗi của một kênh (token hỏng) chỉ nằm trong mục "loi" của kênh đó; kênh kia vẫn được cập nhật.
Nhịp: main đọc AUDIOBOOK_RELEASE_WEEKDAYS (mặc định 2,6), xomque đọc AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE (mặc định 0,3,5); 0 = Thứ Hai.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from director import paths
from director.report import credentials_for, video_ids_for

STATE_NAME = "trang-thai.json"
DEFAULT_WEEKDAYS = {"main": {2, 6}, "xomque": {0, 3, 5}}
ENV_VAR = {"main": "AUDIOBOOK_RELEASE_WEEKDAYS", "xomque": "AUDIOBOOK_RELEASE_WEEKDAYS_XOMQUE"}
PUBLISH_HOUR = 20
LAST_START_HOUR = 18          # sau giờ này không lấy tối hôm nay nữa (video chưa kịp dựng/đăng)
WINDOW_DAYS = 7
State = dict


def _env() -> Mapping[str, str]:
    try:
        from dotenv import dotenv_values
        return {**dotenv_values(paths.ROOT / ".env"), **os.environ}
    except ImportError:
        return os.environ


def channel_weekdays(channel: str, env: Mapping[str, str] | None = None, warnings: list[str] | None = None) -> set[int]:
    env = _env() if env is None else env
    raw = (env.get(ENV_VAR[channel]) or "").strip()
    if not raw:
        return set(DEFAULT_WEEKDAYS[channel])
    try:
        days = {int(x) for x in raw.split(",") if x.strip()}
        if not days or not days <= set(range(7)):
            raise ValueError(raw)
        return days
    except ValueError:
        if warnings is not None:
            warnings.append(f"{ENV_VAR[channel]}={raw!r} không hợp lệ, dùng mặc định {sorted(DEFAULT_WEEKDAYS[channel])}")
        return set(DEFAULT_WEEKDAYS[channel])


def taken_evenings(statuses: Mapping[str, Mapping[str, Any]]) -> set[date]:
    """Ngày (giờ VN) của các video riêng tư đã hẹn công khai."""
    out = set()
    for st in statuses.values():
        if st.get("privacyStatus") == "private" and st.get("publishAt"):
            out.add(datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00")).astimezone(paths.VN).date())
    return out


def next_free_evening(channel: str, taken: set[date], now: datetime, weekdays: set[int], window_days: int = WINDOW_DAYS,
                      hour: int = PUBLISH_HOUR) -> datetime | None:
    now = now.astimezone(paths.VN)
    start = now.date() if now.hour < LAST_START_HOUR else now.date() + timedelta(days=1)
    for i in range(window_days + 1):
        d = start + timedelta(days=i)
        if d > now.date() + timedelta(days=window_days):
            break
        if d.weekday() in weekdays and d not in taken:
            return datetime(d.year, d.month, d.day, hour, 0, tzinfo=paths.VN)
    return None


def _statuses(youtube, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        resp = youtube.videos().list(part="status", id=",".join(ids[i:i + 50])).execute()
        for it in resp.get("items", []):
            out[it["id"]] = it.get("status", {})
    return out


def default_youtube_for(channel: str):
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=credentials_for(channel), cache_discovery=False)


def empty_state() -> State:
    return {"cap_nhat": None, "kenh": {}, "lan_cuoi": {"kenh": None, "ngay": None}, "thu_nghiem": [], "ban_giao": {}}


def refresh(now: datetime, *, youtube_for: Callable[[str], Any] = default_youtube_for, env: Mapping[str, str] | None = None,
            previous: State | None = None) -> State:
    s = previous or empty_state()
    s.setdefault("thu_nghiem", []); s.setdefault("ban_giao", {}); s.setdefault("lan_cuoi", {"kenh": None, "ngay": None})
    s["cap_nhat"] = now.astimezone(paths.VN).isoformat(timespec="seconds")
    s["kenh"] = {}
    for channel in ("main", "xomque"):
        warn: list[str] = []
        weekdays = channel_weekdays(channel, env, warnings=warn)
        k = {"nhip": sorted(weekdays), "toi_da_chiem": [], "toi_trong_ke_tiep": None, "so_video": 0, "loi": list(warn)}
        try:
            ids = [v for v, _ in video_ids_for(channel)]
            k["so_video"] = len(ids)
            taken = taken_evenings(_statuses(youtube_for(channel), ids)) if ids else set()
        except Exception as exc:
            k["loi"].append(f"{type(exc).__name__}: {str(exc)[:160]}")
            taken = set()
        k["toi_da_chiem"] = [d.isoformat() for d in sorted(taken)]
        nxt = next_free_evening(channel, taken, now, weekdays)
        k["toi_trong_ke_tiep"] = nxt.isoformat(timespec="seconds") if nxt else None
        s["kenh"][channel] = k
    return s


def state_path(path: Path | None = None) -> Path:
    return path or paths.DIRECTOR_DIR / STATE_NAME


def load(path: Path | None = None) -> State:
    p = state_path(path)
    if not p.exists():
        return empty_state()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_state()


def save(state: State, path: Path | None = None) -> Path:
    p = state_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Trạng thái hai kênh cho giám đốc kênh.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--refresh", action="store_true")
    g.add_argument("--show", action="store_true")
    ap.add_argument("--path", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.refresh:
        s = refresh(datetime.now(tz=paths.VN), previous=load(a.path))
        p = save(s, a.path)
        for ch, k in s["kenh"].items():
            print(f"{ch}: nhịp {k['nhip']}, tối đã chiếm {k['toi_da_chiem']}, tối trống kế tiếp {k['toi_trong_ke_tiep']}" + (f", lỗi: {k['loi']}" if k["loi"] else ""))
        print(f"Trạng thái: {p}")
        return 0
    print(json.dumps(load(a.path), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
