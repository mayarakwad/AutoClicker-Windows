"""Engine tests. They use a fake mouse, so nothing is really clicked.

Run from the project folder:  python -m unittest
"""
import os
import time
import unittest


from engine import MIN_INTERVAL_MS, ClickConfig, ClickEngine, next_delay

# Shared CI machines (GitHub sets CI=true) oversleep by 10-80 ms per wait, so
# there the timing tests only catch hangs and bursts. Real machines get the
# precise limits.
SHARED_CI = os.environ.get("CI") == "true"


class FakeMouse:
    def __init__(self):
        self.position = (500, 500)
        self.clicked = []  # (button, count, (x, y) or None for the cursor)

    def click(self, button, count=1):
        self.clicked.append((button, count, None))

    def click_at(self, x, y, button, count=1):
        self.clicked.append((button, count, (x, y)))


class ClickEngineTest(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.engine = ClickEngine(mouse=self.mouse)

    def tearDown(self):
        self.engine.stop()
        self.engine.join(5)

    def run_for(self, seconds, **config):
        """Run for about `seconds`; returns how long it really ran (CI machines oversleep)."""
        started = time.perf_counter()
        self.engine.start(ClickConfig(**config))
        time.sleep(seconds)
        self.engine.stop()
        ran = time.perf_counter() - started
        self.engine.join(5)
        return ran

    def assert_no_bursts(self, ran, interval_ms):
        # One click per interval actually elapsed (+1 in flight): never a catch-up burst.
        self.assertLessEqual(self.engine.clicks, ran / (interval_ms / 1000) + 1)

    def test_clicks_at_interval(self):
        ran = self.run_for(0.5, interval_ms=20)
        # 0.5 s / 20 ms = 25 clicks; allow for timer jitter.
        self.assertGreaterEqual(self.engine.clicks, 1 if SHARED_CI else 20)
        self.assert_no_bursts(ran, 20)
        self.assertEqual(self.engine.clicks, len(self.mouse.clicked))

    def test_stop_is_quick_with_long_interval(self):
        self.engine.start(ClickConfig(interval_ms=10_000))
        time.sleep(0.1)
        started = time.perf_counter()
        self.engine.stop()
        self.engine.join(5)
        self.assertFalse(self.engine.running)
        self.assertLess(time.perf_counter() - started, 1.0 if SHARED_CI else 0.2)
        self.assertEqual(self.engine.clicks, 0)

    def test_uses_chosen_button(self):
        self.run_for(0.3, interval_ms=5, button="right")
        self.assertTrue(self.mouse.clicked)
        self.assertTrue(all(b == "right" for b, _, _ in self.mouse.clicked))

    def test_double_click_counts_once(self):
        self.run_for(0.3, interval_ms=5, double=True)
        self.assertTrue(self.mouse.clicked)
        self.assertTrue(all(count == 2 for _, count, _ in self.mouse.clicked))
        self.assertEqual(self.engine.clicks, len(self.mouse.clicked))

    def test_clicks_at_picked_position(self):
        self.run_for(0.3, interval_ms=5, position=(10, -20))
        self.assertTrue(self.mouse.clicked)
        self.assertTrue(all(pos == (10, -20) for _, _, pos in self.mouse.clicked))

    def test_repeat_stops_after_count(self):
        self.engine.start(ClickConfig(interval_ms=5, repeat=7))
        self.engine.join(5)
        self.assertFalse(self.engine.running)
        self.assertEqual(self.engine.clicks, 7)
        self.assertEqual(len(self.mouse.clicked), 7)
        self.assertEqual(self.engine.stop_reason, "finished")

    def test_failsafe_corner_stops_clicking(self):
        self.engine.start(ClickConfig(interval_ms=10))
        time.sleep(0.1)
        self.mouse.position = (1, 0)
        self.engine.join(5)
        self.assertFalse(self.engine.running)
        self.assertEqual(self.engine.stop_reason, "mouse in top-left corner")
        clicks = self.engine.clicks
        time.sleep(0.1)
        self.assertEqual(self.engine.clicks, clicks)

    def test_stop_reason_is_kept(self):
        self.engine.start(ClickConfig(interval_ms=10))
        self.engine.stop("Esc pressed")
        self.engine.join(5)
        self.assertEqual(self.engine.stop_reason, "Esc pressed")

    def test_rejects_bad_config(self):
        for bad in (ClickConfig(interval_ms=0), ClickConfig(interval_ms=0.09), ClickConfig(button="side"),
                    ClickConfig(random_offset_ms=-1), ClickConfig(repeat=-1)):
            with self.assertRaises(ValueError):
                self.engine.start(bad)
        self.assertFalse(self.engine.running)

    def test_fastest_interval(self):
        ran = self.run_for(0.5, interval_ms=MIN_INTERVAL_MS)
        # 0.5 s / 0.1 ms = 5000 clicks: timed by watching the clock, not sleeping.
        self.assertGreaterEqual(self.engine.clicks, 1 if SHARED_CI else 4000)
        self.assert_no_bursts(ran, MIN_INTERVAL_MS)

    def test_fractional_interval(self):
        ran = self.run_for(0.5, interval_ms=1.5)  # 1 ms + 500000 ns
        # 0.5 s / 1.5 ms = 333 clicks.
        self.assertGreaterEqual(self.engine.clicks, 1 if SHARED_CI else 320)
        self.assert_no_bursts(ran, 1.5)

    def test_stop_is_quick_at_the_fastest_interval(self):
        self.engine.start(ClickConfig(interval_ms=MIN_INTERVAL_MS))
        time.sleep(0.1)
        started = time.perf_counter()
        self.engine.stop()
        self.engine.join(5)
        self.assertFalse(self.engine.running)
        self.assertLess(time.perf_counter() - started, 1.0 if SHARED_CI else 0.05)


class NextDelayTest(unittest.TestCase):
    def test_no_offset_is_exact(self):
        self.assertEqual(next_delay(ClickConfig(interval_ms=250)), 0.25)

    def test_offset_stays_in_range_and_varies(self):
        delays = [next_delay(ClickConfig(interval_ms=100, random_offset_ms=40)) for _ in range(2000)]
        self.assertGreaterEqual(min(delays), 0.060)
        self.assertLessEqual(max(delays), 0.140)
        self.assertGreater(len(set(delays)), 40)

    def test_offset_larger_than_interval_never_below_the_minimum(self):
        delays = [next_delay(ClickConfig(interval_ms=5, random_offset_ms=40)) for _ in range(500)]
        self.assertGreaterEqual(min(delays), MIN_INTERVAL_MS / 1000)

    def test_fraction_of_a_millisecond_is_kept(self):
        self.assertEqual(next_delay(ClickConfig(interval_ms=1.5)), 0.0015)
        self.assertEqual(next_delay(ClickConfig(interval_ms=MIN_INTERVAL_MS)), 0.0001)


if __name__ == "__main__":
    unittest.main()
