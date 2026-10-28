"""Recorder and playback tests. Events are fed in directly and the engine uses
a fake mouse, so nothing is really clicked or hooked."""
import time
import unittest


from engine import ClickEngine, PlaybackConfig, Step
from recorder import ClickRecorder, dump_steps, load_steps
from tests.test_engine import SHARED_CI, FakeMouse


class ClickRecorderTest(unittest.TestCase):
    def setUp(self):
        self.steps = []
        self.own = set()
        self.recorder = ClickRecorder(on_step=self.steps.append, is_own=lambda x, y: (x, y) in self.own)

    def test_records_presses_with_delays(self):
        self.recorder._last = time.perf_counter()
        time.sleep(0.05)
        self.recorder._on_press(10, 20, "left")
        time.sleep(0.03)
        self.recorder._on_press(-5, 7, "right")
        self.recorder._on_press(1, 1, "middle")
        self.assertEqual([(s.button, s.x, s.y) for s in self.steps],
                         [("left", 10, 20), ("right", -5, 7), ("middle", 1, 1)])
        self.assertGreaterEqual(self.steps[0].delay_ms, 50)
        self.assertGreaterEqual(self.steps[1].delay_ms, 30)
        self.assertGreaterEqual(self.steps[2].delay_ms, 1)  # never 0

    def test_skips_own_windows(self):
        self.own.add((5, 5))
        self.recorder._on_press(5, 5, "left")
        self.assertEqual(self.steps, [])


class StepsJsonTest(unittest.TestCase):
    def test_round_trip(self):
        steps = [Step(1250, "left", 812, 430), Step(40, "right", -300, 5)]
        self.assertEqual(load_steps(dump_steps(steps)), steps)

    def test_invalid_data_gives_nothing(self):
        good = {"delay_ms": 10, "button": "left", "x": 1, "y": 2}
        for data in (None, "x", {"a": 1}, [good, "x"], [dict(good, delay_ms=0)], [dict(good, button="side")],
                     [dict(good, x=1.5)], [dict(good, y=True)], [dict(good, extra=1)], [{"delay_ms": 10}]):
            self.assertEqual(load_steps(data), [], data)
        self.assertEqual(load_steps([]), [])


class PlaybackTest(unittest.TestCase):
    def setUp(self):
        self.mouse = FakeMouse()
        self.engine = ClickEngine(mouse=self.mouse)

    def tearDown(self):
        self.engine.stop()
        self.engine.join(5)

    def test_plays_steps_once_in_order_with_delays(self):
        steps = [Step(30, "left", 1, 2), Step(60, "right", 3, 4), Step(30, "middle", 5, 6)]
        started = time.perf_counter()
        self.engine.start(PlaybackConfig(steps))
        self.engine.join(5)
        elapsed = time.perf_counter() - started
        self.assertEqual(self.mouse.clicked, [("left", 1, (1, 2)), ("right", 1, (3, 4)),
                                              ("middle", 1, (5, 6))])
        self.assertEqual(self.engine.stop_reason, "finished")
        self.assertGreaterEqual(elapsed, 0.115)
        self.assertLess(elapsed, 2.0 if SHARED_CI else 0.2)

    def test_loop_repeats_until_stopped(self):
        steps = [Step(5, "left", 1, 1), Step(5, "left", 2, 2)]
        self.engine.start(PlaybackConfig(steps, loop=True))
        time.sleep(1.0 if SHARED_CI else 0.2)
        self.assertTrue(self.engine.running)
        self.engine.stop("Esc pressed")
        self.engine.join(5)
        positions = [pos for _, _, pos in self.mouse.clicked]
        self.assertGreaterEqual(len(positions), 4 if SHARED_CI else 7)  # at least one full loop
        self.assertEqual(positions[:4], [(1, 1), (2, 2), (1, 1), (2, 2)])
        self.assertEqual(self.engine.stop_reason, "Esc pressed")

    def test_failsafe_corner_stops_playback(self):
        self.engine.start(PlaybackConfig([Step(10, "left", 50, 50)], loop=True))
        time.sleep(0.1)
        self.mouse.position = (0, 0)
        self.engine.join(5)
        self.assertFalse(self.engine.running)
        self.assertEqual(self.engine.stop_reason, "mouse in top-left corner")

    def test_rejects_bad_playback(self):
        for bad in (PlaybackConfig([]), PlaybackConfig([Step(0, "left", 1, 1)]),
                    PlaybackConfig([Step(5, "side", 1, 1)])):
            with self.assertRaises(ValueError):
                self.engine.start(bad)
        self.assertFalse(self.engine.running)


if __name__ == "__main__":
    unittest.main()
