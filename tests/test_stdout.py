import io
import unittest

from switchbot_exporter.decode import Reading
from switchbot_exporter.sinks.stdout import StdoutSink


class StdoutSinkTest(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.out = io.StringIO()
        self.sink = StdoutSink(60.0, {"dev1": "bedroom"}, out=self.out, clock=lambda: self.t)
        self.r1 = Reading("Meter", 21.5, 40, 90)
        self.r2 = Reading("Meter", 22.0, 40, 90)

    def lines(self):
        return self.out.getvalue().splitlines()

    def test_dedupe_within_interval(self):
        self.sink.update("dev1", self.r1, -60)
        self.t = 30.0
        self.sink.update("dev1", self.r1, -60)
        self.assertEqual(len(self.lines()), 1)

    def test_reprint_after_interval(self):
        self.sink.update("dev1", self.r1, -60)
        self.t = 61.0
        self.sink.update("dev1", self.r1, -60)
        self.assertEqual(len(self.lines()), 2)

    def test_change_prints_immediately(self):
        self.sink.update("dev1", self.r1, -60)
        self.sink.update("dev1", self.r2, -60)
        self.assertEqual(len(self.lines()), 2)

    def test_devices_independent(self):
        self.sink.update("dev1", self.r1, -60)
        self.sink.update("dev2", self.r1, -60)
        self.assertEqual(len(self.lines()), 2)

    def test_line_has_name_and_id(self):
        self.sink.update("dev1", self.r1, -60)
        self.sink.update("abcd1234", self.r1, -70)
        first, second = self.lines()
        self.assertIn("bedroom", first)
        self.assertIn("dev1", first)
        self.assertIn("21.5C", first)
        self.assertIn("meter-1234", second)


if __name__ == "__main__":
    unittest.main()
