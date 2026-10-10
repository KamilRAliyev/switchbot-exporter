import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from switchbot_exporter.decode import Reading, decode_meter


class DecodeTest(unittest.TestCase):
    def test_positive_temp(self):
        # model T, battery 0x64=100, 23.5C, 55%
        r = decode_meter(bytes([0x54, 0x00, 0x64, 0x05, 0x97, 0x37]))
        self.assertEqual(r, Reading("Meter", 23.5, 55, 100))

    def test_negative_temp(self):
        r = decode_meter(bytes([0x54, 0x00, 0x50, 0x03, 0x05, 0x40]))
        self.assertEqual(r, Reading("Meter", -5.3, 64, 80))

    def test_meter_plus(self):
        r = decode_meter(bytes([0x69, 0x00, 0x5A, 0x00, 0x94, 0x28]))
        self.assertEqual(r.model, "MeterPlus")
        self.assertEqual(r.temperature_c, 20.0)

    def test_fahrenheit_flag_ignored(self):
        r = decode_meter(bytes([0x54, 0x00, 0x64, 0x05, 0x97, 0xB7]))
        self.assertEqual(r.humidity, 55)

    def test_wrong_model(self):
        self.assertIsNone(decode_meter(bytes([0x48, 0, 0x64, 0, 0x97, 0x37])))

    def test_too_short(self):
        self.assertIsNone(decode_meter(bytes([0x54, 0x00, 0x64])))


if __name__ == "__main__":
    unittest.main()
