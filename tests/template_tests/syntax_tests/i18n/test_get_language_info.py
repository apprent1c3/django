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

        Tests the i18n template tag for rendering language information.

        This test case loads the i18n template tag and uses the get_language_info
        tag to retrieve information about the German language. It then checks that
        the rendered output matches the expected language code, name, and bidi
        (direction) information.

        The expected output includes the language code, name, local name, and bidi
        information, which should be correctly formatted as 'de: German/Deutsch
        bidi=False' for the German language.

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

        Tests the i18n29 template tag by rendering a string with language information.

        The test case verifies that the language code, name, and bidirectional text support
        are correctly displayed for a given language. In this instance, the function tests
        the 'fi' language code, which corresponds to Finnish.

        The expected output includes the language code, name, local name, and bidi (bidirectional)
        text support, which is set to False for the Finnish language.

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
        Tests the rendering of language information with Django's i18n template tags.

        Verifies that the language code, name, local name, and translated name are correctly
        displayed, along with the bidirectional text support flag. The test case overrides
        the language to Czech and checks the rendered output for the German language
        information.

        The expected output includes the language code, name, local name, translated name,
        and bidirectional text support flag, ensuring that the i18n template tags function
        as expected in the given context.
        """
        with translation.override("cs"):
            output = self.engine.render_to_string("i18n38")
        self.assertEqual(output, "de: German/Deutsch/německy bidi=False")

    @setup({"template": "{% load i18n %}{% get_language_info %}"})
    def test_no_for_as(self):
        """

        Tests that the 'get_language_info' template tag raises a TemplateSyntaxError when not used with the 'for string as variable' syntax.

        Ensures the correct usage of the 'get_language_info' tag is enforced, preventing template rendering errors.

        """
        msg = "'get_language_info' requires 'for string as variable' (got [])"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")
