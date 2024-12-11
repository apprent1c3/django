from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ..utils import setup


class NamedEndblockTests(SimpleTestCase):
    @setup(
        {
            "namedendblocks01": "1{% block first %}_{% block second %}"
            "2{% endblock second %}_{% endblock first %}3"
        }
    )
    def test_namedendblocks01(self):
        """
        Checks the rendering of a template containing named endblocks, verifying that the engine correctly interprets and replaces the blocks with empty content, resulting in the expected output string.
        """
        output = self.engine.render_to_string("namedendblocks01")
        self.assertEqual(output, "1_2_3")

    # Unbalanced blocks
    @setup(
        {
            "namedendblocks02": "1{% block first %}_{% block second %}"
            "2{% endblock first %}_{% endblock second %}3"
        }
    )
    def test_namedendblocks02(self):
        """
        Tests that the template engine raises a TemplateSyntaxError when a named endblock directive does not match the corresponding block directive in the template. 

        This test case checks the engine's handling of improperly nested or mismatched named block and endblock tags.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("namedendblocks02")

    @setup(
        {
            "namedendblocks03": "1{% block first %}_{% block second %}"
            "2{% endblock %}_{% endblock second %}3"
        }
    )
    def test_namedendblocks03(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("namedendblocks03")

    @setup(
        {
            "namedendblocks04": "1{% block first %}_{% block second %}"
            "2{% endblock second %}_{% endblock third %}3"
        }
    )
    def test_namedendblocks04(self):
        """
        Tests that a TemplateSyntaxError is raised when an endblock tag does not match the outermost block tag it is nested within.

        This test case checks that the templating engine correctly enforces the matching of block and endblock tags, even when the tags are named. It verifies that an error is raised when a mismatch occurs, ensuring that the templating engine maintains a correct and consistent state.

        The test is focused on the specific scenario where an endblock tag is used without a corresponding block tag, demonstrating the importance of proper block nesting in template syntax.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("namedendblocks04")

    @setup(
        {
            "namedendblocks05": (
                "1{% block first %}_{% block second %}2{% endblock first %}"
            )
        }
    )
    def test_namedendblocks05(self):
        """
        Test that the template engine raises a TemplateSyntaxError when named endblocks are not properly matched.

        This test case checks if the engine correctly identifies and reports a syntax error
        when a named endblock does not have a corresponding start block with the same name.

        Raises:
            TemplateSyntaxError: If the engine fails to raise an exception for mismatched named endblocks.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("namedendblocks05")

    # Mixed named and unnamed endblocks
    @setup(
        {
            "namedendblocks06": "1{% block first %}_{% block second %}"
            "2{% endblock %}_{% endblock first %}3"
        }
    )
    def test_namedendblocks06(self):
        """
        Mixed named and unnamed endblocks
        """
        output = self.engine.render_to_string("namedendblocks06")
        self.assertEqual(output, "1_2_3")

    @setup(
        {
            "namedendblocks07": "1{% block first %}_{% block second %}"
            "2{% endblock second %}_{% endblock %}3"
        }
    )
    def test_namedendblocks07(self):
        output = self.engine.render_to_string("namedendblocks07")
        self.assertEqual(output, "1_2_3")
