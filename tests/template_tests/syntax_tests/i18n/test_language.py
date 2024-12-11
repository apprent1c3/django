from template_tests.utils import setup

from django.template import TemplateSyntaxError
from django.test import SimpleTestCase


class I18nLanguageTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"i18n_language": "{% load i18n %} {% language %} {% endlanguage %}"})
    def test_no_arg(self):
        """
        Tests the language template tag behavior when no arguments are provided.

        Verifies that rendering a template with the language tag and no language argument
        raises a TemplateSyntaxError with a message indicating that the 'language' tag
        requires one argument.

        Ensures that the i18n language functionality is correctly validated and reported
        when misused, promoting proper usage and preventing unexpected behavior in
        templates.
        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "'language' takes one argument (language)"
        ):
            self.engine.render_to_string("i18n_language")
