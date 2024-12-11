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

        This test case verifies that the engine correctly renders a string containing multiple lines, 
        ensuring that the output matches the original multiline string. It is used to validate the 
        engine's ability to handle and preserve line breaks in the input string. 
        """
        output = self.engine.render_to_string("multiline01")
        self.assertEqual(output, multiline_string)
