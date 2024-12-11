from django.template.base import TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils.lorem_ipsum import COMMON_P, WORDS

from ..utils import setup


class LoremTagTests(SimpleTestCase):
    @setup({"lorem1": "{% lorem 3 w %}"})
    def test_lorem1(self):
        """

        Tests the rendering of the lorem template tag with a word count parameter.

        Verifies that the template engine correctly renders a string of lorem ipsum text
        with a specified number of words.

        The test case checks that the output of the rendered template matches the expected
        lorem ipsum string, ensuring that the template tag is working as expected.

        """
        output = self.engine.render_to_string("lorem1")
        self.assertEqual(output, "lorem ipsum dolor")

    @setup({"lorem_random": "{% lorem 3 w random %}"})
    def test_lorem_random(self):
        output = self.engine.render_to_string("lorem_random")
        words = output.split(" ")
        self.assertEqual(len(words), 3)
        for word in words:
            self.assertIn(word, WORDS)

    @setup({"lorem_default": "{% lorem %}"})
    def test_lorem_default(self):
        output = self.engine.render_to_string("lorem_default")
        self.assertEqual(output, COMMON_P)

    @setup({"lorem_syntax_error": "{% lorem 1 2 3 4 %}"})
    def test_lorem_syntax(self):
        msg = "Incorrect format for 'lorem' tag"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("lorem_syntax_error")

    @setup({"lorem_multiple_paragraphs": "{% lorem 2 p %}"})
    def test_lorem_multiple_paragraphs(self):
        """
        Tests the rendering of multiple paragraphs using the lorem template tag, verifying that the output contains the correct number of paragraph elements.
        """
        output = self.engine.render_to_string("lorem_multiple_paragraphs")
        self.assertEqual(output.count("<p>"), 2)

    @setup({"lorem_incorrect_count": "{% lorem two p %}"})
    def test_lorem_incorrect_count(self):
        """
        Tests that the lorem filter correctly handles invalid paragraph counts.

        Verifies that when an invalid count is provided to the lorem filter,
        it defaults to a single paragraph, ensuring the generated output is consistent.

        This test case covers the scenario where the loremm filter is used with an
        incorrect count argument, validating that the rendering engine behaves as expected.
        """
        output = self.engine.render_to_string("lorem_incorrect_count")
        self.assertEqual(output.count("<p>"), 1)
