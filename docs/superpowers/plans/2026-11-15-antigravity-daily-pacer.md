# Antigravity Daily Pacer (`D1-Max`) & Silent Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Claude quota bars on the Kindle E-Ink dashboard with the `D1-Max` Gemini visual layout (separated dual semicircular arcs + 100%-normalized cumulative daily budget + stick-figure pacing trail) and eliminate all 10-minute terminal flashes on Windows 11.

**Architecture:** `render.py` computes the cumulative 7-day daily budget statelessly from `gemini.utilization` and `gemini.resets_at` (`Asia/Ho_Chi_Minh`), rendering anti-aliased 3× supersampled vector primitives (dual separated arcs, stick figure, flag, negative alert badge) directly into the `1072×1448` grayscale PNG while merging session status into the `ANTIGRAVITY` header. `windows/antigravity_sync.py` and `windows/install_task.ps1` isolate child/grandchild CLI processes (`agy.exe`, MCP helpers, `gh.exe`) inside a Win32 hidden desktop (`CreateDesktopW`) and `conhost.exe --headless`, dropping unused Claude buckets and redundant `/credits` calls.

**Tech Stack:** Python 3.12, Pillow (`PIL`), Win32 `ctypes` (`user32.CreateDesktopW`), PowerShell 5.1 / Windows Task Scheduler, `unittest` / `pytest`.

**Spec:** `docs/superpowers/specs/2026-11-15-antigravity-daily-pacer-design.md`

## Global Constraints

- Target screen: Kindle Paperwhite 3 `1072 × 1448` (`mode="L"`, `DASH_SCALE=1.12`, logical grid `957 × 1293`).
- Keep `ANTIGRAVITY` block height ~`205–220px` logical so `VIỆC CẦN LÀM` and `LỊCH` retain full vertical capacity.
- Timezone: `Asia/Ho_Chi_Minh` (`UTC+7`), daily boundary at `00:00`.
- Zero changes to Kindle on-device scripts (`F:\`), `apps_script.gs`, or `e:\2026\2. Project\31. vietbao-agent`.
- Never log or print `DATA_URL`, `TOKEN`, or `SECRET_PATH`.

## Review Focus

- Stale sync across weekly reset (`resets_at <= now` while `utilization` still holds last week's high usage): must clamp to `k = 7` instead of wrapping to `k = 1` and displaying a false `-500%` deficit.
- Deep multi-day deficit (`today_pct < -100`, making `tomorrow_pct < 0`): both `NAY` and `MAI` must format negative values with `−` cleanly without overflowing column bounds or breaking stick-figure coordinates.
- Missing or malformed `resets_at` string from `agy`: must fall back to `now.weekday() + 1` (`1..7`) without raising `ValueError`.
- Evening vs morning weekly `resets_at` (`hour >= 12` vs `hour < 12`): must step `k` by `+1` at `00:00` local time across all 7 days of the cycle.
- Child/grandchild console spawns inside `agy.exe` on Windows 11 (where `WindowsTerminal.exe` is default terminal): must execute on a hidden desktop / headless `conhost` while preserving stdout JSON capture and DPAPI auth access.

---

### Task 1: Stateless Daily Budget Math & `D1-Max` E-Ink Renderer

**Files:**
- Create: `tests/test_daily_pacer.py`
- Modify: `render.py`
- Modify: `sample.json`

**Interfaces:**
- Produces:
  - `compute_daily_pacer(gemini_quota: dict | None, now: datetime) -> dict | None` returning `{"day_index": int, "today_pct": int, "tomorrow_pct": int, "reset_day_short": str}` (or `None` if `gemini_quota` has no numeric `utilization`).
  - Updated `draw_antigravity(d: ScaledDraw, y: int, agy: dict, now: datetime) -> int` rendering `D1-Max`.

- [x] **Step 1: Write failing unit & render tests in `tests/test_daily_pacer.py`**
  Cover: (1) live surplus (`k=2, used=26.0% -> today=18, tomorrow=118, reset_day_short='T7'`), (2) deficit (`k=2, used=32.3% -> today=-26, tomorrow=74`), (3) deep deficit (`k=1, used=30.0% -> today=-110, tomorrow=-10`), (4) cycle day 7 (`k=7, used=90.0% -> today=70, tomorrow=100`), (5) stale post-reset (`resets_at < now, used=85.0% -> k=7, today=105`), (6) evening reset (`reset 18:00`), (7) missing `resets_at` fallback, and (8) full `render()` output validation (`1072×1448`, mode `L`, height budget check) for both surplus and deficit states.

- [x] **Step 2: Run tests to verify failure**
  Run: `python -m unittest discover -s tests -v`
  Expected: FAIL (`ImportError: cannot import name 'compute_daily_pacer' from 'render'`).

- [x] **Step 3: Implement `compute_daily_pacer` and `D1-Max` graphics in `render.py` (+ remove Claude from `sample.json` & `draw_antigravity_big`)**
  Implement 3× supersampled anti-aliased helper for the separated upper/lower semicircular arcs (`5 GIỜ` / `TUẦN · <Thứ>`, zero center divider) and the right-hand `NAY` / `MAI` giant KPIs + stick-figure walking/sprinting & flag trail (`Nk/7`), plus merged header status pill (`ĐANG CHẠY` / `SẴN SÀNG` / `LỖI`).

- [x] **Step 4: Run tests to verify pass**
  Run: `python -m unittest discover -s tests -v`
  Expected: PASS (0 failures).

---

### Task 2: Zero-Flash Hidden Desktop & Gemini-Only Sync on Windows 11

**Files:**
- Modify: `windows/antigravity_sync.py`
- Modify: `windows/install_task.ps1`
- Modify: `tests/test_daily_pacer.py`

**Interfaces:**
- Produces:
  - `_hidden_subprocess_run(cmd: list[str] | str, **kwargs) -> subprocess.CompletedProcess` executing child trees on off-screen Win32 desktop `KindleDashHidden` (`CreateDesktopW` fallback to `SW_HIDE | CREATE_NO_WINDOW`) so neither `agy.exe` grandchildren nor `gh.exe` ever create a window on `WinSta0\Default`.
  - Gemini-only `_map_agy_bucket_key` (ignoring `3p-5h` / `3p-weekly`) and opt-in `DASH_FETCH_CREDITS=1`.
  - Updated `install_task.ps1` using `conhost.exe --headless` + `python.exe` + `-Hidden` task setting.

- [x] **Step 1: Add unit tests for Gemini-only bucket mapping & hidden desktop runner in `tests/test_daily_pacer.py`**
  Assert `3p-5h` and `3p-weekly` return `None`, `gemini-5h` -> `five_hour`, `gemini-weekly` -> `gemini`, and `_hidden_subprocess_run` captures JSON stdout cleanly on Windows.

- [x] **Step 2: Run tests to verify failure**
  Run: `python -m unittest discover -s tests -v`
  Expected: FAIL on `3p-5h` / `3p-weekly` still returning `"seven_day"` / `"claude"`.

- [x] **Step 3: Implement hidden desktop isolation & Gemini-only sync in `windows/antigravity_sync.py` and `windows/install_task.ps1`**
  Update `_hidden_subprocess_run` (Win32 `CreateDesktopW("KindleDashHidden")` + `STARTUPINFOW.lpDesktop`), update `trigger_github_workflow()` to use `_hidden_subprocess_run`, remove Claude mapping in `_map_agy_bucket_key`, gate `/credits` behind `DASH_FETCH_CREDITS=1`, and update `install_task.ps1` to wrap execution in `conhost.exe --headless` with `-Hidden`.

- [x] **Step 4: Re-run tests & re-install Scheduled Task**
  Run: `python -m unittest discover -s tests -v` and `powershell -ExecutionPolicy Bypass -File windows\install_task.ps1`
  Expected: All unit tests PASS, task `KindleDashboard-AntigravitySync` runs with `LastTaskResult = 0`, zero console flash, `quotas=['gemini', 'five_hour']` (or `['five_hour', 'gemini']`), and `gh_dispatch=ok`.

---

### Task 3: End-to-End Preview Verification, Commit, Push & Live GitHub Pages Check

**Files:**
- Modify: `README.md` (if needed, keep minimal)
- Commit: `docs/superpowers/specs/2026-11-15-antigravity-daily-pacer-design.md`, `docs/superpowers/plans/2026-11-15-antigravity-daily-pacer.md`, `render.py`, `sample.json`, `windows/antigravity_sync.py`, `windows/install_task.ps1`, `tests/test_daily_pacer.py`

- [x] **Step 1: Render both surplus & deficit PNG previews and visually inspect them with `read_file`**
  Generate `scratch/preview_surplus.png` (using live `~/.kindle-dashboard-quota.json`) and `scratch/preview_deficit.png` (simulated deficit), inspect both images with `read_file` to verify crisp typography, zero overlap, separated arcs, stick figure posture, and balanced vertical layout.

- [x] **Step 2: Commit, push to `main`, and verify GitHub Actions workflow succeeds**
  Stage only the intended files (never `config.sh` or `antigravity_sync.log` or `launch_sync_hidden.vbs` if untracked/local), push to `origin/main`, and verify `gh run watch` completes `success`.
