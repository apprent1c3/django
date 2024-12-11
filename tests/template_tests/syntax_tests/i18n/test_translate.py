import inspect
from functools import partial, wraps

from asgiref.local import Local

from django.template import Context, Template, TemplateSyntaxError
from django.templatetags.l10n import LocalizeNode
from django.test import SimpleTestCase, override_settings
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import trans_real

from ...utils import setup as base_setup
from .base import MultipleLocaleActivationTestCase, extended_locale_paths


def setup(templates, *args, **kwargs):
    """

    Setup a decorator to configure template translation for a given function.

    This decorator provides two setup configurations: one for 'trans' tags and one for 'translate' tags.
    It automatically wraps the decorated function and applies the setup configurations based on the function's signature.

    The setup configurations are created from the provided templates, which are dictionaries mapping template names to template strings.
    The templates are modified to replace '{% translate ' with '{% trans ' to create the 'trans' setup configuration.

    The decorator can be used to enable template translation for functions that support 'trans' or 'translate' tags.
    It takes care of configuring the translation setup for the decorated function, making it easy to switch between 'trans' and 'translate' tags.

    :param templates: a dictionary of template names to template strings
    :param args: additional positional arguments
    :param kwargs: additional keyword arguments
    :returns: a decorator that configures template translation for a given function

    """
    translate_setup = base_setup(templates, *args, **kwargs)
    trans_setup = base_setup(
        {
            name: template.replace("{% translate ", "{% trans ")
            for name, template in templates.items()
        }
    )

    tags = {
        "trans": trans_setup,
        "translate": translate_setup,
    }

    def decorator(func):
        @wraps(func)
        def inner(self, *args):
            signature = inspect.signature(func)
            for tag_name, setup_func in tags.items():
                if "tag_name" in signature.parameters:
                    setup_func(partial(func, tag_name=tag_name))(self)
                else:
                    setup_func(func)(self)

        return inner

    return decorator


class I18nTransTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup({"i18n01": "{% load i18n %}{% translate 'xxxyyyxxx' %}"})
    def test_i18n01(self):
        """simple translation of a string delimited by '."""
        output = self.engine.render_to_string("i18n01")
        self.assertEqual(output, "xxxyyyxxx")

    @setup({"i18n02": '{% load i18n %}{% translate "xxxyyyxxx" %}'})
    def test_i18n02(self):
        """simple translation of a string delimited by "."""
        output = self.engine.render_to_string("i18n02")
        self.assertEqual(output, "xxxyyyxxx")

    @setup({"i18n06": '{% load i18n %}{% translate "Page not found" %}'})
    def test_i18n06(self):
        """simple translation of a string to German"""
        with translation.override("de"):
            output = self.engine.render_to_string("i18n06")
        self.assertEqual(output, "Seite nicht gefunden")

    @setup({"i18n09": '{% load i18n %}{% translate "Page not found" noop %}'})
    def test_i18n09(self):
        """simple non-translation (only marking) of a string to German"""
        with translation.override("de"):
            output = self.engine.render_to_string("i18n09")
        self.assertEqual(output, "Page not found")

    @setup({"i18n20": "{% load i18n %}{% translate andrew %}"})
    def test_i18n20(self):
        output = self.engine.render_to_string("i18n20", {"andrew": "a & b"})
        self.assertEqual(output, "a &amp; b")

    @setup({"i18n22": "{% load i18n %}{% translate andrew %}"})
    def test_i18n22(self):
        """
        Tests the functionality of internationalization (i18n) with the Django templating engine, specifically that HTML entities rendered through the `{% translate %}` template tag are correctly escaped. Verifies that the output of the rendered template matches the expected string, ensuring that the translation mechanism preserves the original content without additional escaping.
        """
        output = self.engine.render_to_string("i18n22", {"andrew": mark_safe("a & b")})
        self.assertEqual(output, "a & b")

    @setup(
        {
            "i18n23": (
                '{% load i18n %}{% translate "Page not found"|capfirst|slice:"6:" %}'
            )
        }
    )
    def test_i18n23(self):
        """Using filters with the {% translate %} tag (#5972)."""
        with translation.override("de"):
            output = self.engine.render_to_string("i18n23")
        self.assertEqual(output, "nicht gefunden")

    @setup({"i18n24": "{% load i18n %}{% translate 'Page not found'|upper %}"})
    def test_i18n24(self):
        """

        Test that the i18n translation is correctly applied when rendering a template.

        This test case sets up a template with an i18n translation block and renders it
        to a string while overriding the translation locale to German. It then asserts
        that the rendered output matches the expected translated string.

        The test verifies that the translation is correctly applied, and the template
        is rendered with the translated text in the expected language.

        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n24")
        self.assertEqual(output, "SEITE NICHT GEFUNDEN")

    @setup({"i18n25": "{% load i18n %}{% translate somevar|upper %}"})
    def test_i18n25(self):
        with translation.override("de"):
            output = self.engine.render_to_string(
                "i18n25", {"somevar": "Page not found"}
            )
        self.assertEqual(output, "SEITE NICHT GEFUNDEN")

    # trans tag with as var
    @setup(
        {
            "i18n35": (
                '{% load i18n %}{% translate "Page not found" as page_not_found %}'
                "{{ page_not_found }}"
            )
        }
    )
    def test_i18n35(self):
        """
        Tests the i18n functionality using the Django template engine.

        Verifies that the translation override works correctly by rendering a template
        with a translation block and checking the output matches the expected translation
        for the specified language (German).

        Checks if the \"Page not found\" string is properly translated when the language
        is set to German using the 'de' locale, ensuring the output is 'Seite nicht gefunden'.
        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n35")
        self.assertEqual(output, "Seite nicht gefunden")

    @setup(
        {
            "i18n36": (
                '{% load i18n %}{% translate "Page not found" noop as page_not_found %}'
                "{{ page_not_found }}"
            )
        }
    )
    def test_i18n36(self):
        with translation.override("de"):
            output = self.engine.render_to_string("i18n36")
        self.assertEqual(output, "Page not found")

    @setup({"template": "{% load i18n %}{% translate %}A}"})
    def test_syntax_error_no_arguments(self, tag_name):
        msg = "'{}' takes at least one argument".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" badoption %}'})
    def test_syntax_error_bad_option(self, tag_name):
        """
        Tests that a TemplateSyntaxError is raised when an unknown option is provided to a template tag.

        The function verifies that the template engine correctly handles invalid options by checking that the expected error message is raised.
        It checks for the presence of a specific error message, indicating that the unknown option 'badoption' is not recognized by the '{% load i18n %}{% translate \"Yes\" badoption %}' tag.

        :param tag_name: The name of the template tag being tested.

        """
        msg = "Unknown argument for '{}' tag: 'badoption'".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" as %}'})
    def test_syntax_error_missing_assignment(self, tag_name):
        """

        Tests that a TemplateSyntaxError is raised when the 'as' option is used without an assignment in a template tag.

        This test case verifies that the templating engine correctly handles missing assignments for the 'as' option in a specific template tag.
        The test checks for the expected error message when rendering a template with a syntax error, ensuring that the engine behaves as expected in such cases.

        :param tag_name: The name of the template tag being tested.

        """
        msg = "No argument provided to the '{}' tag for the as option.".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" as var context %}'})
    def test_syntax_error_missing_context(self, tag_name):
        msg = "No argument provided to the '{}' tag for the context option.".format(
            tag_name
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" context as var %}'})
    def test_syntax_error_context_as(self, tag_name):
        msg = (
            f"Invalid argument 'as' provided to the '{tag_name}' tag for the context "
            f"option"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" context noop %}'})
    def test_syntax_error_context_noop(self, tag_name):
        """

        Tests the rendering of a template with an invalid 'noop' context option provided to a template tag.

        The function checks if a TemplateSyntaxError is raised when an invalid argument 'noop' is passed to the context option of the specified template tag.

        :param tag_name: The name of the template tag being tested.
        :raises TemplateSyntaxError: If the 'noop' argument is provided to the context option of the template tag.

        """
        msg = (
            f"Invalid argument 'noop' provided to the '{tag_name}' tag for the context "
            f"option"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" noop noop %}'})
    def test_syntax_error_duplicate_option(self):
        """
        Tests that rendering a template with a duplicate 'noop' option raises a TemplateSyntaxError.

        The test verifies that the template engine correctly identifies and reports the error when the 'noop' option is specified multiple times.

        :raises TemplateSyntaxError: If the 'noop' option is specified more than once in the template.
        """
        msg = "The 'noop' option was specified more than once."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "%s" %}'})
    def test_trans_tag_using_a_string_that_looks_like_str_fmt(self):
        """

        Test rendering a template using the trans tag with a string 
        that resembles a string format specifier.

        This test case verifies that the templating engine correctly 
        handles a string that looks like a format specifier, 
        ensuring it is translated correctly rather than being 
        interpreted as a format string.

        The expected output is the original string, demonstrating 
        that the templating engine correctly escapes the string 
        and prevents any formatting errors.

        """
        output = self.engine.render_to_string("template")
        self.assertEqual(output, "%s")


class TranslationTransTagTests(SimpleTestCase):
    tag_name = "trans"

    def get_template(self, template_string):
        return Template(
            template_string.replace("{{% translate ", "{{% {}".format(self.tag_name))
        )

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_template_tags_pgettext(self):
        """{% translate %} takes message contexts into account (#14806)."""
        trans_real._active = Local()
        trans_real._translations = {}
        with translation.override("de"):
            # Nonexistent context...
            t = self.get_template(
                '{% load i18n %}{% translate "May" context "nonexistent" %}'
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "May")

            # Existing context... using a literal
            t = self.get_template(
                '{% load i18n %}{% translate "May" context "month name" %}'
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Mai")
            t = self.get_template('{% load i18n %}{% translate "May" context "verb" %}')
            rendered = t.render(Context())
            self.assertEqual(rendered, "Kann")

            # Using a variable
            t = self.get_template(
                '{% load i18n %}{% translate "May" context message_context %}'
            )
            rendered = t.render(Context({"message_context": "month name"}))
            self.assertEqual(rendered, "Mai")
            t = self.get_template(
                '{% load i18n %}{% translate "May" context message_context %}'
            )
            rendered = t.render(Context({"message_context": "verb"}))
            self.assertEqual(rendered, "Kann")

            # Using a filter
            t = self.get_template(
                '{% load i18n %}{% translate "May" context message_context|lower %}'
            )
            rendered = t.render(Context({"message_context": "MONTH NAME"}))
            self.assertEqual(rendered, "Mai")
            t = self.get_template(
                '{% load i18n %}{% translate "May" context message_context|lower %}'
            )
            rendered = t.render(Context({"message_context": "VERB"}))
            self.assertEqual(rendered, "Kann")

            # Using 'as'
            t = self.get_template(
                '{% load i18n %}{% translate "May" context "month name" as var %}'
                "Value: {{ var }}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Value: Mai")
            t = self.get_template(
                '{% load i18n %}{% translate "May" as var context "verb" %}Value: '
                "{{ var }}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Value: Kann")


class TranslationTranslateTagTests(TranslationTransTagTests):
    tag_name = "translate"


class MultipleLocaleActivationTransTagTests(MultipleLocaleActivationTestCase):
    tag_name = "trans"

    def get_template(self, template_string):
        return Template(
            template_string.replace("{{% translate ", "{{% {}".format(self.tag_name))
        )

    def test_single_locale_activation(self):
        """
        Simple baseline behavior with one locale for all the supported i18n
        constructs.
        """
        with translation.override("fr"):
            self.assertEqual(
                self.get_template("{% load i18n %}{% translate 'Yes' %}").render(
                    Context({})
                ),
                "Oui",
            )

    def test_multiple_locale_trans(self):
        """

        Tests translation functionality for multiple locales.

        This test case verifies that the translation system correctly switches between different languages.
        It checks that a template with a translate tag renders the correct translation for the 'No' string when the locale is set to Dutch ('nl').
        The test is run with German ('de') as the initial locale to ensure that the translation system can handle changes in locale.

        """
        with translation.override("de"):
            t = self.get_template("{% load i18n %}{% translate 'No' %}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_deactivate_trans(self):
        """
        Tests deactivation of translation for a specific locale by rendering a template with translated content. 

        The test first sets the locale to German ('de') and deactivates translation. It then loads a template containing a translatable string and renders it in the Dutch ('nl') locale to verify that translation is still active for other locales. 

        The expected result is that the translated string is rendered in Dutch ('Nee'), confirming that translation deactivation only applies to the specified locale.
        """
        with translation.override("de", deactivate=True):
            t = self.get_template("{% load i18n %}{% translate 'No' %}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_direct_switch_trans(self):
        with translation.override("de"):
            t = self.get_template("{% load i18n %}{% translate 'No' %}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")


class MultipleLocaleActivationTranslateTagTests(MultipleLocaleActivationTransTagTests):
    tag_name = "translate"


class LocalizeNodeTests(SimpleTestCase):
    def test_repr(self):
        node = LocalizeNode(nodelist=[], use_l10n=True)
        self.assertEqual(repr(node), "<LocalizeNode>")
