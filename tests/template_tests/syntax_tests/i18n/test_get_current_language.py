from template_tests.utils import setup

from django.template import TemplateSyntaxError
from django.test import SimpleTestCase


class I18nGetCurrentLanguageTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"template": "{% load i18n %} {% get_current_language %}"})
    def test_no_as_var(self):
        """

        Tests that using the 'get_current_language' tag in a template without the 'as variable' syntax raises a TemplateSyntaxError.

        The function verifies that the template engine correctly identifies and reports the error when the 'get_current_language' tag is used without proper assignment to a variable.

        """
        msg = (
            "'get_current_language' requires 'as variable' (got "
            "['get_current_language'])"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")
