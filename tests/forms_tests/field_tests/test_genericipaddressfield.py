from django.core.exceptions import ValidationError
from django.forms import GenericIPAddressField
from django.test import SimpleTestCase


class GenericIPAddressFieldTest(SimpleTestCase):
    def test_generic_ipaddress_invalid_arguments(self):
        with self.assertRaises(ValueError):
            GenericIPAddressField(protocol="hamster")
        with self.assertRaises(ValueError):
            GenericIPAddressField(protocol="ipv4", unpack_ipv4=True)

    def test_generic_ipaddress_as_generic(self):
        # The edge cases of the IPv6 validation code are not deeply tested
        # here, they are covered in the tests for django.utils.ipv6
        f = GenericIPAddressField()
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual(f.clean(" 127.0.0.1 "), "127.0.0.1")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("foo")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("127.0.0.")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("1.2.3.4.5")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("256.125.1.5")
        self.assertEqual(
            f.clean(" fe80::223:6cff:fe8a:2e8a "), "fe80::223:6cff:fe8a:2e8a"
        )
        self.assertEqual(
            f.clean(" 2a02::223:6cff:fe8a:2e8a "), "2a02::223:6cff:fe8a:2e8a"
        )
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("12345:2:3:4")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1::2:3::4")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("foo::223:6cff:fe8a:2e8a")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1::2:3:4:5:6:7:8")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1:2")

    def test_generic_ipaddress_as_ipv4_only(self):
        """
        Tests the GenericIPAddressField when restricted to IPv4-only protocol.

        This test case checks the validation of IPv4 addresses, ensuring that the field:
        - raises a ValidationError when no value is provided (empty string or None)
        - validates and removes leading/trailing whitespace from valid IPv4 addresses
        - rejects invalid IPv4 addresses, including:
          - strings that do not resemble an IPv4 address
          - incomplete or malformed IPv4 addresses
          - IPv6 addresses
          - IPv4 addresses with out-of-range values (e.g. octets greater than 255)

        """
        f = GenericIPAddressField(protocol="IPv4")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        self.assertEqual(f.clean(" 127.0.0.1 "), "127.0.0.1")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv4 address.'"):
            f.clean("foo")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv4 address.'"):
            f.clean("127.0.0.")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv4 address.'"):
            f.clean("1.2.3.4.5")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv4 address.'"):
            f.clean("256.125.1.5")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv4 address.'"):
            f.clean("fe80::223:6cff:fe8a:2e8a")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv4 address.'"):
            f.clean("2a02::223:6cff:fe8a:2e8a")

    def test_generic_ipaddress_as_ipv6_only(self):
        """
        Tests that the GenericIPAddressField behaves correctly when configured to only accept IPv6 addresses.

        This test case verifies that validation errors are raised when attempting to clean invalid or empty input, and that valid IPv6 addresses are cleaned and returned as expected.

        Validation is performed on various types of invalid input, including empty strings, non-IPv6 addresses such as IPv4 addresses, and malformed IPv6 addresses. It also checks that valid IPv6 addresses, including those with leading or trailing whitespace, are accepted and cleaned correctly.

        Error messages are verified to be the expected ones, which include 'This field is required.', 'Enter a valid IPv6 address.', and 'This is not a valid IPv6 address.'
        """
        f = GenericIPAddressField(protocol="IPv6")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv6 address.'"):
            f.clean("127.0.0.1")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv6 address.'"):
            f.clean("foo")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv6 address.'"):
            f.clean("127.0.0.")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv6 address.'"):
            f.clean("1.2.3.4.5")
        with self.assertRaisesMessage(ValidationError, "'Enter a valid IPv6 address.'"):
            f.clean("256.125.1.5")
        self.assertEqual(
            f.clean(" fe80::223:6cff:fe8a:2e8a "), "fe80::223:6cff:fe8a:2e8a"
        )
        self.assertEqual(
            f.clean(" 2a02::223:6cff:fe8a:2e8a "), "2a02::223:6cff:fe8a:2e8a"
        )
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("12345:2:3:4")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1::2:3::4")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("foo::223:6cff:fe8a:2e8a")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1::2:3:4:5:6:7:8")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1:2")

    def test_generic_ipaddress_as_generic_not_required(self):
        f = GenericIPAddressField(required=False)
        self.assertEqual(f.clean(""), "")
        self.assertEqual(f.clean(None), "")
        self.assertEqual(f.clean("127.0.0.1"), "127.0.0.1")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("foo")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("127.0.0.")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("1.2.3.4.5")
        with self.assertRaisesMessage(
            ValidationError, "'Enter a valid IPv4 or IPv6 address.'"
        ):
            f.clean("256.125.1.5")
        self.assertEqual(
            f.clean(" fe80::223:6cff:fe8a:2e8a "), "fe80::223:6cff:fe8a:2e8a"
        )
        self.assertEqual(
            f.clean(" 2a02::223:6cff:fe8a:2e8a "), "2a02::223:6cff:fe8a:2e8a"
        )
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("12345:2:3:4")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1::2:3::4")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("foo::223:6cff:fe8a:2e8a")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1::2:3:4:5:6:7:8")
        with self.assertRaisesMessage(
            ValidationError, "'This is not a valid IPv6 address.'"
        ):
            f.clean("1:2")

    def test_generic_ipaddress_normalization(self):
        # Test the normalizing code
        """
        .. method:: test_generic_ipaddress_normalization(self)

            Tests the normalization of IP addresses using the GenericIPAddressField.

            This test case covers the cleaning and normalization of various IP address formats, including IPv4 and IPv6.
            It verifies that the field correctly removes unnecessary whitespace, collapses consecutive sections of zeros in IPv6 addresses,
            and converts IPv4 addresses embedded in IPv6 addresses to their standard dotted decimal notation when the unpack_ipv4 option is enabled.
            The test ensures that the field produces consistent and standardized output for different input formats.
        """
        f = GenericIPAddressField()
        self.assertEqual(f.clean(" ::ffff:0a0a:0a0a  "), "::ffff:10.10.10.10")
        self.assertEqual(f.clean(" ::ffff:10.10.10.10  "), "::ffff:10.10.10.10")
        self.assertEqual(
            f.clean(" 2001:000:a:0000:0:fe:fe:beef  "), "2001:0:a::fe:fe:beef"
        )
        self.assertEqual(
            f.clean(" 2001::a:0000:0:fe:fe:beef  "), "2001:0:a::fe:fe:beef"
        )

        f = GenericIPAddressField(unpack_ipv4=True)
        self.assertEqual(f.clean(" ::ffff:0a0a:0a0a"), "10.10.10.10")
