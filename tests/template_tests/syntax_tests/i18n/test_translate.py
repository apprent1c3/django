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
        """

        Verifies that the i18n translation system correctly escapes special characters in the output.

        This test case checks that the 'andrew' variable, which contains a string with special characters ('a & b'), is properly escaped to its HTML entity equivalent ('a &amp; b') when rendered as a translated string using the i18n template tag.

        """
        output = self.engine.render_to_string("i18n20", {"andrew": "a & b"})
        self.assertEqual(output, "a &amp; b")

    @setup({"i18n22": "{% load i18n %}{% translate andrew %}"})
    def test_i18n22(self):
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
        with translation.override("de"):
            output = self.engine.render_to_string("i18n24")
        self.assertEqual(output, "SEITE NICHT GEFUNDEN")

    @setup({"i18n25": "{% load i18n %}{% translate somevar|upper %}"})
    def test_i18n25(self):
        """

        Tests the i18n template tag with the |upper filter.

        This test case verifies that the i18n translation system correctly handles the |upper filter
        when rendering a template string. It sets the input variable 'somevar' to 'Page not found',
        switches to the German locale, and then renders the template. The output is then compared
        to the expected translated and uppercased string 'SEITE NICHT GEFUNDEN'.

        The test ensures that the translation system correctly applies the |upper filter to the
        translated string, resulting in the desired output.

        """
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

        Tests the i18n template tag by rendering a template with a translation override.

        The test verifies that the translation is correctly applied when the locale is set to German ('de').
        It checks if the rendered output matches the expected translated string for the phrase \"Page not found\".

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
        """
        Tests the i18n translation functionality in the template engine.

        This test case verifies that the translation of a string works correctly. 
        It overrides the language to German and then renders a template that contains a 
        translated string. The test checks if the output of the rendered template is 
        the original string in English, indicating that the translation did not occur 
        as expected, since the translation to German should not be applied in this case.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the output of the rendered template does not match the 
                            expected string 'Page not found'
        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n36")
        self.assertEqual(output, "Page not found")

    @setup({"template": "{% load i18n %}{% translate %}A}"})
    def test_syntax_error_no_arguments(self, tag_name):
        """

        Tests that a TemplateSyntaxError is raised when a template tag is used without any arguments.

        The test checks that the error message includes the name of the tag and an indication that at least one argument is required.

        :param tag_name: The name of the template tag being tested.
        :raises TemplateSyntaxError: If the tag is used without any arguments.

        """
        msg = "'{}' takes at least one argument".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" badoption %}'})
    def test_syntax_error_bad_option(self, tag_name):
        """
        Test that a TemplateSyntaxError is raised when an invalid option is used with an i18n template tag.

        The test checks that an error is thrown when the template engine encounters an unknown argument with the given tag name. This validation ensures that template tags are used correctly with their specified options to prevent runtime errors.
        """
        msg = "Unknown argument for '{}' tag: 'badoption'".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" as %}'})
    def test_syntax_error_missing_assignment(self, tag_name):
        """
        Tests the behavior of a Django template tag when an assignment is missing for the 'as' option.

        This test checks that a TemplateSyntaxError is raised with the expected error message when the template tag is used without providing an argument for the 'as' option.

        :param tag_name: The name of the template tag being tested.

        """
        msg = "No argument provided to the '{}' tag for the as option.".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" as var context %}'})
    def test_syntax_error_missing_context(self, tag_name):
        """
        Tests that a TemplateSyntaxError is raised when the context option is missing 
        for a given template tag.

        :arg tag_name: The name of the template tag to test.
        :raises TemplateSyntaxError: If no argument is provided to the template tag 
            for the context option.

        """
        msg = "No argument provided to the '{}' tag for the context option.".format(
            tag_name
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" context as var %}'})
    def test_syntax_error_context_as(self, tag_name):
        """

        Tests that providing the 'as' argument to a template tag for the context option results in a TemplateSyntaxError.

        This test ensures that the template engine raises an error when the 'as' keyword is used incorrectly, providing a specific error message that indicates the problem.

        :param tag_name: The name of the template tag being tested.

        """
        msg = (
            f"Invalid argument 'as' provided to the '{tag_name}' tag for the context "
            f"option"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" context noop %}'})
    def test_syntax_error_context_noop(self, tag_name):
        """
        Test that providing an invalid 'noop' argument to a template tag raises a TemplateSyntaxError.

        This test case ensures that when the 'noop' argument is passed to a template tag for the context option,
        the expected error message is raised, indicating that the argument is not valid for the given tag.
        The error message includes the name of the tag that caused the error, providing helpful information
        for debugging and troubleshooting template syntax issues.
        """
        msg = (
            f"Invalid argument 'noop' provided to the '{tag_name}' tag for the context "
            f"option"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "Yes" noop noop %}'})
    def test_syntax_error_duplicate_option(self):
        msg = "The 'noop' option was specified more than once."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": '{% load i18n %}{% translate "%s" %}'})
    def test_trans_tag_using_a_string_that_looks_like_str_fmt(self):
        """
        Tests the translation tag functionality using a string that resembles a string format.

        This test case checks if the translation engine correctly interprets and renders a template with a string
        that has a format similar to string formatting, ensuring that the translation is applied as expected
        and the resulting output matches the anticipated string format template.
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

        Tests rendering a template with translations in multiple locales.

        This test checks if a template containing a translation tag renders correctly 
        when the locale is switched between different languages. Specifically, it 
        verifies that the translation for 'No' is rendered as 'Nee' when the locale 
        is set to Dutch ('nl') after initially setting it to German ('de').

        """
        with translation.override("de"):
            t = self.get_template("{% load i18n %}{% translate 'No' %}")
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_deactivate_trans(self):
        """
        Test the translation deactivation for multiple locales.

        This test case verifies the correct rendering of a template with translations 
        deactivated for a specific locale ('de') and then activated for another locale ('nl'). 
        It checks that the translation is correctly applied when the locale is switched, 
        ensuring that the template renders the expected translation ('Nee' for Dutch).
        """
        with translation.override("de", deactivate=True):
            t = self.get_template("{% load i18n %}{% translate 'No' %}")
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_direct_switch_trans(self):
        """
        Tests the translation of a template string when switching between multiple locales.

        The function verifies that the translation is correctly applied when the locale is changed from German ('de') to Dutch ('nl').

        It checks that the translated string 'No' is rendered as 'Nee' when the locale is set to Dutch.
        """
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
