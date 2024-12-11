import unittest

from django.utils.ipv6 import clean_ipv6_address, is_valid_ipv6_address


class TestUtilsIPv6(unittest.TestCase):
    def test_validates_correct_plain_address(self):
        """
        Test cases to validate correct plain IPv6 addresses.

        This function checks if the provided IPv6 addresses are correctly formatted and valid.
        Valid IPv6 addresses include various formats such as shortened and uncompressed addresses.
        The test covers a range of examples including link-local, global unicast, and zero-address.
        Each test case ensures that the address is recognized as valid by the is_valid_ipv6_address function.

        """
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

         Tests whether the function to validate IPv6 addresses correctly identifies invalid IPv6 addresses.

         This test case covers a variety of incorrect plain address formats, including those with:
         - Non-numeric characters
         - IPv4 addresses
         - Incorrect use of the '::' abbreviation
         - Too many colon-separated values
         - Insufficient colon-separated values
         - Invalid character usage within the address
         - Incorrect whitespace usage

         The test asserts that the function returns False for each of these invalid address formats.

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

        Tests the cleaning functionality of an IPv6 address.

        This function validates that the address cleaning process correctly simplifies
        IPv6 addresses by removing unnecessary leading zeros and applying zero suppression.
        It checks the cleaning of addresses with various formats to ensure they are
        converted to their shortest valid form.

        """
        self.assertEqual(clean_ipv6_address("DEAD::0:BEEF"), "dead::beef")
        self.assertEqual(
            clean_ipv6_address("2001:000:a:0000:0:fe:fe:beef"), "2001:0:a::fe:fe:beef"
        )
        self.assertEqual(
            clean_ipv6_address("2001::a:0000:0:fe:fe:beef"), "2001:0:a::fe:fe:beef"
        )

    def test_cleans_with_v4_mapping(self):
        """

        Tests the functionality of the clean_ipv6_address function with IPv4 mapped addresses.

        The function clean_ipv6_address is expected to convert IPv6 addresses in the ::ffff:xxxx:xxxx format 
        to their IPv4 notation. These tests cover various scenarios to ensure correct conversion, 
        including different numerical values and existing IPv4 notations.

        """
        self.assertEqual(clean_ipv6_address("::ffff:0a0a:0a0a"), "::ffff:10.10.10.10")
        self.assertEqual(clean_ipv6_address("::ffff:1234:1234"), "::ffff:18.52.18.52")
        self.assertEqual(clean_ipv6_address("::ffff:18.52.18.52"), "::ffff:18.52.18.52")
        self.assertEqual(clean_ipv6_address("::ffff:0.52.18.52"), "::ffff:0.52.18.52")
        self.assertEqual(clean_ipv6_address("::ffff:0.0.0.0"), "::ffff:0.0.0.0")

    def test_unpacks_ipv4(self):
        """

        Tests the functionality of unpacking IPv4 addresses embedded within IPv6 addresses.

        This test case validates the conversion of IPv4 addresses embedded in IPv6 addresses 
        in the format '::ffff:<ipv4>' to their standard IPv4 address representation.

        The test checks for correct unpacking of both numerical and dotted decimal notation 
        of the embedded IPv4 addresses, ensuring the output matches the expected IPv4 address 
        format.

        """
        self.assertEqual(
            clean_ipv6_address("::ffff:0a0a:0a0a", unpack_ipv4=True), "10.10.10.10"
        )
        self.assertEqual(
            clean_ipv6_address("::ffff:1234:1234", unpack_ipv4=True), "18.52.18.52"
        )
        self.assertEqual(
            clean_ipv6_address("::ffff:18.52.18.52", unpack_ipv4=True), "18.52.18.52"
        )
