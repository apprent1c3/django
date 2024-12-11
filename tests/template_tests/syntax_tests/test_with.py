from django.template import TemplateSyntaxError
from django.template.defaulttags import WithNode
from django.test import SimpleTestCase

from ..utils import setup


class WithTagTests(SimpleTestCase):
    at_least_with_one_msg = "'with' expected at least one variable assignment"

    @setup({"with01": "{% with key=dict.key %}{{ key }}{% endwith %}"})
    def test_with01(self):
        """
        Test the rendering of a template with a 'with' statement to extract a value from a nested dictionary.

        This test case checks if the 'with' statement in the template correctly assigns the value of 'dict.key' to a variable named 'key', and then renders the value of 'key' in the output string. The expected output is the string representation of the integer value assigned to 'dict.key'.
        """
        output = self.engine.render_to_string("with01", {"dict": {"key": 50}})
        self.assertEqual(output, "50")

    @setup({"legacywith01": "{% with dict.key as key %}{{ key }}{% endwith %}"})
    def test_legacywith01(self):
        """
        Tests the legacy \"with\" syntax for variable assignment in templates, 
        ensuring it correctly assigns and displays a value from a dictionary.
        """
        output = self.engine.render_to_string("legacywith01", {"dict": {"key": 50}})
        self.assertEqual(output, "50")

    @setup(
        {
            "with02": "{{ key }}{% with key=dict.key %}"
            "{{ key }}-{{ dict.key }}-{{ key }}"
            "{% endwith %}{{ key }}"
        }
    )
    def test_with02(self):
        """

        Tests the 'with' template tag functionality.

        This test case evaluates the rendering of a template that utilizes the 'with' tag to 
        temporarily modify the value of a variable. The 'with' block sets a new value for 'key', 
        which is then used within the block and should revert to its original value outside the block.

        The test checks if the rendering produces the expected output, taking into account 
        whether the template engine is configured to display an 'INVALID' placeholder for invalid 
        variables or to use the actual variable values.

        """
        output = self.engine.render_to_string("with02", {"dict": {"key": 50}})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID50-50-50INVALID")
        else:
            self.assertEqual(output, "50-50-50")

    @setup(
        {
            "legacywith02": "{{ key }}{% with dict.key as key %}"
            "{{ key }}-{{ dict.key }}-{{ key }}"
            "{% endwith %}{{ key }}"
        }
    )
    def test_legacywith02(self):
        output = self.engine.render_to_string("legacywith02", {"dict": {"key": 50}})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID50-50-50INVALID")
        else:
            self.assertEqual(output, "50-50-50")

    @setup({"with03": "{% with a=alpha b=beta %}{{ a }}{{ b }}{% endwith %}"})
    def test_with03(self):
        output = self.engine.render_to_string("with03", {"alpha": "A", "beta": "B"})
        self.assertEqual(output, "AB")

    @setup({"with-error01": "{% with dict.key xx key %}{{ key }}{% endwith %}"})
    def test_with_error01(self):
        """
        Test a template syntax error when using a 'with' statement with an invalid key.

        The test checks that rendering a template with a 'with' statement containing a dictionary key that does not exist raises a :class:`TemplateSyntaxError`. The test verifies that the error message is at least as informative as a certain expected message.
        """
        with self.assertRaisesMessage(TemplateSyntaxError, self.at_least_with_one_msg):
            self.engine.render_to_string("with-error01", {"dict": {"key": 50}})

    @setup({"with-error02": "{% with dict.key as %}{{ key }}{% endwith %}"})
    def test_with_error02(self):
        """
        Tests that a TemplateSyntaxError is raised when using the 'with' tag without specifying a variable to assign the value to.
        """
        with self.assertRaisesMessage(TemplateSyntaxError, self.at_least_with_one_msg):
            self.engine.render_to_string("with-error02", {"dict": {"key": 50}})


class WithNodeTests(SimpleTestCase):
    def test_repr(self):
        node = WithNode(nodelist=[], name="a", var="dict.key")
        self.assertEqual(repr(node), "<WithNode>")
