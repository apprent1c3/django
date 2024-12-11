from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

from ...utils import setup
from .base import MultipleLocaleActivationTestCase


class MultipleLocaleActivationTests(MultipleLocaleActivationTestCase):
    def test_single_locale_activation(self):
        """
        Simple baseline behavior with one locale for all the supported i18n
        constructs.
        """
        with translation.override("fr"):
            self.assertEqual(Template("{{ _('Yes') }}").render(Context({})), "Oui")

    # Literal marked up with _() in a filter expression

    def test_multiple_locale_filter(self):
        with translation.override("de"):
            t = Template("{% load i18n %}{{ 0|yesno:_('yes,no,maybe') }}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "nee")

    def test_multiple_locale_filter_deactivate(self):
        """
        Tests the behavior of the yesno filter with multiple locales when the locale is deactivated.

        The test case verifies that the yesno filter correctly handles translations when the locale is overridden and deactivated.
        It checks that the filter uses the correct translation catalog and falls back to the default translation when the locale is deactivated.

        Parameters: None
        Returns: None
        Raises: AssertionError if the test fails
        """
        with translation.override("de", deactivate=True):
            t = Template("{% load i18n %}{{ 0|yesno:_('yes,no,maybe') }}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "nee")

    def test_multiple_locale_filter_direct_switch(self):
        with translation.override("de"):
            t = Template("{% load i18n %}{{ 0|yesno:_('yes,no,maybe') }}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "nee")

    # Literal marked up with _()

    def test_multiple_locale(self):
        """
        Tests rendering of a template with a translation string under multiple locales.

        The function verifies that a template containing a translation string can be correctly
        rendered when the locale is switched between different languages. It checks that the
        translation string is properly substituted with the correct translated text for each
        locale.

        :raises AssertionError: if the rendered template does not match the expected translated text
        """
        with translation.override("de"):
            t = Template("{{ _('No') }}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_deactivate(self):
        """
        Tests deactivating and reactivating locale translation for template rendering.

        Checks that a template with a translatable string is rendered correctly after
        the locale translation has been deactivated and then reactivated with a
        different locale. The string 'No' is expected to be translated to 'Nee' when
        rendered with the 'nl' locale.

        This test ensures that the translation override mechanism works correctly and
        that template rendering is not affected by temporary locale deactivation.
        """
        with translation.override("de", deactivate=True):
            t = Template("{{ _('No') }}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_direct_switch(self):
        with translation.override("de"):
            t = Template("{{ _('No') }}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    # Literal marked up with _(), loading the i18n template tag library

    def test_multiple_locale_loadi18n(self):
        """

        Tests the loading of multiple locale translations with the i18n template tag.

        Verifies that the correct translation is loaded when the locale is switched
        multiple times. Specifically, tests that the translation for 'No' in the Dutch
        locale ('Nee') is rendered correctly after the locale is set to German and then
        switched back to the original locale and then to Dutch.

        """
        with translation.override("de"):
            t = Template("{% load i18n %}{{ _('No') }}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_loadi18n_deactivate(self):
        with translation.override("de", deactivate=True):
            t = Template("{% load i18n %}{{ _('No') }}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_loadi18n_direct_switch(self):
        """

        Tests the correct loading of multiple locales with the i18n template tag.

        This test verifies that the i18n template tag can switch between different locales and 
        correctly translates text. It checks that the translation is rendered correctly 
        when the locale is changed directly.

        The test case specifically checks the translation of the text 'No' in German ('de') 
        and Dutch ('nl') locales, ensuring that the correct translation 'Nee' is used when 
        rendering the template in the Dutch locale.

        """
        with translation.override("de"):
            t = Template("{% load i18n %}{{ _('No') }}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")


class I18nStringLiteralTests(SimpleTestCase):
    """translation of constant strings"""

    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"i18n13": '{{ _("Password") }}'})
    def test_i18n13(self):
        """

        Tests the internationalization (i18n) functionality by rendering a template 
        with a translated string. 

        Specifically, it checks that the string 'Password' is correctly translated 
        to 'Passwort' when the language is set to German ('de'). 

        The test verifies that the translation override is applied correctly and 
        that the rendered output matches the expected translated string.

        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n13")
        self.assertEqual(output, "Passwort")

    @setup(
        {
            "i18n14": (
                '{% cycle "foo" _("Password") _(\'Password\') as c %} {% cycle c %} '
                "{% cycle c %}"
            )
        }
    )
    def test_i18n14(self):
        """

        Tests the i18n14 functionality of the templating engine, specifically the interaction 
        between the cycle tag and internationalization (i18n) for password translation.

        Verifies that when rendering the template with the translation set to German ('de'), 
        the output matches the expected string, demonstrating correct i18n translation 
        and cycling of the password placeholder.

        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n14")
        self.assertEqual(output, "foo Passwort Passwort")

    @setup({"i18n15": '{{ absent|default:_("Password") }}'})
    def test_i18n15(self):
        """
        .. function:: test_i18n15(self)

           Tests the internationalization (i18n) functionality of the templating engine, 
           specifically the rendering of a German translation for a missing variable.

           This test verifies that when the variable 'absent' is empty, the default 
           German translation 'Passwort' is rendered instead of the English translation 
           'Password'. The test is performed by overriding the language to German, 
           rendering the 'i18n15' template and then asserting the output matches 
           the expected German translation.
        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n15", {"absent": ""})
        self.assertEqual(output, "Passwort")

    @setup({"i18n16": '{{ _("<") }}'})
    def test_i18n16(self):
        """
        Tests internationalization feature for left angle bracket character.

        Verifies that the engine correctly renders the left angle bracket character
        when the locale is set to German ('de'). The test checks that the rendered
        output matches the expected output.

        :raises AssertionError: If the rendered output does not match the expected output.
        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n16")
        self.assertEqual(output, "<")
