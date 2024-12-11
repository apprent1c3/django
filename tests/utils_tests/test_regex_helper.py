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
        """
        Tests the behavior of the regex_helper when a pre-compiled regular expression pattern is passed with flags.

        Verifies that an AssertionError is raised when attempting to match a string against a pre-compiled regex pattern with non-empty flags, ensuring that the flags provided are correctly validated in such scenarios.
        """
        test_pattern = re.compile("test")
        lazy_test_pattern = regex_helper._lazy_re_compile(test_pattern, re.I)
        msg = "flags must be empty if regex is passed pre-compiled"
        with self.assertRaisesMessage(AssertionError, msg):
            lazy_test_pattern.match("TEST")
