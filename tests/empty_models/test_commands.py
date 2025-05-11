import io

from django.core.management import call_command
from django.test import TestCase


class CoreCommandsNoOutputTests(TestCase):
    available_apps = ["empty_models"]

    def test_sqlflush_no_tables(self):
        """
        Tests that the sqlflush command correctly handles the case where no tables are found.
        """
        out = io.StringIO()
        err = io.StringIO()
        call_command("sqlflush", stdout=out, stderr=err)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "No tables found.\n")

    def test_sqlsequencereset_no_sequences(self):
        """
        Tests that the sqlsequencereset command correctly handles a scenario where no sequences are found, ensuring it produces the expected output and error messages.
        """
        out = io.StringIO()
        err = io.StringIO()
        call_command("sqlsequencereset", "empty_models", stdout=out, stderr=err)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "No sequences found.\n")
