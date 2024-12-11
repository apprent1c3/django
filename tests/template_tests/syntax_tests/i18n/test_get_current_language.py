from template_tests.utils import setup

from django.template import TemplateSyntaxError
from django.test import SimpleTestCase


class I18nGetCurrentLanguageTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"template": "{% load i18n %} {% get_current_language %}"})
    def test_no_as_var(self):
        """
        Checks that the 'get_current_language' template tag raises an exception when not used with the 'as variable' syntax.

        This test case verifies that the template engine correctly handles the 'get_current_language' tag and enforces its usage with the 'as variable' syntax, as required. It validates that a TemplateSyntaxError is raised with the expected error message when the tag is used incorrectly.
        """
        msg = (
            "'get_current_language' requires 'as variable' (got "
            "['get_current_language'])"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")
