from django.template import TemplateSyntaxError
from django.test import SimpleTestCase

from ...utils import setup


class GetAvailableLanguagesTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup(
        {
            "i18n12": "{% load i18n %}"
            "{% get_available_languages as langs %}{% for lang in langs %}"
            '{% if lang.0 == "de" %}{{ lang.0 }}{% endif %}{% endfor %}'
        }
    )
    def test_i18n12(self):
        """
        Tests the i18n template tag for rendering available languages.

        This test case verifies that the get_available_languages tag correctly retrieves
        and renders the list of available languages in the system, specifically checking
        for the presence of the German language (\"de\").

        The test renders a template that loads the i18n tag, retrieves the available
        languages, and loops through them to find the German language code. It then
        asserts that the rendered output matches the expected value, confirming that the
        i18n tag is functioning as expected.

        The purpose of this test is to ensure that the i18n functionality is properly
        integrated and working as intended, allowing the application to support
        multiple languages and provide a seamless experience for users of different
        language backgrounds.
        """
        output = self.engine.render_to_string("i18n12")
        self.assertEqual(output, "de")

    @setup({"syntax_i18n": "{% load i18n %}{% get_available_languages a langs %}"})
    def test_no_as_var(self):
        """
        Tests that the 'get_available_languages' template tag raises a TemplateSyntaxError when not used with the 'as variable' syntax. 

        This test ensures that the template engine correctly processes the 'get_available_languages' tag and fails when it is used without assigning the result to a variable.
        """
        msg = (
            "'get_available_languages' requires 'as variable' (got "
            "['get_available_languages', 'a', 'langs'])"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("syntax_i18n")
