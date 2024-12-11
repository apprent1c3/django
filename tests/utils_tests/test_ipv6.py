import unittest

from django.utils.ipv6 import clean_ipv6_address, is_valid_ipv6_address


class TestUtilsIPv6(unittest.TestCase):
    def test_validates_correct_plain_address(self):
        self.assertTrue(is_valid_ipv6_address("fe80::223:6cff:fe8a:2e8a"))
        self.assertTrue(is_valid_ipv6_address("2a02::223:6cff:fe8a:2e8a"))
        self.assertTrue(is_valid_ipv6_address("1::2:3:4:5:6:7"))
        self.assertTrue(is_valid_ipv6_address("::"))
        self.assertTrue(is_valid_ipv6_address("::a"))
        self.assertTrue(is_valid_ipv6_address("2::"))

    def test_validates_correct_with_v4mapping(self):
        self.assertTrue(is_valid_ipv6_address("::ffff:254.42.16.14"))
        self.assertTrue(is_valid_ipv6_address("::ffff:0a0a:0a0a"))

    def test_validates_incorrect_plain_address(self):
        """
        .. function:: test_validates_incorrect_plain_address

            Tests the validation of incorrect plain IPv6 addresses.

            This test case checks that the function :func:`is_valid_ipv6_address` correctly identifies and rejects invalid IPv6 addresses. 
            The test covers a variety of invalid formats, including non-numeric characters, incorrect grouping, and addresses with too many or too few parts. 
            It ensures that only correctly formatted IPv6 addresses are accepted as valid.
        """
        self.assertFalse(is_valid_ipv6_address("foo"))
        self.assertFalse(is_valid_ipv6_address("127.0.0.1"))
        self.assertFalse(is_valid_ipv6_address("12345::"))
        self.assertFalse(is_valid_ipv6_address("1::2:3::4"))
        self.assertFalse(is_valid_ipv6_address("1::zzz"))
        self.assertFalse(is_valid_ipv6_address("1::2:3:4:5:6:7:8"))
        self.assertFalse(is_valid_ipv6_address("1:2"))
        self.assertFalse(is_valid_ipv6_address("1:::2"))
        self.assertFalse(is_valid_ipv6_address("fe80::223: 6cff:fe8a:2e8a"))
        self.assertFalse(is_valid_ipv6_address("2a02::223:6cff :fe8a:2e8a"))

    def test_validates_incorrect_with_v4mapping(self):
        self.assertFalse(is_valid_ipv6_address("::ffff:999.42.16.14"))
        self.assertFalse(is_valid_ipv6_address("::ffff:zzzz:0a0a"))
        # The ::1.2.3.4 format used to be valid but was deprecated
        # in RFC 4291 section 2.5.5.1.
        self.assertTrue(is_valid_ipv6_address("::254.42.16.14"))
        self.assertTrue(is_valid_ipv6_address("::0a0a:0a0a"))
        self.assertFalse(is_valid_ipv6_address("::999.42.16.14"))
        self.assertFalse(is_valid_ipv6_address("::zzzz:0a0a"))

    def test_cleans_plain_address(self):
        """

        Tests the function that cleans and formats IPv6 addresses.

        This test case checks if the function correctly converts IPv6 addresses to their 
        shortest form by removing leading zeros and collapsing consecutive sections of zeros.
        The test covers various address formats to ensure the function handles different 
        input scenarios correctly.

        The function should return an IPv6 address in its canonical form, which is the 
        shortest representation possible according to the IPv6 address syntax rules.

        """
        self.assertEqual(clean_ipv6_address("DEAD::0:BEEF"), "dead::beef")
        self.assertEqual(
            clean_ipv6_address("2001:000:a:0000:0:fe:fe:beef"), "2001:0:a::fe:fe:beef"
        )
        self.assertEqual(
            clean_ipv6_address("2001::a:0000:0:fe:fe:beef"), "2001:0:a::fe:fe:beef"
        )

    def test_cleans_with_v4_mapping(self):
        self.assertEqual(clean_ipv6_address("::ffff:0a0a:0a0a"), "::ffff:10.10.10.10")
        self.assertEqual(clean_ipv6_address("::ffff:1234:1234"), "::ffff:18.52.18.52")
        self.assertEqual(clean_ipv6_address("::ffff:18.52.18.52"), "::ffff:18.52.18.52")
        self.assertEqual(clean_ipv6_address("::ffff:0.52.18.52"), "::ffff:0.52.18.52")
        self.assertEqual(clean_ipv6_address("::ffff:0.0.0.0"), "::ffff:0.0.0.0")

    def test_unpacks_ipv4(self):
        self.assertEqual(
            clean_ipv6_address("::ffff:0a0a:0a0a", unpack_ipv4=True), "10.10.10.10"
        )
        self.assertEqual(
            clean_ipv6_address("::ffff:1234:1234", unpack_ipv4=True), "18.52.18.52"
        )
        self.assertEqual(
            clean_ipv6_address("::ffff:18.52.18.52", unpack_ipv4=True), "18.52.18.52"
        )
