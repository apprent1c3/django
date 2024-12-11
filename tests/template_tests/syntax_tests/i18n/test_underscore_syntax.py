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
        """

        Test the functionality of translating a template with multiple locale filters.

        This test checks if the yesno template filter works correctly with translations
        when the locale is changed. It specifically verifies that the filter outputs the
        correct translation for a given boolean value when using the i18n library.

        """
        with translation.override("de"):
            t = Template("{% load i18n %}{{ 0|yesno:_('yes,no,maybe') }}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "nee")

    def test_multiple_locale_filter_deactivate(self):
        """
        Tests the deactivation of the locale filter in a template when the locale is set to German ('de') and then overridden to Dutch ('nl'), verifying that the yesno filter correctly renders the 'no' translation for the Dutch locale.
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
        with translation.override("de"):
            t = Template("{{ _('No') }}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_deactivate(self):
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
        Tests the loading of locale translations using the i18n template tag.

        Verifies that the translation system correctly switches between languages and 
        renders the expected localized string. In this case, it checks that the string 
        'No' is translated to 'Nee' when the locale is set to Dutch ('nl') after 
        initially being set to German ('de').
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
        Test that translation override works correctly for a specific template string.

        This test case verifies that the engine renders the correct translated string 
        when the locale is set to German ('de'). It checks that the output of the 
        rendered template matches the expected translated string 'Passwort' for the 
        original string 'Password'.
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
        with translation.override("de"):
            output = self.engine.render_to_string("i18n14")
        self.assertEqual(output, "foo Passwort Passwort")

    @setup({"i18n15": '{{ absent|default:_("Password") }}'})
    def test_i18n15(self):
        with translation.override("de"):
            output = self.engine.render_to_string("i18n15", {"absent": ""})
        self.assertEqual(output, "Passwort")

    @setup({"i18n16": '{{ _("<") }}'})
    def test_i18n16(self):
        with translation.override("de"):
            output = self.engine.render_to_string("i18n16")
        self.assertEqual(output, "<")
