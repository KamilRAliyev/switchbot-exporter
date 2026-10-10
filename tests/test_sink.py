import unittest

from switchbot_exporter.sink import display_name, parse_names


class ParseNamesTest(unittest.TestCase):
    def test_basic_and_lowercase(self):
        self.assertEqual(parse_names("AA:BB=Bedroom, cc=office"),
                         {"aabb": "Bedroom", "cc": "office"})

    def test_keys_normalized(self):
        self.assertEqual(parse_names("AA-BB:CC=x"), {"aabbcc": "x"})

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

    def test_suffix_hit(self):
        names = parse_names("1065=Office")
        self.assertEqual(display_name("aa:bb:cc:dd:10:65", names), "Office")

    def test_full_id_hit_mixed_case_colons(self):
        names = parse_names("AA:bb:CC:dd:10:65=Office")
        self.assertEqual(display_name("aa:BB:cc:DD:10:65", names), "Office")

    def test_longest_suffix_wins(self):
        names = parse_names("1065=Short,dd1065=Long")
        self.assertEqual(display_name("aa:bb:cc:dd:10:65", names), "Long")

    def test_short_key_ignored(self):
        names = parse_names("065=X")
        self.assertEqual(display_name("aa:bb:cc:dd:10:65", names), "meter-1065")

    def test_miss_falls_back(self):
        names = parse_names("4a22=Bedroom")
        self.assertEqual(display_name("aa:bb:cc:dd:10:65", names), "meter-1065")


if __name__ == "__main__":
    unittest.main()
