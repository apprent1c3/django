from template_tests.utils import setup

from django.template import TemplateSyntaxError
from django.test import SimpleTestCase


class I18nGetCurrentLanguageTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"template": "{% load i18n %} {% get_current_language %}"})
    def test_no_as_var(self):
        """
        Tests that the 'get_current_language' template tag in Django raises a TemplateSyntaxError when used without the 'as variable' syntax. 

        This function verifies that the correct error message is thrown when the template tag is used incorrectly, ensuring proper handling of language setting in templating.
        """
        msg = (
            "'get_current_language' requires 'as variable' (got "
            "['get_current_language'])"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")
