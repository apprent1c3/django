import re
import unittest

from django.test import SimpleTestCase
from django.utils import regex_helper


class NormalizeTests(unittest.TestCase):
    def test_empty(self):
        """
        Tests the normalization of an empty regular expression pattern.

        Verifies that an empty pattern is normalized correctly, returning an expected result.
        The normalization process should handle this edge case and return a tuple containing an empty string and an empty list.
        This test ensures the regex_helper module's normalize function behaves as expected with invalid or edge case inputs.
        """
        pattern = r""
        expected = [("", [])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_escape(self):
        """

        Tests the normalization of a regular expression pattern that contains special escape characters.

        The function verifies that the regex_helper.normalize method correctly handles a pattern with
        special characters such as ^, $,., |,?, *, +, (, ), and [ by checking the output against an expected result.

        The expected result is a normalized pattern that contains the special characters without any additional escaping.

        """
        pattern = r"\\\^\$\.\|\?\*\+\(\)\["
        expected = [("\\^$.|?*+()[", [])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_group_positional(self):
        pattern = r"(.*)-(.+)"
        expected = [("%(_0)s-%(_1)s", ["_0", "_1"])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_group_noncapturing(self):
        pattern = r"(?:non-capturing)"
        expected = [("non-capturing", [])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_group_named(self):
        """

        Tests the functionality of the regex_helper.normalize function 
        for a regular expression pattern with named groups.

        This function verifies that the pattern is successfully normalized 
        and the group names are correctly extracted. The expected output 
        is a list containing the normalized pattern and the names of the 
        groups in the order they appear.

        The function uses a pattern with two named groups, 'first_group_name' 
        and 'second_group_name', separated by a hyphen to test the normalization 
        process.

        """
        pattern = r"(?P<first_group_name>.*)-(?P<second_group_name>.*)"
        expected = [
            (
                "%(first_group_name)s-%(second_group_name)s",
                ["first_group_name", "second_group_name"],
            )
        ]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_group_backreference(self):
        pattern = r"(?P<first_group_name>.*)-(?P=first_group_name)"
        expected = [("%(first_group_name)s-%(first_group_name)s", ["first_group_name"])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)


class LazyReCompileTests(SimpleTestCase):
    def test_flags_with_pre_compiled_regex(self):
        test_pattern = re.compile("test")
        lazy_test_pattern = regex_helper._lazy_re_compile(test_pattern, re.I)
        msg = "flags must be empty if regex is passed pre-compiled"
        with self.assertRaisesMessage(AssertionError, msg):
            lazy_test_pattern.match("TEST")
