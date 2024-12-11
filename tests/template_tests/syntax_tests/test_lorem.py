from django.template.base import TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils.lorem_ipsum import COMMON_P, WORDS

from ..utils import setup


class LoremTagTests(SimpleTestCase):
    @setup({"lorem1": "{% lorem 3 w %}"})
    def test_lorem1(self):
        """

        Tests the lorem text rendering functionality.

        This test case verifies that the lorem template tag generates the expected
        lorem ipsum text. The test renders a template containing the lorem tag with
        a specified word count and checks if the resulting output matches the
        expected text.

        The test configuration includes a setup with a lorem template variable
        named 'lorem1' that is set to render 3 words of lorem ipsum text.

        """
        output = self.engine.render_to_string("lorem1")
        self.assertEqual(output, "lorem ipsum dolor")

    @setup({"lorem_random": "{% lorem 3 w random %}"})
    def test_lorem_random(self):
        """
        Tests the rendering of a random 3-word lorem ipsum string.

        Verifies that the output contains exactly 3 words and that each word is a valid lorem ipsum word.

        :raises AssertionError: if the output does not contain exactly 3 words or if any word is not a valid lorem ipsum word
        """
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
        """

        Tests that a TemplateSyntaxError is raised with the correct error message when the 'lorem' tag is used with an incorrect format.

        The test case verifies that the error message 'Incorrect format for 'lorem' tag' is displayed when the 'lorem' tag is used with more than the expected number of arguments.

        """
        msg = "Incorrect format for 'lorem' tag"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("lorem_syntax_error")

    @setup({"lorem_multiple_paragraphs": "{% lorem 2 p %}"})
    def test_lorem_multiple_paragraphs(self):
        """
        Test that the lorem filter correctly generates multiple paragraphs of text.

        The test case checks if rendering a template containing the lorem filter with multiple paragraphs produces the expected HTML output, specifically verifying that the correct number of paragraph tags are generated.
        """
        output = self.engine.render_to_string("lorem_multiple_paragraphs")
        self.assertEqual(output.count("<p>"), 2)

    @setup({"lorem_incorrect_count": "{% lorem two p %}"})
    def test_lorem_incorrect_count(self):
        """

        Tests the rendering of a lorem text with an incorrect count.

        Verifies that when an invalid count is provided to the lorem filter,
        it defaults to a single paragraph, ensuring the output is still valid.

        """
        output = self.engine.render_to_string("lorem_incorrect_count")
        self.assertEqual(output.count("<p>"), 1)
