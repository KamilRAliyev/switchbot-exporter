import unittest
from unittest import mock

from prometheus_client.exposition import generate_latest

from switchbot_exporter.decode import Reading
from switchbot_exporter.sinks.prometheus import PrometheusSink

LABELS = 'device="dev1",model="Meter",name="bedroom"'


class PrometheusSinkTest(unittest.TestCase):
    def setUp(self):
        self.sink = PrometheusSink(0, {"dev1": "bedroom"})

    def scrape(self):
        return generate_latest(self.sink.registry).decode().splitlines()

    def test_values_and_labels(self):
        with mock.patch("time.time", return_value=1700000000.0):
            self.sink.update("dev1", Reading("Meter", 21.5, 40, 90), -60)
        lines = self.scrape()
        for expected in (
            "switchbot_temperature_celsius{%s} 21.5" % LABELS,
            "switchbot_humidity_percent{%s} 40.0" % LABELS,
            "switchbot_battery_percent{%s} 90.0" % LABELS,
            "switchbot_rssi_dbm{%s} -60.0" % LABELS,
            "switchbot_last_seen_timestamp_seconds{%s} 1.7e+09" % LABELS,
        ):
            self.assertIn(expected, lines)

    def test_default_name(self):
        self.sink.update("aa:bb:cc:dd:ee:ff", Reading("MeterPlus", 5.0, 50, 80), -70)
        self.assertIn('name="meter-eeff"', "\n".join(self.scrape()))

    def test_second_update_overwrites(self):
        self.sink.update("dev1", Reading("Meter", 21.5, 40, 90), -60)
        self.sink.update("dev1", Reading("Meter", 22.5, 41, 89), -55)
        lines = self.scrape()
        temps = [l for l in lines if l.startswith("switchbot_temperature_celsius{")]
        self.assertEqual(temps, ["switchbot_temperature_celsius{%s} 22.5" % LABELS])
        self.assertIn("switchbot_humidity_percent{%s} 41.0" % LABELS, lines)
        self.assertIn("switchbot_rssi_dbm{%s} -55.0" % LABELS, lines)

    def test_stop_without_start(self):
        import asyncio
        asyncio.run(self.sink.stop())


if __name__ == "__main__":
    unittest.main()
