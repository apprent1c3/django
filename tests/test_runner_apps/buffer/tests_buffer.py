import sys
from unittest import TestCase


class WriteToStdoutStderrTestCase(TestCase):
    def test_pass(self):
        """
        This is a comment
        """
        sys.stderr.write("Write to stderr.")
        sys.stdout.write("Write to stdout.")
        self.assertTrue(True)

    def test_fail(self):
        """
        This is a comment
        """
        sys.stderr.write("Write to stderr.")
        sys.stdout.write("Write to stdout.")
        self.assertTrue(False)
