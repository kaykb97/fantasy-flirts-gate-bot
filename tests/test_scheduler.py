import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import bot

EASTERN = ZoneInfo("America/New_York")


class SchedulerTests(unittest.TestCase):
    def test_refresh_advances_to_next_even_hour(self):
        now = datetime(2026, 11, 25, 15, 17, tzinfo=EASTERN)
        actual = datetime.fromtimestamp(bot.next_refresh_timestamp(int(now.timestamp())), EASTERN)
        self.assertEqual(actual, datetime(2026, 11, 25, 16, 0, tzinfo=EASTERN))

    def test_refresh_at_even_hour_advances_two_hours(self):
        now = datetime(2026, 11, 25, 16, 0, tzinfo=EASTERN)
        actual = datetime.fromtimestamp(bot.next_refresh_timestamp(int(now.timestamp())), EASTERN)
        self.assertEqual(actual, datetime(2026, 11, 25, 18, 0, tzinfo=EASTERN))

    def test_refresh_wraps_to_midnight(self):
        now = datetime(2026, 11, 25, 23, 59, tzinfo=EASTERN)
        actual = datetime.fromtimestamp(bot.next_refresh_timestamp(int(now.timestamp())), EASTERN)
        self.assertEqual(actual, datetime(2026, 11, 26, 0, 0, tzinfo=EASTERN))

    def test_spring_dst_skips_nonexistent_two_am_boundary(self):
        now = datetime(2026, 3, 8, 1, 30, tzinfo=EASTERN)
        actual = datetime.fromtimestamp(bot.next_refresh_timestamp(int(now.timestamp())), EASTERN)
        self.assertEqual(actual, datetime(2026, 3, 8, 3, 0, tzinfo=EASTERN))

    def test_dm_alert_window_is_independent_and_15_minutes(self):
        at_lead_time = datetime(2026, 11, 25, 10, 5, 0, tzinfo=EASTERN)
        before_lead_time = datetime(2026, 11, 25, 10, 4, 59, tzinfo=EASTERN)
        self.assertIsNotNone(bot.build_gate_notification(int(at_lead_time.timestamp())))
        self.assertIsNone(bot.build_gate_notification(int(before_lead_time.timestamp())))

    def test_dm_does_not_alert_after_current_slot(self):
        at_slot = datetime(2026, 11, 25, 10, 20, 0, tzinfo=EASTERN)
        self.assertIsNone(bot.build_gate_notification(int(at_slot.timestamp())))


if __name__ == "__main__":
    unittest.main()
