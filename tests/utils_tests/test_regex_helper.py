import re
import unittest

from django.test import SimpleTestCase
from django.utils import regex_helper


class NormalizeTests(unittest.TestCase):
    def test_empty(self):
        pattern = r""
        expected = [("", [])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_escape(self):
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
        """
        Tests the normalization of a non-capturing group in a regular expression pattern.

        The function verifies that the regex_helper.normalize function correctly handles a non-capturing group,
        defined by the `(?:)` syntax, and returns the expected result.

        This test case checks that the normalization process identifies the group content and returns it
        along with an empty list of capturing groups, as non-capturing groups do not capture any values.

        The expected output is a list containing a tuple with the group content and an empty list of captures.
        """
        pattern = r"(?:non-capturing)"
        expected = [("non-capturing", [])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_group_named(self):
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
