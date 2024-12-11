from django.test import SimpleTestCase

from ..utils import setup

multiline_string = """
Hello,
boys.
How
are
you
gentlemen.
"""


class MultilineTests(SimpleTestCase):
    @setup({"multiline01": multiline_string})
    def test_multiline01(self):
        """
        Tests rendering of a multiline string.

        This test verifies that a given multiline string is rendered correctly by the engine.
        It checks if the output of the rendering process matches the original multiline string.
        The test case ensures the engine's ability to handle and preserve multiline text formatting.
        """
        output = self.engine.render_to_string("multiline01")
        self.assertEqual(output, multiline_string)
