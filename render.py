#!/usr/bin/env python3
"""Vẽ dashboard lịch + todo + Antigravity cho Kindle Paperwhite 3 (1072x1448, xám).

Dữ liệu thật (dùng trong GitHub Actions):
    DATA_URL  (hoặc GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN)
    python render.py --out _site/dashboard.png

Xem trước bằng dữ liệu mẫu:
    python render.py --sample sample.json --out preview_sample.png
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- cấu hình
PW = int(os.environ.get("DASH_WIDTH", "1072"))   # Paperwhite 3 (7th gen): 1072x1448
PH = int(os.environ.get("DASH_HEIGHT", "1448"))
# Phóng to toàn bộ bố cục (chữ + khoảng cách). 1.12 cân đối cho màn 1072x1448.
SCALE = float(os.environ.get("DASH_SCALE", "1.12"))
W, H = round(PW / SCALE), round(PH / SCALE)   # kích thước "logic" dùng khi bố trí (~957x1293)
TZ = ZoneInfo(os.environ.get("DASH_TZ", "Asia/Ho_Chi_Minh"))
# Bố cục (biến DASH_LAYOUT): lich = ngày + thời tiết + dải Antigravity (mặc định) · antigravity = Antigravity cỡ lớn ở trên cùng
TITLE = os.environ.get("DASH_TITLE") or "Antigravity"
LAYOUT = (os.environ.get("DASH_LAYOUT") or "lich").strip().lower()
SKIP_CALENDARS = {s.strip() for s in os.environ.get("DASH_SKIP_CALENDARS", "").split(",") if s.strip()}

FONT_DIR = Path(__file__).parent / "fonts"
BLACK, DARK, MID, LIGHT, PALE, WHITE = 0, 60, 120, 180, 225, 255
MARGIN = round(72 / SCALE ** 0.5)   # lề tăng ít hơn chữ để không phí chỗ

THU = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
THU_NGAN = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    win_font = "segoeuib.ttf" if weight in ("Bold", "SemiBold") else "segoeui.ttf"
    for p in (
        FONT_DIR / f"Inter-{weight}.otf",
        Path(f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if weight in ('Bold', 'SemiBold') else ''}.ttf"),
        Path("C:/Windows/Fonts") / win_font,
    ):
        if p.exists():
            return ImageFont.truetype(str(p), round(size * SCALE))
    return ImageFont.load_default(round(size * SCALE))


class ScaledDraw:
    """Vẽ theo toạ độ logic, tự nhân SCALE sang điểm ảnh thật (chữ vẫn nét căng)."""

    def __init__(self, img):
        self._img = img
        self._d = ImageDraw.Draw(img)

    @staticmethod
    def _xy(v):
        if isinstance(v, (list, tuple)) and v and isinstance(v[0], (list, tuple)):
            return [(x * SCALE, y * SCALE) for x, y in v]
        return [c * SCALE for c in v]

    @staticmethod
    def _kw(kw):
        for k in ("width", "radius"):
            if k in kw:
                kw[k] = max(1, round(kw[k] * SCALE))
        return kw

    def textlength(self, text, font):
        return self._d.textlength(text, font=font) / SCALE

    def text(self, xy, text, **kw):
        self._d.text((xy[0] * SCALE, xy[1] * SCALE), text, **kw)

    def line(self, xy, **kw):
        self._d.line(self._xy(xy), **self._kw(kw))

    def polygon(self, xy, **kw):
        self._d.polygon(self._xy(xy), **self._kw(kw))

    def ellipse(self, xy, **kw):
        self._d.ellipse(self._xy(xy), **self._kw(kw))

    def rounded_rectangle(self, xy, **kw):
        self._d.rounded_rectangle(self._xy(xy), **self._kw(kw))


# ---------------------------------------------------------------- dữ liệu
@dataclass
class Event:
    title: str
    start: datetime | None  # None = cả ngày
    end: datetime | None
    location: str = ""
    calendar: str = ""

    @property
    def all_day(self) -> bool:
        return self.start is None


@dataclass
class Task:
    title: str
    due: date | None
    list_name: str = ""
    notes: str = ""


def _google_session():
    import requests

    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def _get_all(s, url, params=None):
    params = dict(params or {})
    while True:
        r = s.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        yield from data.get("items", [])
        if not data.get("nextPageToken"):
            return
        params["pageToken"] = data["nextPageToken"]


def fetch_google(today: date) -> tuple[list[Event], list[Task]]:
    s = _google_session()
    t0 = datetime.combine(today, time.min, TZ)
    t1 = t0 + timedelta(days=2)

    events: list[Event] = []
    for cal in _get_all(s, "https://www.googleapis.com/calendar/v3/users/me/calendarList"):
        name = cal.get("summaryOverride") or cal.get("summary", "")
        if name in SKIP_CALENDARS or cal.get("selected") is False:
            continue
        for e in _get_all(s, f"https://www.googleapis.com/calendar/v3/calendars/{cal['id']}/events", {
            "timeMin": t0.isoformat(), "timeMax": t1.isoformat(),
            "singleEvents": "true", "orderBy": "startTime", "maxResults": 100,
        }):
            if e.get("status") == "cancelled":
                continue
            if any(a.get("self") and a.get("responseStatus") == "declined" for a in e.get("attendees", [])):
                continue
            st, en = e.get("start", {}), e.get("end", {})
            if "dateTime" in st:
                start = datetime.fromisoformat(st["dateTime"]).astimezone(TZ)
                end = datetime.fromisoformat(en["dateTime"]).astimezone(TZ)
                events.append(Event(e.get("summary", "(Không tiêu đề)"), start, end, e.get("location", ""), name))
            else:
                d0, d1 = date.fromisoformat(st["date"]), date.fromisoformat(en["date"])
                for i in range((d1 - d0).days):
                    d = d0 + timedelta(days=i)
                    if today <= d <= today + timedelta(days=1):
                        ev = Event(e.get("summary", "(Không tiêu đề)"), None, None, e.get("location", ""), name)
                        ev.__dict__["day"] = d
                        events.append(ev)

    tasks: list[Task] = []
    for tl in _get_all(s, "https://tasks.googleapis.com/tasks/v1/users/@me/lists"):
        for t in _get_all(s, f"https://tasks.googleapis.com/tasks/v1/lists/{tl['id']}/tasks", {
            "showCompleted": "false", "showHidden": "false", "maxResults": 100,
        }):
            if not t.get("title", "").strip():
                continue
            due = date.fromisoformat(t["due"][:10]) if t.get("due") else None
            tasks.append(Task(t["title"].strip(), due, tl.get("title", ""), t.get("notes", "")))
    return events, tasks


def parse_payload(data: dict, today: date) -> tuple[list[Event], list[Task]]:
    """Đọc JSON từ Google Apps Script (apps_script.gs)."""
    events: list[Event] = []
    for e in data.get("events", []):
        name = e.get("calendar", "")
        if name in SKIP_CALENDARS:
            continue
        if e.get("allDay"):
            d0 = date.fromisoformat(e["startDate"])
            d1 = date.fromisoformat(e.get("endDate") or e["startDate"])
            if d1 <= d0:
                d1 = d0 + timedelta(days=1)
            d = d0
            while d < d1:
                if today <= d <= today + timedelta(days=1):
                    ev = Event(e["title"], None, None, e.get("location", ""), name)
                    ev.__dict__["day"] = d
                    events.append(ev)
                d += timedelta(days=1)
        else:
            start = datetime.fromisoformat(e["start"].replace("Z", "+00:00")).astimezone(TZ)
            end = datetime.fromisoformat(e["end"].replace("Z", "+00:00")).astimezone(TZ)
            events.append(Event(e["title"], start, end, e.get("location", ""), name))
    tasks = [Task(t["title"], date.fromisoformat(t["due"]) if t.get("due") else None,
                  t.get("list", ""), t.get("notes", "")) for t in data.get("tasks", [])]
    return events, tasks


def fetch_appscript(url: str, today: date) -> tuple[list[Event], list[Task]]:
    import requests

    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise SystemExit(f"Apps Script báo lỗi: {data['error']} (kiểm tra token trong DATA_URL)")
    global AGY_DATA
    AGY_DATA = data.get("antigravity") or data.get("claude")
    return parse_payload(data, today)


# ---------------------------------------------------------------- Antigravity
AGY_DATA: dict | None = None


def draw_antigravity_logo(d: ScaledDraw, x: float, y: float, size: float) -> None:
    """Vẽ biểu tượng hình học Antigravity sắc nét cho màn e-ink."""
    r = max(4, round(size * 0.24))
    d.rounded_rectangle([x, y, x + size, y + size], radius=r, fill=BLACK)
    # Chữ A cách điệu (delta nhọn) màu trắng bên trong
    cx = x + size * 0.50
    top = y + size * 0.18
    bot = y + size * 0.80
    left = x + size * 0.22
    right = x + size * 0.78
    d.line([(left, bot), (cx, top), (right, bot)], fill=WHITE, width=max(2, round(size * 0.12)))
    # Điểm quỹ đạo (orbit dot) tạo cảm giác không trọng lực
    dot_r = max(1.5, size * 0.09)
    d.ellipse([cx - dot_r, y + size * 0.62 - dot_r, cx + dot_r, y + size * 0.62 + dot_r], fill=WHITE)


def _extract_quotas(agy: dict) -> dict[str, dict]:
    raw_q = agy.get("quotas") if isinstance(agy.get("quotas"), dict) else {}
    out: dict[str, dict] = {}
    for k in ("gemini", "claude", "gpt", "five_hour", "seven_day"):
        v = raw_q.get(k) if isinstance(raw_q.get(k), dict) else agy.get(k)
        if isinstance(v, dict) and isinstance(v.get("utilization"), (int, float)):
            out[k] = v
    return out


def _reset_label(iso: str | None, now: datetime) -> str:
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return ""
    if t.date() == now.date():
        return f"đặt lại {t:%H:%M}"
    return f"đặt lại {THU_NGAN[t.weekday()]} {t:%H:%M}"


def _remaining(iso: str | None, now: datetime) -> tuple[str, datetime | None]:
    if not iso:
        return "", None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return "", None
    mins = max(0, int((t - now).total_seconds() // 60))
    days, rem = divmod(mins, 1440)
    hrs, m = divmod(rem, 60)
    if days:
        txt = f"còn {days} ngày {hrs} giờ"
    elif hrs:
        txt = f"còn {hrs} giờ {m:02d} phút"
    else:
        txt = f"còn {m} phút"
    return txt, t


def _draw_activity_row(d: ScaledDraw, y: int, activity: dict) -> int:
    latest = activity.get("latest") if isinstance(activity.get("latest"), dict) else {}
    status = str(latest.get("status") or "DONE").upper()
    active_count = int(activity.get("active_count") or 0)

    if status == "ERROR":
        pill_txt, fill_bg, fg, border_w = "LỖI", None, BLACK, 3
    elif status == "RUNNING" or active_count > 0:
        pill_txt, fill_bg, fg, border_w = "ĐANG CHẠY", BLACK, WHITE, 0
    else:
        pill_txt, fill_bg, fg, border_w = "SẴN SÀNG", None, BLACK, 2

    fpill = font("Bold", 17)
    pill_w = round(d.textlength(pill_txt, font=fpill) + 22)
    pill_h = 28
    if fill_bg is not None:
        d.rounded_rectangle([MARGIN, y, MARGIN + pill_w, y + pill_h], radius=14, fill=fill_bg)
    else:
        d.rounded_rectangle([MARGIN, y, MARGIN + pill_w, y + pill_h], radius=14, outline=BLACK, width=border_w)
    d.text((MARGIN + pill_w / 2, y + pill_h / 2), pill_txt, font=fpill, fill=fg, anchor="mm")

    fstats = font("Regular", 21)
    today_sess = int(activity.get("today_sessions") or 0)
    today_steps = int(activity.get("today_steps") or 0)
    stats_txt = f"Hôm nay: {today_sess} phiên · {today_steps} bước"
    stats_w = d.textlength(stats_txt, font=fstats)
    d.text((W - MARGIN - stats_w, y + pill_h / 2), stats_txt, font=fstats, fill=DARK, anchor="lm")

    flabel = font("Medium", 22)
    lx = MARGIN + pill_w + 14
    avail_w = max(80, (W - MARGIN - stats_w - 16) - lx)
    raw_label = str(latest.get("label") or "Chưa có phiên gần đây")
    d.text((lx, y + pill_h / 2), fit(d, raw_label, flabel, avail_w), font=flabel, fill=BLACK, anchor="lm")
    return y + pill_h + 10


def draw_antigravity(d: ScaledDraw, y: int, agy: dict, now: datetime) -> int:
    """Dải Antigravity gọn trên bố cục Lịch: Quota (Gemini/Claude/GPT + Credits) + Trạng thái phiên."""
    draw_antigravity_logo(d, MARGIN, y, 24)
    f_lab = font("Bold", 24)
    d.text((MARGIN + 34, y + 12), "ANTIGRAVITY", font=f_lab, fill=BLACK, anchor="lm")

    # Dòng metadata bên phải: Credits + giờ cập nhật
    credits_obj = agy.get("credits") if isinstance(agy.get("credits"), dict) else None
    cred_txt = ""
    if credits_obj and isinstance(credits_obj.get("remaining"), (int, float)):
        cred_txt = f"Credits: {int(round(credits_obj['remaining']))}"

    time_txt, stale = "", False
    fetched = agy.get("fetched_at")
    if fetched:
        try:
            ft = datetime.fromisoformat(str(fetched).replace("Z", "+00:00")).astimezone(TZ)
            stale = (now - ft).total_seconds() > 7200
            time_txt = f"số liệu cũ · {ft:%H:%M %d/%m}" if stale else f"cập nhật {ft:%H:%M}"
        except ValueError:
            pass

    f_cred, f_time = font("SemiBold", 21), font("Regular", 20)
    rx = W - MARGIN
    if time_txt:
        tw = d.textlength(time_txt, font=f_time)
        d.text((rx - tw, y + 12), time_txt, font=f_time, fill=DARK if stale else MID, anchor="lm")
        rx -= tw
    if cred_txt and time_txt:
        sep = " · "
        sw = d.textlength(sep, font=f_time)
        d.text((rx - sw, y + 12), sep, font=f_time, fill=MID, anchor="lm")
        rx -= sw
    if cred_txt:
        cw = d.textlength(cred_txt, font=f_cred)
        d.text((rx - cw, y + 12), cred_txt, font=f_cred, fill=BLACK, anchor="lm")

    y += 36
    quotas = _extract_quotas(agy)
    activity = agy.get("activity") if isinstance(agy.get("activity"), dict) else None

    if quotas:
        if any(k in quotas for k in ("gemini", "claude", "gpt")):
            cols = [("gemini", "Gemini"), ("claude", "Claude"), ("gpt", "GPT")]
            gap = 28
        else:
            cols = [("five_hour", "Phiên hiện tại"), ("seven_day", "Tuần này")]
            gap = 40

        col_w = (W - 2 * MARGIN - gap * (len(cols) - 1)) / len(cols)
        has_any_reset = any(_reset_label((quotas.get(k) or {}).get("resets_at"), now) for k, _ in cols)
        f_name, f_pct, f_rst = font("Medium", 22), font("Bold", 26), font("Regular", 18)

        for i, (key, label) in enumerate(cols):
            x0 = MARGIN + i * (col_w + gap)
            v = quotas.get(key) or {}
            pct = v.get("utilization")
            pct_txt = "--" if pct is None else f"{round(pct)}%"
            d.text((x0, y), label, font=f_name, fill=DARK)
            d.text((x0 + col_w - d.textlength(pct_txt, font=f_pct), y - 3), pct_txt, font=f_pct, fill=BLACK)
            by = y + 32
            bh = 13
            d.rounded_rectangle([x0, by, x0 + col_w, by + bh], radius=6, outline=BLACK, width=2)
            if pct:
                fill_w = max(bh, col_w * min(float(pct), 100.0) / 100.0)
                d.rounded_rectangle([x0, by, x0 + fill_w, by + bh], radius=6, fill=BLACK)
            if has_any_reset:
                rst = _reset_label(v.get("resets_at"), now)
                if rst:
                    d.text((x0, by + bh + 4), fit(d, rst, f_rst, col_w), font=f_rst, fill=MID)

        y += 32 + 13 + (32 if has_any_reset else 12)

    if activity:
        y = _draw_activity_row(d, y, activity)
    elif not quotas:
        d.text((MARGIN, y), "Chưa có số liệu Antigravity từ Windows PC.", font=font("Regular", 22), fill=MID)
        y += 34

    return y


def _pct_text(d, x, y, pct, fp):
    pct_txt = "--" if pct is None else f"{round(pct):02d}%"
    cell = max(d.textlength(c, font=fp) for c in "0123456789")
    for c in pct_txt:
        cw = d.textlength(c, font=fp)
        if c.isdigit():
            d.text((x + (cell - cw) / 2, y), c, font=fp, fill=BLACK, anchor="lm")
            x += cell
        else:
            d.text((x, y), c, font=fp, fill=BLACK, anchor="lm")
            x += cw
    return x


def _status(pct):
    return ("Thoải mái" if pct < 50 else "Vừa phải" if pct < 80
            else "Sắp chạm giới hạn" if pct < 100 else "Đã hết, chờ đặt lại")


def _big_quota_block(d: ScaledDraw, y: int, name: str, v: dict, now: datetime, span: timedelta) -> int:
    pct = v.get("utilization")
    left, reset_at = _remaining(v.get("resets_at"), now)
    elapsed = min(max(1 - (reset_at - now) / span, 0), 1) if reset_at else None
    fp = font("Bold", 190)
    x_end = _pct_text(d, MARGIN - 6, y + 78, pct, fp)
    rx = x_end + 30
    d.text((rx, y + 12), name.upper(), font=font("Bold", 32), fill=BLACK)
    if pct is not None:
        status = _status(pct)
        fs = font("SemiBold", 30)
        if pct >= 80:
            sw = d.textlength(status, font=fs)
            d.rounded_rectangle([rx, y + 56, rx + sw + 30, y + 100], radius=22, fill=BLACK)
            d.text((rx + 15, y + 78), status, font=fs, fill=WHITE, anchor="lm")
        else:
            d.text((rx, y + 78), status, font=fs, fill=DARK, anchor="lm")
    fi = font("Medium", 25)
    if reset_at:
        when = f"{reset_at:%H:%M}" if reset_at.date() == now.date() else f"{THU_NGAN[reset_at.weekday()]} {reset_at:%H:%M}"
        d.text((rx, y + 118), f"đặt lại {when}", font=fi, fill=DARK, anchor="lm")
        d.text((rx, y + 150), left, font=fi, fill=DARK, anchor="lm")
    y += 174
    bx0, bx1 = MARGIN, W - MARGIN
    bar_w = bx1 - bx0
    bh = 44
    d.rounded_rectangle([bx0, y, bx1, y + bh], radius=bh // 2, outline=BLACK, width=4)
    for q in (0.25, 0.5, 0.75):
        qx = bx0 + bar_w * q
        d.line([(qx, y + 11), (qx, y + bh - 11)], fill=LIGHT, width=3)
    if pct:
        fw = max(bh, bar_w * min(float(pct), 100.0) / 100.0)
        d.rounded_rectangle([bx0, y, bx0 + fw, y + bh], radius=bh // 2, fill=BLACK)
    ty = y + bh + 6
    if elapsed is not None:
        mx = bx0 + bar_w * elapsed
        d.polygon([(mx, ty), (mx - 12, ty + 16), (mx + 12, ty + 16)], fill=BLACK)
        cap = f"đã trôi {round(elapsed * 100)}% thời gian"
        fc = font("Regular", 21)
        cw = d.textlength(cap, font=fc)
        cx = mx + 18 if mx + 18 + cw <= bx1 else mx - 18 - cw
        d.text((cx, ty - 1), cap, font=fc, fill=MID)
    return ty + 32


def _mini_quota_col(d: ScaledDraw, x0: float, y: int, w: float, name: str, v: dict, now: datetime) -> None:
    v = v or {}
    pct = v.get("utilization")
    d.text((x0, y), name, font=font("SemiBold", 28), fill=DARK)
    fp = font("Bold", 40)
    pct_txt = "--" if pct is None else f"{round(pct)}%"
    d.text((x0 + w - d.textlength(pct_txt, font=fp), y - 6), pct_txt, font=fp, fill=BLACK)
    by, bh = y + 46, 20
    d.rounded_rectangle([x0, by, x0 + w, by + bh], radius=bh // 2, outline=BLACK, width=3)
    if pct:
        fw = max(bh, w * min(float(pct), 100.0) / 100.0)
        d.rounded_rectangle([x0, by, x0 + fw, by + bh], radius=bh // 2, fill=BLACK)
    rst = _reset_label(v.get("resets_at"), now)
    if rst:
        fc = font("Regular", 21)
        d.text((x0, by + bh + 8), fit(d, rst, fc, w), font=fc, fill=MID)


def draw_antigravity_big(d: ScaledDraw, y: int, agy: dict | None, now: datetime) -> int:
    """Bố cục Antigravity cỡ lớn khi DASH_LAYOUT = antigravity."""
    x = MARGIN
    logo_path = next((p for p in Path(__file__).parent.iterdir() if p.name.lower() == "logo.png"), None)
    if logo_path:
        try:
            lg = Image.open(logo_path).convert("RGBA")
            lh = round(48 * SCALE)
            lg = lg.resize((max(1, round(lg.width * lh / lg.height)), lh), Image.LANCZOS)
            bg = Image.new("RGBA", lg.size, (255, 255, 255, 255))
            bg.alpha_composite(lg)
            d._img.paste(bg.convert("L"), (round(x * SCALE), round((y - 2) * SCALE)))
            x += lg.width / SCALE + 14
        except Exception:
            draw_antigravity_logo(d, x, y + 2, 38)
            x += 50
    else:
        draw_antigravity_logo(d, x, y + 2, 38)
        x += 50

    d.text((x, y + 22), TITLE, font=font("Bold", 40), fill=BLACK, anchor="lm")
    note, stale = "", False
    if agy and agy.get("fetched_at"):
        try:
            ft = datetime.fromisoformat(str(agy["fetched_at"]).replace("Z", "+00:00")).astimezone(TZ)
            stale = (now - ft).total_seconds() > 7200
            note = f"SỐ LIỆU CŨ · {ft:%H:%M %d/%m}" if stale else f"số liệu lúc {ft:%H:%M}"
        except ValueError:
            pass
    if note:
        fn = font("SemiBold" if stale else "Regular", 23)
        d.text((W - MARGIN - d.textlength(note, font=fn), y + 22), note, font=fn, fill=BLACK if stale else MID, anchor="lm")
    y += 54
    d.line([(MARGIN, y), (W - MARGIN, y)], fill=BLACK, width=5)
    y += 22
    if not agy:
        d.text((MARGIN, y), "Chưa có số liệu từ Windows PC.", font=font("Regular", 30), fill=MID)
        return y + 66

    quotas = _extract_quotas(agy)
    credits_obj = agy.get("credits") if isinstance(agy.get("credits"), dict) else None
    activity = agy.get("activity") if isinstance(agy.get("activity"), dict) else None

    if quotas:
        primary_key = next((k for k in ("claude", "gemini", "seven_day", "five_hour", "gpt") if k in quotas), None)
        names = {"gemini": "Gemini", "claude": "Claude", "gpt": "GPT", "five_hour": "Phiên 5 giờ", "seven_day": "Tuần này"}
        if primary_key:
            span = timedelta(hours=5) if primary_key == "five_hour" else timedelta(days=7)
            y = _big_quota_block(d, y, names[primary_key], quotas[primary_key], now, span)
            others = [(k, names[k]) for k in ("gemini", "claude", "gpt", "five_hour") if k != primary_key and k in quotas]
            if others:
                gap = 36
                col_w = (W - 2 * MARGIN - gap * (len(others) - 1)) / len(others)
                for i, (k, label) in enumerate(others):
                    _mini_quota_col(d, MARGIN + i * (col_w + gap), y, col_w, label, quotas[k], now)
                y += 102
    elif activity:
        # Không có quota nhưng có activity -> hiện nổi bật số bước & phiên hôm nay
        big_txt = f"{int(activity.get('today_steps') or 0)}"
        d.text((MARGIN, y), big_txt, font=font("Bold", 110), fill=BLACK)
        bw = d.textlength(big_txt, font=font("Bold", 110))
        d.text((MARGIN + bw + 24, y + 26), "BƯỚC HÔM NAY", font=font("Bold", 28), fill=BLACK)
        d.text((MARGIN + bw + 24, y + 66), f"{int(activity.get('today_sessions') or 0)} phiên · {int(activity.get('week_steps') or 0)} bước/7 ngày", font=font("Medium", 26), fill=DARK)
        y += 130

    if credits_obj and isinstance(credits_obj.get("remaining"), (int, float)):
        d.text((MARGIN, y), f"AI Credits còn lại: {int(round(credits_obj['remaining']))}", font=font("SemiBold", 24), fill=DARK)
        y += 36

    if activity:
        y = _draw_activity_row(d, y, activity)
    return y + 12


def load_sample(path: str, today: date) -> tuple[list[Event], list[Task]]:
    """Mẫu JSON: giờ dạng "HH:MM" tính theo hôm nay, "+1 HH:MM" là ngày mai; due là số ngày lệch."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    def parse(v):
        off = 0
        if v.startswith("+"):
            o, v = v.split(" ", 1)
            off = int(o)
        hh, mm = map(int, v.split(":"))
        return datetime.combine(today + timedelta(days=off), time(hh, mm), TZ)

    events = []
    for e in data.get("events", []):
        if "day" in e:
            ev = Event(e["title"], None, None, e.get("location", ""))
            ev.__dict__["day"] = today + timedelta(days=e["day"])
        else:
            ev = Event(e["title"], parse(e["start"]), parse(e["end"]), e.get("location", ""))
        events.append(ev)
    tasks = [Task(t["title"], today + timedelta(days=t["due"]) if t.get("due") is not None else None,
                  t.get("list", "")) for t in data.get("tasks", [])]
    return events, tasks


def event_day(e: Event) -> date:
    return e.__dict__.get("day") if e.all_day else e.start.date()


# ---------------------------------------------------------------- vẽ cơ bản
def fit(d: ScaledDraw, text: str, f, max_w: float) -> str:
    if d.textlength(text, font=f) <= max_w:
        return text
    while text and d.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(d, text, f, max_w, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(d, lines[-1] + " …", f, max_w)
    return [fit(d, l, f, max_w) for l in lines]


# ---------------------------------------------------------------- thời tiết
LAT = float(os.environ.get("DASH_LAT", "10.7769"))   # mặc định: TP.HCM — đặt DASH_LAT/DASH_LON cho thành phố của bạn
LON = float(os.environ.get("DASH_LON", "106.7009"))

WMO = {0: ("Trời quang", "sun"), 1: ("Nắng nhẹ", "sun"), 2: ("Có mây", "partly"), 3: ("Nhiều mây", "cloud"),
       45: ("Sương mù", "fog"), 48: ("Sương mù", "fog"), 51: ("Mưa phùn", "rain"), 53: ("Mưa phùn", "rain"),
       55: ("Mưa phùn", "rain"), 61: ("Mưa nhỏ", "rain"), 63: ("Mưa vừa", "rain"), 65: ("Mưa to", "rain"),
       80: ("Mưa rào", "rain"), 81: ("Mưa rào", "rain"), 82: ("Mưa rất to", "rain"),
       95: ("Dông", "storm"), 96: ("Dông, mưa đá", "storm"), 99: ("Dông, mưa đá", "storm")}


@dataclass
class Weather:
    temp: float
    code: int
    tmin: float
    tmax: float
    rain: int            # % khả năng mưa
    aqi: int | None = None

    @property
    def desc(self):
        return WMO.get(self.code, ("", "cloud"))[0]

    @property
    def icon(self):
        return WMO.get(self.code, ("", "cloud"))[1]


def fetch_weather() -> Weather | None:
    import requests
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": LAT, "longitude": LON, "timezone": str(TZ), "forecast_days": 1,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        }, timeout=20).json()
        w = Weather(r["current"]["temperature_2m"], r["current"]["weather_code"],
                    r["daily"]["temperature_2m_min"][0], r["daily"]["temperature_2m_max"][0],
                    r["daily"]["precipitation_probability_max"][0] or 0)
    except Exception as e:
        print("Không lấy được thời tiết:", e)
        return None
    try:
        a = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": LAT, "longitude": LON, "current": "us_aqi"}, timeout=20).json()
        w.aqi = round(a["current"]["us_aqi"])
    except Exception:
        pass
    return w


def aqi_label(v):
    for lim, name in ((50, "Tốt"), (100, "Trung bình"), (150, "Kém"), (200, "Xấu"), (300, "Rất xấu")):
        if v <= lim:
            return name
    return "Nguy hại"


def draw_icon(d, kind, cx, cy, s):
    """Icon thời tiết đơn giản, nét đen, hợp e-ink. s = bán kính cơ sở."""
    import math

    def sun(x, y, r):
        d.ellipse([x - r, y - r, x + r, y + r], outline=BLACK, width=6)
        for i in range(8):
            a = i * math.pi / 4
            d.line([(x + math.cos(a) * r * 1.45, y + math.sin(a) * r * 1.45),
                    (x + math.cos(a) * r * 1.9, y + math.sin(a) * r * 1.9)], fill=BLACK, width=6)

    def cloud(x, y, w, fill=WHITE):
        h = w * 0.55
        parts = [(x - w * .30, y + h * .05, w * .28), (x + w * .02, y - h * .25, w * .34), (x + w * .32, y + h * .08, w * .24)]
        for px, py, r in parts:
            d.ellipse([px - r - 6, py - r - 6, px + r + 6, py + r + 6], fill=BLACK)
        d.rounded_rectangle([x - w * .58 - 6, y - 6, x + w * .56 + 6, y + h * .45 + 6], radius=int(h * .3), fill=BLACK)
        for px, py, r in parts:
            d.ellipse([px - r, py - r, px + r, py + r], fill=fill)
        d.rounded_rectangle([x - w * .58, y, x + w * .56, y + h * .45], radius=int(h * .3), fill=fill)

    if kind == "sun":
        sun(cx, cy, s * .55)
    elif kind == "partly":
        sun(cx + s * .35, cy - s * .35, s * .42)
        cloud(cx - s * .1, cy + s * .1, s * 1.5)
    elif kind in ("cloud", "fog"):
        cloud(cx, cy - s * .1, s * 1.7)
        if kind == "fog":
            for i in range(3):
                d.line([(cx - s * .8, cy + s * .55 + i * 16), (cx + s * .8, cy + s * .55 + i * 16)], fill=BLACK, width=6)
    else:
        cloud(cx, cy - s * .3, s * 1.7)
        if kind == "storm":
            d.polygon([(cx, cy + s * .25), (cx - s * .25, cy + s * .75), (cx, cy + s * .7),
                       (cx - s * .15, cy + s * 1.1), (cx + s * .3, cy + s * .55), (cx + s * .05, cy + s * .58)], fill=BLACK)
        else:
            for i in (-1, 0, 1):
                x = cx + i * s * .45
                d.line([(x + 8, cy + s * .35), (x - 8, cy + s * .8)], fill=BLACK, width=7)


# ---------------------------------------------------------------- vẽ dashboard
def section_title(d, y, text, right=""):
    f = font("Bold", 26)
    d.text((MARGIN, y), text.upper(), font=f, fill=BLACK)
    if right:
        fr = font("Medium", 24)
        d.text((W - MARGIN - d.textlength(right, font=fr), y + 2), right, font=fr, fill=MID)
    d.line([(MARGIN, y + 40), (W - MARGIN, y + 40)], fill=BLACK, width=3)
    return y + 56


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def due_tag(t: Task, today: date):
    if not t.due:
        return ""
    if t.due < today:
        return "Quá hạn"
    if t.due == today:
        return "Hôm nay"
    if t.due == today + timedelta(days=1):
        return "Ngày mai"
    return f"{t.due.day}/{t.due.month}"


def render(events: list[Event], tasks: list[Task], now: datetime, weather: Weather | None = None) -> Image.Image:
    from lunar import solar_to_lunar, year_name

    today, tomorrow = now.date(), now.date() + timedelta(days=1)
    img = Image.new("L", (PW, PH), WHITE)
    d = ScaledDraw(img)
    f_sub = font("Regular", 26)

    if LAYOUT in ("antigravity", "claude"):
        y = draw_antigravity_big(d, 36, AGY_DATA, now)
        d.line([(MARGIN, y - 10), (W - MARGIN, y - 10)], fill=PALE, width=2)
        y += 12
    else:
        # ============ HEADER: ngày + âm lịch | thời tiết
        y = 46
        d.text((MARGIN, y), THU[today.weekday()], font=font("Bold", 82), fill=BLACK)
        d.text((MARGIN, y + 104), f"{today.day} tháng {today.month}, {today.year}", font=font("SemiBold", 35), fill=DARK)
        ld, lm, ly, leap = solar_to_lunar(today.day, today.month, today.year)
        lunar_txt = f"Âm lịch {ld}/{lm}{' nhuận' if leap else ''} · năm {year_name(ly)}"
        d.text((MARGIN, y + 152), lunar_txt, font=f_sub, fill=MID)

        if weather:
            right = W - MARGIN
            ft = font("Bold", 88)
            t = f"{round(weather.temp)}°"
            tw = d.textlength(t, font=ft)
            d.text((right - tw, y - 6), t, font=ft, fill=BLACK)
            draw_icon(d, weather.icon, int(right - tw - 80), y + 48, 56)
            l1 = f"{weather.desc} · {round(weather.tmin)}–{round(weather.tmax)}°"
            l2 = f"Mưa {weather.rain}%" + (f" · AQI {weather.aqi} {aqi_label(weather.aqi)}" if weather.aqi is not None else "")
            fw = font("Medium", 26)
            d.text((right - d.textlength(l1, font=fw), y + 114), l1, font=fw, fill=DARK)
            d.text((right - d.textlength(l2, font=f_sub), y + 152), l2, font=f_sub, fill=MID)
        y += 204
        d.line([(MARGIN, y), (W - MARGIN, y)], fill=BLACK, width=5)
        y += 20

        # ============ DẢI ANTIGRAVITY (quota + phiên chạy gần nhất)
        if AGY_DATA:
            y = draw_antigravity(d, y, AGY_DATA, now)
            d.line([(MARGIN, y), (W - MARGIN, y)], fill=PALE, width=2)
            y += 18

    ev_today = sorted([e for e in events if event_day(e) == today], key=lambda e: (not e.all_day, e.start or now))
    ev_tom = sorted([e for e in events if event_day(e) == tomorrow], key=lambda e: (not e.all_day, e.start or now))
    timed = [e for e in ev_today if not e.all_day]
    nxt = next((e for e in timed if e.end > now), None)

    # ============ THẺ "TIẾP THEO" (nền đen, nổi bật trên e-ink)
    if nxt:
        live = nxt.start <= now
        has_loc = bool(nxt.location)
        ch = 136 if has_loc else 108
        d.rounded_rectangle([MARGIN, y, W - MARGIN, y + ch], radius=16, fill=BLACK)
        label = ("ĐANG DIỄN RA" if live else "TIẾP THEO") + f" · {hm(nxt.start)}–{hm(nxt.end)}"
        d.text((MARGIN + 28, y + 16), label, font=font("SemiBold", 24), fill=PALE)
        d.text((MARGIN + 28, y + 48), fit(d, nxt.title, font("Bold", 40), W - 2 * MARGIN - 56),
               font=font("Bold", 40), fill=WHITE)
        if has_loc:
            d.text((MARGIN + 28, y + 96), fit(d, "@ " + nxt.location, f_sub, W - 2 * MARGIN - 56), font=f_sub, fill=PALE)
        y += ch + 24

    # ---- tính trước khối dưới cùng (lịch hôm nay + ngày mai) để todo lấp phần giữa
    footer_y = H - 56
    min_todo = 56 + 3 * 64 if tasks else 120
    cal_max, tom_max = 5, 3

    def _bottom_h(cm, tm):
        cr = min(len(ev_today), cm) or 1
        tr = min(len(ev_tom), tm) or 1
        return (56 + 42 * cr + (32 if len(ev_today) > cm else 0) + 20) + (56 + 40 * tr) + 12

    while footer_y - _bottom_h(cal_max, tom_max) - y < min_todo and (tom_max > 1 or cal_max > 1):
        if tom_max > 1:
            tom_max -= 1
        else:
            cal_max -= 1
    bottom_y = footer_y - _bottom_h(cal_max, tom_max)

    # ============ VIỆC CẦN LÀM (khu vực chính)
    tasks_open = sorted(tasks, key=lambda t: (t.due is None, t.due or date.max, t.title.lower()))
    overdue = sum(1 for t in tasks_open if t.due and t.due < today)
    due_today = sum(1 for t in tasks_open if t.due == today)
    right = f"{len(tasks_open)} việc" + (f" · {overdue} quá hạn" if overdue else "") + \
        (f" · {due_today} hôm nay" if due_today else "")
    y = section_title(d, y, "Việc cần làm", right if tasks_open else "")
    f_task, box = font("Medium", 30), 34
    if not tasks_open:
        d.text((MARGIN, y + 6), "Không còn việc nào. Tuyệt vời!", font=font("Regular", 32), fill=MID)
        y += 62
    for i, t in enumerate(tasks_open):
        tag = due_tag(t, today)
        f_tag = font("SemiBold", 21)
        tag_w = int(d.textlength(tag, font=f_tag)) + 26 if tag else 0
        text_w = W - 2 * MARGIN - box - 22 - (tag_w + 18 if tag else 0)
        line = fit(d, t.title, f_task, text_w)
        limit = bottom_y - (14 if i == len(tasks_open) - 1 else 40)
        row_h = 60
        if y + row_h > limit:
            d.text((MARGIN, y + 2), f"+ {len(tasks_open) - i} việc nữa", font=f_sub, fill=MID)
            y += 38
            break
        d.rounded_rectangle([MARGIN, y + 4, MARGIN + box, y + 4 + box], radius=8, outline=BLACK, width=4)
        d.text((MARGIN + box + 22, y + 21), line, font=f_task, fill=BLACK, anchor="lm")
        if tag:
            x1, x0 = W - MARGIN, W - MARGIN - tag_w
            if tag in ("Quá hạn", "Hôm nay"):
                d.rounded_rectangle([x0, y + 4, x1, y + 38], radius=17, fill=BLACK)
                d.text(((x0 + x1) / 2, y + 21), tag, font=f_tag, fill=WHITE, anchor="mm")
            else:
                d.rounded_rectangle([x0, y + 4, x1, y + 38], radius=17, outline=MID, width=2)
                d.text(((x0 + x1) / 2, y + 21), tag, font=f_tag, fill=DARK, anchor="mm")
        y += row_h
        d.line([(MARGIN + box + 24, y - 6), (W - MARGIN, y - 6)], fill=PALE, width=2)
        y += 4

    # ============ LỊCH HÔM NAY (gọn, ghim phía dưới)
    y = bottom_y
    y = section_title(d, y, "Lịch hôm nay", f"{len(ev_today)} sự kiện" if ev_today else "")
    time_w = 232
    f_ev, f_evb = font("Regular", 30), font("SemiBold", 30)
    if not ev_today:
        d.text((MARGIN, y), "Không có sự kiện nào.", font=f_ev, fill=MID)
        y += 42
    shown = list(ev_today)
    while len(shown) > cal_max:
        past_i = next((k for k, x in enumerate(shown) if not x.all_day and x.end <= now), None)
        shown.pop(past_i if past_i is not None else -1)
    for e in shown:
        past = (not e.all_day) and e.end <= now
        is_next = e is nxt
        col = LIGHT if past else BLACK
        tf = f_evb if is_next else f_ev
        when = "Cả ngày" if e.all_day else f"{hm(e.start)}–{hm(e.end)}"
        d.text((MARGIN, y), when, font=font("Medium", 26), fill=LIGHT if past else DARK)
        title_txt = fit(d, e.title, tf, W - 2 * MARGIN - time_w)
        d.text((MARGIN + time_w, y - 2), title_txt, font=tf, fill=col)
        if past:
            tw = min(d.textlength(title_txt, font=tf), W - 2 * MARGIN - time_w)
            d.line([(MARGIN + time_w, y + 18), (MARGIN + time_w + tw, y + 18)], fill=LIGHT, width=2)
        y += 42
    if len(ev_today) > len(shown):
        d.text((MARGIN, y), f"+ {len(ev_today) - len(shown)} sự kiện khác", font=f_sub, fill=MID)
        y += 32
    y += 20

    # ============ NGÀY MAI
    y = section_title(d, y, "Ngày mai · " + THU[tomorrow.weekday()],
                      f"{len(ev_tom)} sự kiện" if len(ev_tom) > tom_max else "")
    if not ev_tom:
        d.text((MARGIN, y), "Chưa có lịch.", font=f_ev, fill=MID)
    for e in ev_tom[:tom_max]:
        d.text((MARGIN, y), "Cả ngày" if e.all_day else hm(e.start), font=font("Medium", 26), fill=DARK)
        d.text((MARGIN + time_w, y - 2), fit(d, e.title, f_ev, W - 2 * MARGIN - time_w), font=f_ev, fill=DARK)
        y += 40

    # ============ FOOTER
    d.line([(MARGIN, footer_y), (W - MARGIN, footer_y)], fill=LIGHT, width=2)
    d.text(
        (MARGIN, footer_y + 14),
        (f"{THU[today.weekday()]} {today.day}/{today.month} · " if LAYOUT in ("antigravity", "claude") else "")
        + f"Cập nhật {now.strftime('%H:%M %d/%m')}",
        font=font("Regular", 22),
        fill=MID,
    )
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site/dashboard.png")
    ap.add_argument("--sample", help="file JSON dữ liệu mẫu (không gọi Google)")
    ap.add_argument("--agy-json", help="file JSON Antigravity riêng (tuỳ chọn)")
    ap.add_argument("--live-weather", action="store_true", help="gọi Open-Meteo lấy thời tiết thật ngay cả khi dùng --sample")
    ap.add_argument("--layout", help="lich | antigravity (mặc định lấy từ DASH_LAYOUT)")
    ap.add_argument("--now", help="giả lập thời điểm, vd 2026-11-03T10:30")
    args = ap.parse_args()

    global LAYOUT, AGY_DATA
    if args.layout:
        LAYOUT = args.layout.strip().lower()
    now = datetime.fromisoformat(args.now).replace(tzinfo=TZ) if args.now else datetime.now(TZ)
    if args.sample:
        events, tasks = load_sample(args.sample, now.date())
        sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
        if args.live_weather:
            weather = fetch_weather()
        else:
            w = sample.get("weather")
            weather = Weather(**w) if w else None
        AGY_DATA = sample.get("antigravity") or sample.get("claude")
    else:
        if os.environ.get("DATA_URL"):
            events, tasks = fetch_appscript(os.environ["DATA_URL"], now.date())
        elif os.environ.get("GOOGLE_CLIENT_ID"):
            events, tasks = fetch_google(now.date())
        else:
            print("Chưa cấu hình DATA_URL — vẽ bảng ngày âm/dương và thời tiết mặc định.")
            events, tasks = [], []
        weather = fetch_weather()

    if args.agy_json:
        AGY_DATA = json.loads(Path(args.agy_json).read_text(encoding="utf-8"))

    img = render(events, tasks, now, weather)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"Đã lưu {out} ({PW}x{PH}, {len(events)} sự kiện, {len(tasks)} việc, thời tiết: {'có' if weather else 'không'})")


if __name__ == "__main__":
    main()
