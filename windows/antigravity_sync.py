#!/usr/bin/env python3
"""Đồng bộ quota + trạng thái phiên Antigravity từ Windows lên Google Apps Script.

Chỉ đọc dữ liệu từ:
  1. Log phiên công khai của Antigravity tại ~/.gemini/antigravity/brain/*/.system_generated/logs/transcript.jsonl
  2. Antigravity CLI chính thức (%LOCALAPPDATA%\agy\bin\agy.exe -p "/usage" và "/credits"),
     hoặc file JSON ~/.kindle-dashboard-quota.json / lệnh AGY_QUOTA_CMD tuỳ chọn.
Tuyệt đối không dò cổng nội bộ hay đọc file credential/token của IDE.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("DASH_TZ", "Asia/Ho_Chi_Minh"))
BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"
QUOTA_FILE = Path.home() / ".kindle-dashboard-quota.json"
URL_FILE = Path.home() / ".kindle-dashboard-url"
LOG_FILE = Path(__file__).resolve().parent / "antigravity_sync.log"
QUOTA_KEYS = ("gemini", "claude", "gpt", "five_hour", "seven_day")


def _log(msg: str) -> None:
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    if LOG_FILE.exists():
        try:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
    lines.append(f"{now_str} {msg}")
    if len(lines) > 300:
        lines = lines[-300:]
    try:
        LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ)
    except ValueError:
        return None


def _clean_user_label(raw: str, session_id: str, redact: bool) -> str:
    fallback = f"Phiên #{session_id[:4]}"
    if redact or not raw:
        return fallback
    txt = raw
    m = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", txt, flags=re.DOTALL)
    if m:
        txt = m.group(1)
    # Loại bỏ các thẻ metadata nếu còn sót
    txt = re.sub(r"<[^>]+>.*?</[^>]+>", " ", txt, flags=re.DOTALL)
    txt = re.sub(r"<[^>]+>", " ", txt)
    # Loại bỏ URL và đường dẫn ổ đĩa để giữ gọn, tránh lộ cấu trúc máy
    txt = re.sub(r"https?://\S+", "", txt)
    txt = re.sub(r'"[^"]*[\\/][^"]*"', "", txt)
    txt = re.sub(r"[A-Za-z]:\\[^\s\"']*", "", txt)
    txt = re.sub(r"(?:^|\s)[/~][^\s\"']+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip(" .,:;-–—")
    if not txt:
        return fallback
    if len(txt) > 44:
        return txt[:43].rstrip() + "…"
    return txt


def collect_brain_activity(now: datetime | None = None, redact_titles: bool = False) -> dict:
    now = now or datetime.now(TZ)
    today = now.date()
    week_cutoff = now - timedelta(days=7)

    today_sessions = 0
    today_steps = 0
    week_steps = 0
    active_count = 0

    latest_dt: datetime | None = None
    latest_info: dict | None = None

    if not BRAIN_DIR.is_dir():
        return {
            "today_sessions": 0,
            "today_steps": 0,
            "week_steps": 0,
            "active_count": 0,
            "latest": None,
        }

    for session_dir in BRAIN_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        transcript = session_dir / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript.is_file():
            continue

        sess_has_today = False
        sess_last_dt: datetime | None = None
        sess_last_entry: dict | None = None
        first_user_text = ""

        try:
            with transcript.open("r", encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(entry, dict):
                        continue

                    dt = _parse_iso(entry.get("created_at"))
                    if dt is not None:
                        if dt.date() == today:
                            sess_has_today = True
                            today_steps += 1
                        if dt >= week_cutoff:
                            week_steps += 1
                        if sess_last_dt is None or dt >= sess_last_dt:
                            sess_last_dt = dt
                            sess_last_entry = entry

                    if not first_user_text and entry.get("type") == "USER_INPUT":
                        content = entry.get("content")
                        if isinstance(content, str) and content.strip():
                            first_user_text = content
        except OSError:
            continue

        if sess_has_today:
            today_sessions += 1

        if sess_last_dt is not None and sess_last_entry is not None:
            age_secs = (now - sess_last_dt).total_seconds()
            if age_secs <= 900:  # 15 phút gần nhất
                active_count += 1

            if latest_dt is None or sess_last_dt > latest_dt:
                latest_dt = sess_last_dt
                last_status_raw = str(sess_last_entry.get("status") or "").upper()
                last_type = str(sess_last_entry.get("type") or "").upper()
                has_tools = bool(sess_last_entry.get("tool_calls"))

                if last_status_raw == "ERROR":
                    status = "ERROR"
                elif age_secs < 600 and (last_type != "PLANNER_RESPONSE" or has_tools):
                    status = "RUNNING"
                else:
                    status = "DONE"

                latest_info = {
                    "label": _clean_user_label(first_user_text, session_dir.name, redact_titles),
                    "status": status,
                    "updated_at": sess_last_dt.isoformat(),
                }

    return {
        "today_sessions": today_sessions,
        "today_steps": today_steps,
        "week_steps": week_steps,
        "active_count": active_count,
        "latest": latest_info,
    }


def _normalize_quota_payload(raw: dict) -> tuple[dict, dict | None]:
    quotas: dict[str, dict] = {}
    src = raw.get("quotas") if isinstance(raw.get("quotas"), dict) else raw
    for k in QUOTA_KEYS:
        v = src.get(k) if isinstance(src, dict) else None
        if not isinstance(v, dict):
            v = raw.get(k)
        if isinstance(v, dict) and isinstance(v.get("utilization"), (int, float)):
            quotas[k] = {
                "utilization": float(v["utilization"]),
                "resets_at": v.get("resets_at") or None,
            }

    credits_obj = None
    c = raw.get("credits")
    if isinstance(c, dict) and isinstance(c.get("remaining"), (int, float)):
        credits_obj = {
            "remaining": int(round(c["remaining"])),
            "limit": int(round(c["limit"])) if isinstance(c.get("limit"), (int, float)) else None,
        }
    return quotas, credits_obj


def _find_agy_cli() -> Path | None:
    """Tìm file thực thi agy.exe chính thức (tránh agy.cmd mở cửa sổ IDE GUI)."""
    custom = os.environ.get("AGY_CLI_BIN", "").strip()
    candidate = (
        Path(custom)
        if custom
        else Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "agy" / "bin" / "agy.exe"
    )
    if candidate.is_file() and candidate.name.lower() == "agy.exe":
        return candidate
    return None


def _run_agy_slash(agy_exe: Path, slash_cmd: str) -> dict | None:
    """Gọi lệnh slash không tương tác của agy.exe, không bật cửa sổ console và bỏ qua hooks."""
    try:
        proc = subprocess.run(
            [str(agy_exe), "--settings", "{}", "-p", slash_cmd, "--output-format", "json", "--print-timeout", "15s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        parsed = json.loads(proc.stdout.strip())
        if isinstance(parsed, dict) and parsed.get("status") == "SUCCESS" and isinstance(parsed.get("command"), dict):
            data = parsed["command"].get("data")
            return data if isinstance(data, dict) else None
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        pass
    return None


def _map_agy_bucket_key(bucket_id: str, window: str, group_name: str) -> str | None:
    bid = bucket_id.lower()
    win = window.lower()
    gname = group_name.lower()
    if bid == "gemini-5h" or ("gemini" in gname and win == "5h"):
        return "five_hour"
    if bid == "gemini-weekly" or ("gemini" in gname and win == "weekly"):
        return "gemini"
    if bid == "3p-5h" or (("claude" in gname or "gpt" in gname) and win == "5h"):
        return "seven_day"
    if bid == "3p-weekly" or (("claude" in gname or "gpt" in gname) and win == "weekly"):
        return "claude"
    return None


def collect_agy_cli_quotas(now: datetime | None = None) -> tuple[dict, dict | None]:
    """Lấy quota 5 giờ / tuần và credits từ agy.exe -p '/usage' & '/credits'."""
    agy_exe = _find_agy_cli()
    if not agy_exe:
        return {}, None

    quotas: dict[str, dict] = {}
    credits_obj: dict | None = None

    usage_data = _run_agy_slash(agy_exe, "/usage")
    groups = usage_data.get("groups") if isinstance(usage_data, dict) else None
    if isinstance(groups, list):
        for g in groups:
            if not isinstance(g, dict):
                continue
            gname = str(g.get("name") or "")
            buckets = g.get("buckets")
            if not isinstance(buckets, list):
                continue
            for b in buckets:
                if not isinstance(b, dict):
                    continue
                key = _map_agy_bucket_key(str(b.get("id") or ""), str(b.get("window") or ""), gname)
                rem_frac = b.get("remaining_fraction")
                if key and isinstance(rem_frac, (int, float)):
                    clamped = max(0.0, min(1.0, float(rem_frac)))
                    quotas[key] = {
                        "utilization": round((1.0 - clamped) * 100.0, 1),
                        "resets_at": b.get("reset_time") or None,
                    }

    credits_data = _run_agy_slash(agy_exe, "/credits")
    if isinstance(credits_data, dict) and isinstance(credits_data.get("remaining_credits"), (int, float)):
        credits_obj = {
            "remaining": int(round(credits_data["remaining_credits"])),
            "limit": None,
        }

    if quotas:
        cache_payload = {
            "source": "agy_cli",
            "fetched_at": (now or datetime.now(TZ)).isoformat(),
            "quotas": quotas,
            "credits": credits_obj,
        }
        try:
            QUOTA_FILE.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    return quotas, credits_obj


def collect_quotas(now: datetime | None = None) -> tuple[dict, dict | None]:
    now = now or datetime.now(TZ)
    raw: dict = {}
    cmd = os.environ.get("AGY_QUOTA_CMD", "").strip()
    if cmd:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0 and proc.stdout.strip():
                parsed = json.loads(proc.stdout)
                if isinstance(parsed, dict):
                    raw = parsed
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            pass
        if raw:
            return _normalize_quota_payload(raw)

    cli_quotas, cli_credits = collect_agy_cli_quotas(now=now)
    if cli_quotas:
        return cli_quotas, cli_credits

    if QUOTA_FILE.is_file():
        try:
            parsed = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                if parsed.get("source") == "agy_cli":
                    ft = _parse_iso(parsed.get("fetched_at"))
                    if ft is not None and (now - ft).total_seconds() <= 6 * 3600:
                        raw = parsed
                else:
                    raw = parsed
        except (OSError, json.JSONDecodeError):
            pass

    quotas, credits_obj = _normalize_quota_payload(raw)
    if credits_obj is None and cli_credits is not None:
        credits_obj = cli_credits
    return quotas, credits_obj


def save_manual_quota(items: list[str], reset_hours: float | None) -> None:
    data: dict = {"quotas": {}, "credits": None}
    if QUOTA_FILE.is_file():
        try:
            existing = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                if isinstance(existing.get("quotas"), dict):
                    data["quotas"] = existing["quotas"]
                if isinstance(existing.get("credits"), dict):
                    data["credits"] = existing["credits"]
        except (OSError, json.JSONDecodeError):
            pass

    reset_iso = None
    if reset_hours is not None:
        reset_iso = (datetime.now(TZ) + timedelta(hours=reset_hours)).isoformat()

    for item in items:
        if "=" not in item:
            raise SystemExit(f"Sai định dạng '{item}'. Hãy dùng key=value, ví dụ gemini=32 credits=420")
        k, val_str = item.split("=", 1)
        k = k.strip().lower()
        try:
            val = float(val_str.strip())
        except ValueError:
            raise SystemExit(f"Giá trị không phải số: '{item}'")
        if k == "credits":
            data["credits"] = {"remaining": int(round(val)), "limit": None}
        elif k in QUOTA_KEYS:
            prev_reset = (data["quotas"].get(k) or {}).get("resets_at")
            data["quotas"][k] = {
                "utilization": max(0.0, min(100.0, val)),
                "resets_at": reset_iso if reset_iso is not None else prev_reset,
            }
        else:
            raise SystemExit(f"Khoá không hỗ trợ '{k}'. Chọn trong: {', '.join(QUOTA_KEYS)}, credits")

    QUOTA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã lưu quota vào {QUOTA_FILE}")


def build_payload(redact_titles: bool = False) -> dict:
    now = datetime.now(TZ)
    quotas, credits_obj = collect_quotas(now=now)
    activity = collect_brain_activity(now=now, redact_titles=redact_titles)
    return {
        "fetched_at": now.isoformat(),
        "quotas": quotas,
        "credits": credits_obj,
        "activity": activity,
    }


def read_data_url() -> str:
    url = os.environ.get("DATA_URL", "").strip()
    if not url and URL_FILE.is_file():
        url = URL_FILE.read_text(encoding="utf-8-sig", errors="replace").strip()
    return url


def _find_gh_cli() -> str | None:
    found = shutil.which("gh")
    if found:
        return found
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "GitHub CLI" / "gh.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHub CLI" / "gh.exe",
    ]
    for c in candidates:
        if str(c) and c.is_file():
            return str(c)
    return None


def _detect_github_repo() -> str | None:
    env_repo = os.environ.get("DASH_GH_REPO", "").strip()
    if env_repo:
        return env_repo
    git_cfg = Path(__file__).resolve().parent.parent / ".git" / "config"
    if git_cfg.is_file():
        try:
            txt = git_cfg.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?(?:\s|$)", txt)
            if m:
                return m.group(1).strip()
        except OSError:
            pass
    return None


def trigger_github_workflow() -> str:
    """Kích hoạt ngay workflow update.yml trên GitHub để không bị trễ bởi GitHub cron."""
    if os.environ.get("DASH_TRIGGER_GH", "1").strip().lower() in ("0", "false", "no"):
        return "skip"
    gh_exe = _find_gh_cli()
    if not gh_exe:
        return "no_gh"
    repo_slug = _detect_github_repo()
    if not repo_slug:
        return "no_repo"
    try:
        proc = subprocess.run(
            [gh_exe, "workflow", "run", "update.yml", "-R", repo_slug],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0:
            return "ok"
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        short_err = err[0][:80] if err else f"rc={proc.returncode}"
        return f"err({short_err})"
    except subprocess.SubprocessError as exc:
        return f"err({type(exc).__name__})"


def main() -> int:
    ap = argparse.ArgumentParser(description="Đồng bộ trạng thái Antigravity lên Kindle Dashboard")
    ap.add_argument("--dry-run", action="store_true", help="In JSON ra màn hình, không gửi lên Apps Script")
    ap.add_argument("--write-local", help="Ghi JSON ra file cục bộ để kiểm thử render.py")
    ap.add_argument("--redact-titles", action="store_true", help="Ẩn tên yêu cầu người dùng, chỉ hiện mã phiên")
    ap.add_argument("--no-trigger-gh", action="store_true", help="Không gọi gh workflow run sau khi gửi Apps Script")
    ap.add_argument(
        "--set-quota",
        nargs="+",
        metavar="KEY=VAL",
        help="Cập nhật nhanh file ~/.kindle-dashboard-quota.json (vd: gemini=32 claude=58 gpt=15 credits=420)",
    )
    ap.add_argument("--reset-hours", type=float, default=None, help="Đặt thời điểm reset sau N giờ cho --set-quota")
    args = ap.parse_args()

    if args.set_quota:
        save_manual_quota(args.set_quota, args.reset_hours)
        if not args.dry_run and not args.write_local:
            return 0

    payload = build_payload(redact_titles=args.redact_titles)

    if args.write_local:
        out_path = Path(args.write_local)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Đã ghi payload cục bộ: {out_path}")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.write_local and not read_data_url():
        return 0

    data_url = read_data_url()
    if not data_url:
        msg = f"Thiếu DATA_URL (chưa có file {URL_FILE} hoặc biến môi trường DATA_URL)"
        _log(msg)
        print(msg, file=sys.stderr)
        return 1

    import requests

    try:
        r = requests.post(data_url, json=payload, timeout=30)
        r.raise_for_status()
        body = r.text.strip()
        if '"ok":true' in body or '"ok": true' in body:
            gh_state = "skip" if args.no_trigger_gh else trigger_github_workflow()
            act = payload["activity"]
            _log(
                f"OK sessions={act['today_sessions']} steps={act['today_steps']} "
                f"quotas={list(payload['quotas'].keys())} gh_dispatch={gh_state}"
            )
            print(f"Đã đồng bộ Antigravity lên Apps Script (gh_dispatch={gh_state}).")
            return 0
        _log(f"Apps Script phản hồi lạ: {body[:160]}")
        print(f"Apps Script phản hồi lạ: {body[:160]}", file=sys.stderr)
        return 1
    except Exception as exc:
        _log(f"Lỗi gửi Apps Script: {exc}")
        print(f"Lỗi gửi Apps Script: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
