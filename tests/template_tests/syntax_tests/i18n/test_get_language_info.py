from django.template import TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils import translation

from ...utils import setup


class I18nGetLanguageInfoTagTests(SimpleTestCase):
    libraries = {
        "custom": "template_tests.templatetags.custom",
        "i18n": "django.templatetags.i18n",
    }

    # retrieving language information
    @setup(
        {
            "i18n28_2": "{% load i18n %}"
            '{% get_language_info for "de" as l %}'
            "{{ l.code }}: {{ l.name }}/{{ l.name_local }} bidi={{ l.bidi }}"
        }
    )
    def test_i18n28_2(self):
        """

        Tests the i18n template tag to retrieve language information for a specific language code.

        Verifies that the rendered template output matches the expected language details, including the language code, name, local name, and bidirectional indicator.

        Args:
            None

        Returns:
            None

        Asserts that the output of the rendered template is 'de: German/Deutsch bidi=False', confirming the correct functionality of the i18n template tag.

        """
        output = self.engine.render_to_string("i18n28_2")
        self.assertEqual(output, "de: German/Deutsch bidi=False")

    @setup(
        {
            "i18n29": "{% load i18n %}"
            "{% get_language_info for LANGUAGE_CODE as l %}"
            "{{ l.code }}: {{ l.name }}/{{ l.name_local }} bidi={{ l.bidi }}"
        }
    )
    def test_i18n29(self):
        """
        Tests the rendering of language information with i18n template tags.

        The function checks that the language code, name, and name in the native language are correctly displayed,
        along with the bidi (bidirectional) setting, for a given language. It verifies that the output matches the expected format.
        """
        output = self.engine.render_to_string("i18n29", {"LANGUAGE_CODE": "fi"})
        self.assertEqual(output, "fi: Finnish/suomi bidi=False")

    # Test whitespace in filter arguments
    @setup(
        {
            "i18n38": "{% load i18n custom %}"
            '{% get_language_info for "de"|noop:"x y" as l %}'
            "{{ l.code }}: {{ l.name }}/{{ l.name_local }}/"
            "{{ l.name_translated }} bidi={{ l.bidi }}"
        }
    )
    def test_i18n38(self):
        """

        Tests language information retrieval with the get_language_info template tag.

        This test verifies that the get_language_info tag correctly retrieves and 
        displays language code, name, local name, and translated name for a given 
        language, as well as its bidirectional text direction.

        The test is run with the language overridden to Czech ('cs') to ensure 
        that the output is correctly translated. The expected output is compared 
        to the rendered template string to ensure that the language information 
        is correctly formatted.

        """
        with translation.override("cs"):
            output = self.engine.render_to_string("i18n38")
        self.assertEqual(output, "de: German/Deutsch/německy bidi=False")

    @setup({"template": "{% load i18n %}{% get_language_info %}"})
    def test_no_for_as(self):
        """
        Test that the 'get_language_info' template tag requires the 'for string as variable' syntax.

            This test case checks if the 'get_language_info' template tag correctly enforces the use of the 'for string as variable' syntax.
            It verifies that a TemplateSyntaxError is raised when the syntax is not provided, providing a specific error message.
        """
        msg = "'get_language_info' requires 'for string as variable' (got [])"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")
