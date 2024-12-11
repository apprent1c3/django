from django.template import TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils import translation

from ...utils import setup


class GetLanguageInfoListTests(SimpleTestCase):
    libraries = {
        "custom": "template_tests.templatetags.custom",
        "i18n": "django.templatetags.i18n",
    }

    @setup(
        {
            "i18n30": "{% load i18n %}"
            "{% get_language_info_list for langcodes as langs %}"
            "{% for l in langs %}{{ l.code }}: {{ l.name }}/"
            "{{ l.name_local }} bidi={{ l.bidi }}; {% endfor %}"
        }
    )
    def test_i18n30(self):
        """
        Tests the i18n template tag to retrieve language information.

        This test case verifies that the template renders the language codes, names, and
        bidirectional properties correctly for a given list of language codes. The test
        input includes language codes for Italian and Norwegian, and it checks that the
        output string contains the expected language information in the correct format.

        The test validates the output against a predefined string, ensuring that the
        language codes, names, and bidirectional properties are rendered as expected.
        This test helps ensure that the i18n template tag is working correctly and
        provides the desired language information in the expected format.
        """
        output = self.engine.render_to_string("i18n30", {"langcodes": ["it", "no"]})
        self.assertEqual(
            output, "it: Italian/italiano bidi=False; no: Norwegian/norsk bidi=False; "
        )

    @setup(
        {
            "i18n31": "{% load i18n %}"
            "{% get_language_info_list for langcodes as langs %}"
            "{% for l in langs %}{{ l.code }}: {{ l.name }}/"
            "{{ l.name_local }} bidi={{ l.bidi }}; {% endfor %}"
        }
    )
    def test_i18n31(self):
        """

        Tests the rendering of language codes with their respective names and bidi information.

        This function checks if the i18n template tag correctly loads and displays language information, 
        including the language code, name, and localized name, as well as its bidirectional text support.

        It uses a predefined set of language codes and their corresponding names, and verifies that the 
        rendered output matches the expected format.

        """
        output = self.engine.render_to_string(
            "i18n31", {"langcodes": (("sl", "Slovenian"), ("fa", "Persian"))}
        )
        self.assertEqual(
            output,
            "sl: Slovenian/Sloven\u0161\u010dina bidi=False; "
            "fa: Persian/\u0641\u0627\u0631\u0633\u06cc bidi=True; ",
        )

    @setup(
        {
            "i18n38_2": "{% load i18n custom %}"
            '{% get_language_info_list for langcodes|noop:"x y" as langs %}'
            "{% for l in langs %}{{ l.code }}: {{ l.name }}/"
            "{{ l.name_local }}/{{ l.name_translated }} "
            "bidi={{ l.bidi }}; {% endfor %}"
        }
    )
    def test_i18n38_2(self):
        """

        Tests the i18n template tag's ability to iterate over a list of language codes and display language information.

        Checks that the language codes are correctly rendered, including their code, name, local name, and translated name, 
        as well as their bidirectional text direction. The test is performed with the translation set to Czech ('cs').

        The output is verified to match the expected string format, which contains the language code, names, and bidi value.

        """
        with translation.override("cs"):
            output = self.engine.render_to_string(
                "i18n38_2", {"langcodes": ["it", "fr"]}
            )
        self.assertEqual(
            output,
            "it: Italian/italiano/italsky bidi=False; "
            "fr: French/français/francouzsky bidi=False; ",
        )

    @setup({"i18n_syntax": "{% load i18n %} {% get_language_info_list error %}"})
    def test_no_for_as(self):
        """
        Tests that the get_language_info_list template tag raises an error when not used within a for loop.

        The function checks that using the get_language_info_list template tag without a 'for sequence as variable' syntax results in a TemplateSyntaxError.

        """
        msg = (
            "'get_language_info_list' requires 'for sequence as variable' (got "
            "['error'])"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("i18n_syntax")
