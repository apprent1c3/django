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
        Tests the rendering of named endblocks in a template.

        This test case verifies that the template engine correctly handles the termination
        of blocks using the \"endblock\" tag with a name, ensuring that the blocks are properly
        closed and the template is rendered as expected.

        The test renders a template containing nested blocks with named endblocks and
        asserts that the output matches the expected result, confirming the correct
        functionality of the named endblock syntax.

        :raises AssertionError: if the rendered output does not match the expected string
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
        Tests the template engine's handling of named endblocks, verifying that a TemplateSyntaxError is raised when endblocks are not properly matched. 

        This test case checks the engine's ability to detect incorrect usage of named endblocks in a template, ensuring that it correctly enforces the requirement that endblocks must have a corresponding start block with a matching name.
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
        """
        Tests that the template engine correctly raises a TemplateSyntaxError when encountering a named endblock tag that does not match the corresponding block tag.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("namedendblocks03")

    @setup(
        {
            "namedendblocks04": "1{% block first %}_{% block second %}"
            "2{% endblock second %}_{% endblock third %}3"
        }
    )
    def test_namedendblocks04(self):
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
        Test that using named endblocks with the wrong name raises a TemplateSyntaxError.

        This test case checks that the template engine correctly identifies and reports syntax errors when an endblock tag does not match the corresponding block tag. It verifies that a TemplateSyntaxError is raised when the template contains named endblocks with incorrect names.
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
