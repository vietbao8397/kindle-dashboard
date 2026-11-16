import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "windows"))

import render  # noqa: E402
import antigravity_sync  # noqa: E402

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class TestDailyPacerMath(unittest.TestCase):
    def test_live_surplus_morning_reset(self):
        # Reset Sat 21/11 06:44+07:00; Now Sun 15/11 19:25+07:00 -> Day 2 of 7
        now = datetime(2026, 11, 15, 19, 25, tzinfo=TZ)
        q = {"utilization": 26.0, "resets_at": "2026-11-20T23:44:21Z"}
        res = render.compute_daily_pacer(q, now)
        self.assertIsNotNone(res)
        self.assertEqual(res["day_index"], 2)
        self.assertEqual(res["today_pct"], 18)
        self.assertEqual(res["today_used_pct"], 82)
        self.assertEqual(res["tomorrow_pct"], 118)
        self.assertEqual(res["reset_day_short"], "T7")

    def test_monday_photo_used_27_tomorrow_173(self):
        # Mon 16/11 08:45+07:00 -> Day 3 of 7, used 32.4% -> rem=73%, used_today=27%, tomorrow=173%
        now = datetime(2026, 11, 16, 8, 45, tzinfo=TZ)
        q = {"utilization": 32.4, "resets_at": "2026-11-20T23:44:21Z"}
        res = render.compute_daily_pacer(q, now)
        self.assertEqual(res["day_index"], 3)
        self.assertEqual(res["today_pct"], 73)
        self.assertEqual(res["today_used_pct"], 27)
        self.assertEqual(res["tomorrow_pct"], 173)

    def test_deficit_subtracts_from_tomorrow(self):
        # Day 2 of 7, used 32.3% -> 200 - 226.1 = -26%, used_today = 126%, tomorrow = 74%
        now = datetime(2026, 11, 15, 21, 30, tzinfo=TZ)
        q = {"utilization": 32.3, "resets_at": "2026-11-20T23:44:21Z"}
        res = render.compute_daily_pacer(q, now)
        self.assertEqual(res["day_index"], 2)
        self.assertEqual(res["today_pct"], -26)
        self.assertEqual(res["today_used_pct"], 126)
        self.assertEqual(res["tomorrow_pct"], 74)

    def test_deep_deficit_makes_tomorrow_negative_too(self):
        # Day 1 of 7, used 30.0% -> 100 - 210 = -110%, used_today = 210%, tomorrow = -10%
        now = datetime(2026, 11, 14, 15, 0, tzinfo=TZ)
        q = {"utilization": 30.0, "resets_at": "2026-11-20T23:44:21Z"}
        res = render.compute_daily_pacer(q, now)
        self.assertEqual(res["day_index"], 1)
        self.assertEqual(res["today_pct"], -110)
        self.assertEqual(res["today_used_pct"], 210)
        self.assertEqual(res["tomorrow_pct"], -10)

    def test_cycle_day_7_tomorrow_resets_to_100(self):
        # Fri 20/11 -> days_diff=1 -> k=7, used 90% -> today = 700 - 630 = 70%, tomorrow = 100%
        now = datetime(2026, 11, 20, 14, 0, tzinfo=TZ)
        q = {"utilization": 90.0, "resets_at": "2026-11-20T23:44:21Z"}
        res = render.compute_daily_pacer(q, now)
        self.assertEqual(res["day_index"], 7)
        self.assertEqual(res["today_pct"], 70)
        self.assertEqual(res["today_used_pct"], 30)
        self.assertEqual(res["tomorrow_pct"], 100)

    def test_stale_post_reset_clamps_to_day_7(self):
        # Sat 21/11 06:50 (6 mins after reset, PC hasn't synced yet, used still 85%)
        now = datetime(2026, 11, 21, 6, 50, tzinfo=TZ)
        q = {"utilization": 85.0, "resets_at": "2026-11-20T23:44:21Z"}
        res = render.compute_daily_pacer(q, now)
        self.assertEqual(res["day_index"], 7)
        self.assertEqual(res["today_pct"], 105)
        self.assertEqual(res["today_used_pct"], 0)
        self.assertEqual(res["tomorrow_pct"], 100)

    def test_evening_reset_steps_across_7_days(self):
        # Reset Thu 19/11 18:00+07:00 (hour >= 12)
        # On Fri 13/11 (days_diff=6) -> k = 7 - 6 = 1
        # On Thu 19/11 10:00 (days_diff=0) -> k = 7 - 0 = 7
        q = {"utilization": 10.0, "resets_at": "2026-11-19T18:00:00+07:00"}
        r_day1 = render.compute_daily_pacer(q, datetime(2026, 11, 13, 9, 0, tzinfo=TZ))
        r_day7 = render.compute_daily_pacer(q, datetime(2026, 11, 19, 10, 0, tzinfo=TZ))
        self.assertEqual(r_day1["day_index"], 1)
        self.assertEqual(r_day7["day_index"], 7)
        self.assertEqual(r_day7["reset_day_short"], "T5")

    def test_missing_or_malformed_reset_fallback(self):
        # Sun (weekday=6 -> fallback k=7) or Tue (weekday=1 -> fallback k=2)
        now = datetime(2026, 11, 17, 10, 0, tzinfo=TZ)  # Tuesday -> weekday=1 -> k=2
        res = render.compute_daily_pacer({"utilization": 20.0, "resets_at": "not-a-date"}, now)
        self.assertEqual(res["day_index"], 2)
        self.assertEqual(res["today_pct"], 60)
        self.assertEqual(res["reset_day_short"], "")

    def test_full_render_surplus_and_deficit_dimensions(self):
        now = datetime(2026, 11, 15, 19, 25, tzinfo=TZ)
        old_agy = render.AGY_DATA
        old_layout = render.LAYOUT
        try:
            render.LAYOUT = "lich"
            for util in (26.0, 32.3, 98.0):
                render.AGY_DATA = {
                    "fetched_at": now.isoformat(),
                    "quotas": {
                        "five_hour": {"utilization": 5.2, "resets_at": "2026-11-15T22:39:19+07:00"},
                        "gemini": {"utilization": util, "resets_at": "2026-11-20T23:44:21Z"},
                    },
                    "activity": {
                        "today_sessions": 9,
                        "today_steps": 2417,
                        "active_count": 1 if util == 26.0 else 0,
                        "latest": {"label": "spec-027", "status": "RUNNING" if util == 26.0 else "DONE"},
                    },
                }
                img = render.render([], [], now, None)
                self.assertEqual(img.size, (render.PW, render.PH))
                self.assertEqual(img.mode, "L")
        finally:
            render.AGY_DATA = old_agy
            render.LAYOUT = old_layout


class TestWindowsSyncGeminiOnlyAndHiddenExec(unittest.TestCase):
    def test_claude_buckets_are_ignored(self):
        self.assertEqual(antigravity_sync._map_agy_bucket_key("gemini-5h", "5h", "Gemini"), "five_hour")
        self.assertEqual(antigravity_sync._map_agy_bucket_key("gemini-weekly", "weekly", "Gemini"), "gemini")
        self.assertIsNone(antigravity_sync._map_agy_bucket_key("3p-5h", "5h", "Claude / GPT"))
        self.assertIsNone(antigravity_sync._map_agy_bucket_key("3p-weekly", "weekly", "Claude / GPT"))

    def test_hidden_subprocess_captures_json_stdout(self):
        proc = antigravity_sync._hidden_subprocess_run(
            [sys.executable, "-c", "import json; print(json.dumps({'hidden_ok': True}))"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout.strip())
        self.assertTrue(data["hidden_ok"])

    def test_respawn_on_hidden_desktop_writes_local_payload(self):
        if sys.platform != "win32":
            self.skipTest("Windows only")
        import tempfile

        out_json = Path(tempfile.gettempdir()) / "test_hidden_desk_payload.json"
        out_json.unlink(missing_ok=True)
        try:
            rc = antigravity_sync._respawn_on_hidden_desktop(["--dry-run", "--write-local", str(out_json)])
            self.assertEqual(rc, 0)
            self.assertTrue(out_json.is_file())
            parsed = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertIn("quotas", parsed)
            self.assertNotIn("claude", parsed["quotas"])
            self.assertNotIn("seven_day", parsed["quotas"])
        finally:
            out_json.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
