from django.template import TemplateSyntaxError
from django.template.defaulttags import WithNode
from django.test import SimpleTestCase

from ..utils import setup


class WithTagTests(SimpleTestCase):
    at_least_with_one_msg = "'with' expected at least one variable assignment"

    @setup({"with01": "{% with key=dict.key %}{{ key }}{% endwith %}"})
    def test_with01(self):
        output = self.engine.render_to_string("with01", {"dict": {"key": 50}})
        self.assertEqual(output, "50")

    @setup({"legacywith01": "{% with dict.key as key %}{{ key }}{% endwith %}"})
    def test_legacywith01(self):
        """
        Tests the rendering of a Django template that uses a legacy with statement to extract a key from a dictionary and display its value, verifying that the output matches the expected result.
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
        #: Tests the behavior of the \"with\" template tag in legacy mode.
        #: 
        #: Verifies that the \"with\" statement correctly assigns the specified value 
        #: to the given variable and that this variable is accessible both inside 
        #: and outside the \"with\" block. The test also handles cases where the 
        #: engine is configured to render invalid template variables as a 
        #: specified string or to output the original variable name. 
        #: 
        #: :param None
        #: :return: None 
        #: :raises: AssertionError if the rendered output does not match the expected result.
        """
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
        with self.assertRaisesMessage(TemplateSyntaxError, self.at_least_with_one_msg):
            self.engine.render_to_string("with-error01", {"dict": {"key": 50}})

    @setup({"with-error02": "{% with dict.key as %}{{ key }}{% endwith %}"})
    def test_with_error02(self):
        """
        Test the rendering of a template with a syntax error in a \"with\" statement, specifically when the \"with\" statement is missing a required \"as\" variable assignment. 

        The test expects a TemplateSyntaxError to be raised, indicating that the template syntax is invalid. The test verifies that the error message contains the expected text, ensuring that the error is correctly identified and reported.
        """
        with self.assertRaisesMessage(TemplateSyntaxError, self.at_least_with_one_msg):
            self.engine.render_to_string("with-error02", {"dict": {"key": 50}})


class WithNodeTests(SimpleTestCase):
    def test_repr(self):
        node = WithNode(nodelist=[], name="a", var="dict.key")
        self.assertEqual(repr(node), "<WithNode>")
