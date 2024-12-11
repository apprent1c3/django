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
        """
        Tests the normalization of a regular expression pattern with escape sequences.

        Verifies that special characters such as caret (^), dollar sign ($), dot (.), 
        pipe (|), question mark (?), asterisk (*), plus sign (+), parentheses, and 
        brackets are properly escaped and normalized. The test case checks if the 
        function correctly converts the input pattern into the expected normalized form.

        This test is crucial to ensure the function behaves correctly with complex 
        patterns containing multiple special characters, which is essential for various 
        text processing and matching applications. The outcome of this test guarantees 
        the function's reliability in handling regular expressions with escape sequences.
        """
        pattern = r"\\\^\$\.\|\?\*\+\(\)\["
        expected = [("\\^$.|?*+()[", [])]
        result = regex_helper.normalize(pattern)
        self.assertEqual(result, expected)

    def test_group_positional(self):
        """
        Tests the normalization of a regular expression pattern with group positional notation.

         The function verifies that the input pattern, containing capturing groups, is correctly transformed into a normalized form with group references.

         The normalized form consists of a string with group references, such as ``%(_group_name)s``, and a list of group names.

         In this specific test case, the input pattern '(.*)-(.+)' is expected to be normalized to a string with group references ' `_0` ' and ' `_1` ', along with a list of the corresponding group names.

         The test asserts that the output of the `regex_helper.normalize` function matches the expected normalized form.
        """
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
        Tests behavior of compiling regular expressions with flags when a pre-compiled regex is provided, verifying that an AssertionError is raised when flags are used with an already compiled pattern.
        """
        test_pattern = re.compile("test")
        lazy_test_pattern = regex_helper._lazy_re_compile(test_pattern, re.I)
        msg = "flags must be empty if regex is passed pre-compiled"
        with self.assertRaisesMessage(AssertionError, msg):
            lazy_test_pattern.match("TEST")
