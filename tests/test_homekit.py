import asyncio
import os
import tempfile
import unittest
from unittest import mock

from pyhap.loader import Loader

from switchbot_exporter.decode import Reading
from switchbot_exporter.sinks.homekit import HomeKitSink, stable_aid


class FakeDriver:
    """Stands in for AccessoryDriver: real loader, no network."""

    def __init__(self):
        self.loader = Loader()
        self.accessory = None
        self.published = []
        self.config_changed = mock.Mock()
        self.async_start = mock.AsyncMock()
        self.async_stop = mock.AsyncMock()

    def add_accessory(self, accessory):
        self.accessory = accessory

    def publish(self, data, sender_client_addr=None, immediate=False):
        self.published.append(data)


class HomeKitSinkTest(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.driver = FakeDriver()
        self.sink = HomeKitSink("homekit.state", {"dev1": "bedroom"},
                                warmup=0, stale_after=600.0, clock=lambda: self.t)
        self.sink._attach(self.driver)
        self.reading = Reading("Meter", 21.5, 40, 90)

    def publish(self):
        asyncio.run(self.sink._publish())

    def acc(self, device_id="dev1"):
        return self.sink._accessories[device_id]

    def test_values_after_publish(self):
        self.sink.update("dev1", self.reading, -60)
        self.assertEqual(self.sink._accessories, {})  # buffered during warmup
        self.publish()
        acc = self.acc()
        self.assertEqual(acc.display_name, "bedroom")
        self.assertEqual(acc.temperature.value, 21.5)
        self.assertEqual(acc.humidity.value, 40)
        self.assertEqual(acc.battery_level.value, 90)
        self.assertEqual(acc.low_battery.value, 0)
        self.assertEqual([c.value for c in acc.faults], [0, 0])
        self.driver.async_start.assert_awaited_once()
        self.assertIn(acc.aid, self.driver.accessory.accessories)

    def test_update_changes_values(self):
        self.sink.update("dev1", self.reading, -60)
        self.publish()
        self.sink.update("dev1", Reading("Meter", -3.5, 55, 80), -60)
        acc = self.acc()
        self.assertEqual(acc.temperature.value, -3.5)
        self.assertEqual(acc.humidity.value, 55)

    def test_low_battery_threshold(self):
        self.sink.update("a", Reading("Meter", 20.0, 40, 19), -60)
        self.sink.update("b", Reading("Meter", 20.0, 40, 20), -60)
        self.publish()
        self.assertEqual(self.acc("a").low_battery.value, 1)
        self.assertEqual(self.acc("b").low_battery.value, 0)

    def test_fault_after_stale_and_cleared(self):
        self.sink.update("dev1", self.reading, -60)
        self.publish()
        self.t = 599.0
        self.sink.check_stale()
        self.assertEqual([c.value for c in self.acc().faults], [0, 0])
        self.t = 600.0
        self.sink.check_stale()
        self.assertEqual([c.value for c in self.acc().faults], [1, 1])
        self.sink.update("dev1", self.reading, -60)
        self.assertEqual([c.value for c in self.acc().faults], [0, 0])

    def test_late_device_added_and_config_bumped(self):
        self.publish()
        self.driver.config_changed.assert_not_called()
        self.sink.update("dev2", self.reading, -60)
        self.driver.config_changed.assert_called_once()
        self.assertEqual(self.acc("dev2").display_name, "meter-dev2")
        self.assertEqual(self.acc("dev2").temperature.value, 21.5)

    def test_stable_aid(self):
        self.assertEqual(stable_aid("AA:BB"), stable_aid("aa:bb"))
        self.assertNotIn(stable_aid("x", taken={stable_aid("x")}), (stable_aid("x"), 1, 7))
        self.assertGreaterEqual(stable_aid("x"), 2)


class LifecycleTest(unittest.TestCase):
    def test_start_stop_with_mock_driver(self):
        async def run():
            with tempfile.TemporaryDirectory() as d, \
                    mock.patch("switchbot_exporter.sinks.homekit.AccessoryDriver",
                               return_value=FakeDriver()) as cls:
                sink = HomeKitSink(os.path.join(d, "s.state"), warmup=0.01)
                await sink.start()
                sink.update("dev1", Reading("Meter", 21.5, 40, 90), -60)
                await asyncio.sleep(0.05)
                self.assertTrue(sink._published)
                self.assertIs(cls.call_args[1]["loop"], asyncio.get_running_loop())
                await sink.stop()
                sink._driver.async_stop.assert_awaited_once()
                self.assertEqual(sink._tasks, [])
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
