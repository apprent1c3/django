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

        Tests the rendering of a template containing named end blocks.

        The function verifies that the template engine correctly processes named end blocks.
        A named end block is used to close a previously defined block, which allows for more
        flexible and readable template code. The test checks that the output of the template
        is rendered as expected, with the blocks correctly nested and closed.

        The expected output is a string where the blocks have been replaced with their
        corresponding content, resulting in the final rendered string.

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
        Tests the templating engine's handling of named endblocks, specifically verifying that it correctly raises a TemplateSyntaxError when a named endblock does not match its corresponding start block.
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
        Tests that a TemplateSyntaxError is raised when using named endblock tags in a template without proper nesting. 

        This test case verifies that the template engine correctly identifies and reports syntax errors when the endblock tags are not properly matched with their corresponding block tags. 

        Args: 
            None 

        Returns: 
            None 

        Raises: 
            TemplateSyntaxError: If the endblock tags are not properly nested in the template.
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
        """
        Test for template syntax error when using a named endblock with an incorrect block name. 

        This test case checks that the templating engine correctly raises a TemplateSyntaxError when a named endblock is used to close a block that does not have a matching open block with the same name.
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
        """
        Tests the rendering of named end blocks in templates.

        This test case verifies that the template engine correctly handles blocks with names
        and their corresponding endblock statements, ensuring the output is rendered as expected.

        :returns: None
        :raises: AssertionError if the rendered output does not match the expected result
        """
        output = self.engine.render_to_string("namedendblocks07")
        self.assertEqual(output, "1_2_3")
