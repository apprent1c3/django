from django.template import TemplateSyntaxError
from django.template.defaulttags import WithNode
from django.test import SimpleTestCase

from ..utils import setup


class WithTagTests(SimpleTestCase):
    at_least_with_one_msg = "'with' expected at least one variable assignment"

    @setup({"with01": "{% with key=dict.key %}{{ key }}{% endwith %}"})
    def test_with01(self):
        """

        Tests rendering of the 'with' template tag with a dictionary value.

        This test case verifies that the 'with' tag correctly assigns the value of a dictionary key to a variable and makes it available for use within the template. 

        The test provides a dictionary with a key-value pair as input to the template engine and checks if the rendered output matches the expected string representation of the dictionary value.

        """
        output = self.engine.render_to_string("with01", {"dict": {"key": 50}})
        self.assertEqual(output, "50")

    @setup({"legacywith01": "{% with dict.key as key %}{{ key }}{% endwith %}"})
    def test_legacywith01(self):
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
        """
        Test the legacy 'with' syntax in templating engine.

        This test case evaluates the behavior of the 'with' statement when used to
        reassign a value within a template. It checks if the original value is
        preserved after the 'with' block and if the reassignments within the block
        remain in effect. The test also considers the case when the templating engine
        uses a string to indicate invalid values, and verifies the output accordingly.
        """
        output = self.engine.render_to_string("legacywith02", {"dict": {"key": 50}})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID50-50-50INVALID")
        else:
            self.assertEqual(output, "50-50-50")

    @setup({"with03": "{% with a=alpha b=beta %}{{ a }}{{ b }}{% endwith %}"})
    def test_with03(self):
        """
        Tests the functionality of the 'with' statement in templating, specifically the assignment of multiple variables within a 'with' block. 
         The test case checks if the assigned variables 'a' and 'b' are correctly replaced with their respective values 'alpha' and 'beta' in the output string. 
         It verifies that the rendered output matches the expected result, ensuring proper functionality of the templating engine.
        """
        output = self.engine.render_to_string("with03", {"alpha": "A", "beta": "B"})
        self.assertEqual(output, "AB")

    @setup({"with-error01": "{% with dict.key xx key %}{{ key }}{% endwith %}"})
    def test_with_error01(self):
        """
        Tests that the templating engine correctly raises a TemplateSyntaxError when using the 'with' statement with an invalid syntax, specifically when the 'as' keyword is missing, and that the raised error message meets the expected minimum requirements.
        """
        with self.assertRaisesMessage(TemplateSyntaxError, self.at_least_with_one_msg):
            self.engine.render_to_string("with-error01", {"dict": {"key": 50}})

    @setup({"with-error02": "{% with dict.key as %}{{ key }}{% endwith %}"})
    def test_with_error02(self):
        with self.assertRaisesMessage(TemplateSyntaxError, self.at_least_with_one_msg):
            self.engine.render_to_string("with-error02", {"dict": {"key": 50}})


class WithNodeTests(SimpleTestCase):
    def test_repr(self):
        """

        Tests the repr function of the WithNode class.

        Verifies that the repr function returns a string representation of the WithNode object,
        which should be '<WithNode>' regardless of the node's properties.

        """
        node = WithNode(nodelist=[], name="a", var="dict.key")
        self.assertEqual(repr(node), "<WithNode>")
