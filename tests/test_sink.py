import unittest

from switchbot_exporter.sink import display_name, parse_names


class ParseNamesTest(unittest.TestCase):
    def test_basic_and_lowercase(self):
        self.assertEqual(parse_names("AA:BB=Bedroom, cc=office"),
                         {"aa:bb": "Bedroom", "cc": "office"})

    def test_empty_and_none(self):
        self.assertEqual(parse_names(None), {})
        self.assertEqual(parse_names(""), {})

    def test_malformed_ignored(self):
        self.assertEqual(parse_names("novalue,=noaddr,addr=,,ok=fine"), {"ok": "fine"})

    def test_name_may_contain_equals(self):
        self.assertEqual(parse_names("a=b=c"), {"a": "b=c"})


class DisplayNameTest(unittest.TestCase):
    def test_configured_case_insensitive(self):
        self.assertEqual(display_name("AA:BB", {"aa:bb": "bedroom"}), "bedroom")

    def test_fallback_mac(self):
        self.assertEqual(display_name("AA:BB:CC:DD:EE:FF", {}), "meter-eeff")

    def test_fallback_uuid(self):
        self.assertEqual(display_name("12345678-ABCD-0000-0000-00000000F00D", {}), "meter-f00d")


if __name__ == "__main__":
    unittest.main()
