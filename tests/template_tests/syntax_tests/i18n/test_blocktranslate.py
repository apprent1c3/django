import inspect
import os
from functools import partial, wraps

from asgiref.local import Local

from django.template import Context, Template, TemplateSyntaxError
from django.template.base import Token, TokenType
from django.templatetags.i18n import BlockTranslateNode
from django.test import SimpleTestCase, override_settings
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import trans_real

from ...utils import setup as base_setup
from .base import MultipleLocaleActivationTestCase, extended_locale_paths, here


def setup(templates, *args, **kwargs):
    blocktranslate_setup = base_setup(templates, *args, **kwargs)
    blocktrans_setup = base_setup(
        {
            name: template.replace("{% blocktranslate ", "{% blocktrans ").replace(
                "{% endblocktranslate %}", "{% endblocktrans %}"
            )
            for name, template in templates.items()
        }
    )

    tags = {
        "blocktrans": blocktrans_setup,
        "blocktranslate": blocktranslate_setup,
    }

    def decorator(func):
        @wraps(func)
        def inner(self, *args):
            """

            Inner function that wraps the original function to handle tags.

            This function takes care of setting up the tags by calling the provided setup functions.
            It checks the signature of the original function to determine if a 'tag_name' parameter is present.
            If 'tag_name' is present, the setup function is called with the original function, partly applied with the 'tag_name' argument.
            Otherwise, the setup function is called directly with the original function.
            The result of the setup function is then called on the instance.

            :param args: variable number of arguments passed to the original function
            :returns: result of the setup function applied to the instance

            """
            signature = inspect.signature(func)
            for tag_name, setup_func in tags.items():
                if "tag_name" in signature.parameters:
                    setup_func(partial(func, tag_name=tag_name))(self)
                else:
                    setup_func(func)(self)

        return inner

    return decorator


class I18nBlockTransTagTests(SimpleTestCase):
    libraries = {"i18n": "django.templatetags.i18n"}

    @setup(
        {
            "i18n03": (
                "{% load i18n %}{% blocktranslate %}{{ anton }}{% endblocktranslate %}"
            )
        }
    )
    def test_i18n03(self):
        """simple translation of a variable"""
        output = self.engine.render_to_string("i18n03", {"anton": "Å"})
        self.assertEqual(output, "Å")

    @setup(
        {
            "i18n04": (
                "{% load i18n %}{% blocktranslate with berta=anton|lower %}{{ berta }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n04(self):
        """simple translation of a variable and filter"""
        output = self.engine.render_to_string("i18n04", {"anton": "Å"})
        self.assertEqual(output, "å")

    @setup(
        {
            "legacyi18n04": (
                "{% load i18n %}"
                "{% blocktranslate with anton|lower as berta %}{{ berta }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_legacyi18n04(self):
        """simple translation of a variable and filter"""
        output = self.engine.render_to_string("legacyi18n04", {"anton": "Å"})
        self.assertEqual(output, "å")

    @setup(
        {
            "i18n05": (
                "{% load i18n %}{% blocktranslate %}xxx{{ anton }}xxx"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n05(self):
        """simple translation of a string with interpolation"""
        output = self.engine.render_to_string("i18n05", {"anton": "yyy"})
        self.assertEqual(output, "xxxyyyxxx")

    @setup(
        {
            "i18n07": "{% load i18n %}"
            "{% blocktranslate count counter=number %}singular{% plural %}"
            "{{ counter }} plural{% endblocktranslate %}"
        }
    )
    def test_i18n07(self):
        """translation of singular form"""
        output = self.engine.render_to_string("i18n07", {"number": 1})
        self.assertEqual(output, "singular")

    @setup(
        {
            "legacyi18n07": "{% load i18n %}"
            "{% blocktranslate count number as counter %}singular{% plural %}"
            "{{ counter }} plural{% endblocktranslate %}"
        }
    )
    def test_legacyi18n07(self):
        """translation of singular form"""
        output = self.engine.render_to_string("legacyi18n07", {"number": 1})
        self.assertEqual(output, "singular")

    @setup(
        {
            "i18n08": "{% load i18n %}"
            "{% blocktranslate count number as counter %}singular{% plural %}"
            "{{ counter }} plural{% endblocktranslate %}"
        }
    )
    def test_i18n08(self):
        """translation of plural form"""
        output = self.engine.render_to_string("i18n08", {"number": 2})
        self.assertEqual(output, "2 plural")

    @setup(
        {
            "legacyi18n08": "{% load i18n %}"
            "{% blocktranslate count counter=number %}singular{% plural %}"
            "{{ counter }} plural{% endblocktranslate %}"
        }
    )
    def test_legacyi18n08(self):
        """translation of plural form"""
        output = self.engine.render_to_string("legacyi18n08", {"number": 2})
        self.assertEqual(output, "2 plural")

    @setup(
        {
            "i18n17": (
                "{% load i18n %}"
                "{% blocktranslate with berta=anton|escape %}{{ berta }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n17(self):
        """
        Escaping inside blocktranslate and translate works as if it was
        directly in the template.
        """
        output = self.engine.render_to_string("i18n17", {"anton": "α & β"})
        self.assertEqual(output, "α &amp; β")

    @setup(
        {
            "i18n18": (
                "{% load i18n %}"
                "{% blocktranslate with berta=anton|force_escape %}{{ berta }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n18(self):
        output = self.engine.render_to_string("i18n18", {"anton": "α & β"})
        self.assertEqual(output, "α &amp; β")

    @setup(
        {
            "i18n19": (
                "{% load i18n %}{% blocktranslate %}{{ andrew }}{% endblocktranslate %}"
            )
        }
    )
    def test_i18n19(self):
        output = self.engine.render_to_string("i18n19", {"andrew": "a & b"})
        self.assertEqual(output, "a &amp; b")

    @setup(
        {
            "i18n21": (
                "{% load i18n %}{% blocktranslate %}{{ andrew }}{% endblocktranslate %}"
            )
        }
    )
    def test_i18n21(self):
        """

        Tests the rendering of a template containing a translated block with HTML entities.

        Verifies that the output of the template contains the correct translation and that
        HTML entities are properly escaped. The test case uses a template with a block
        translated string and a variable containing HTML entities, ensuring that the
        rendering engine correctly handles these entities.

        Args:
            None

        Returns:
            None

        Asserts:
            The rendered output matches the expected string.

        """
        output = self.engine.render_to_string("i18n21", {"andrew": mark_safe("a & b")})
        self.assertEqual(output, "a & b")

    @setup(
        {
            "legacyi18n17": (
                "{% load i18n %}"
                "{% blocktranslate with anton|escape as berta %}{{ berta }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_legacyi18n17(self):
        output = self.engine.render_to_string("legacyi18n17", {"anton": "α & β"})
        self.assertEqual(output, "α &amp; β")

    @setup(
        {
            "legacyi18n18": "{% load i18n %}"
            "{% blocktranslate with anton|force_escape as berta %}"
            "{{ berta }}{% endblocktranslate %}"
        }
    )
    def test_legacyi18n18(self):
        output = self.engine.render_to_string("legacyi18n18", {"anton": "α & β"})
        self.assertEqual(output, "α &amp; β")

    @setup(
        {
            "i18n26": "{% load i18n %}"
            "{% blocktranslate with extra_field=myextra_field count counter=number %}"
            "singular {{ extra_field }}{% plural %}plural{% endblocktranslate %}"
        }
    )
    def test_i18n26(self):
        """
        translation of plural form with extra field in singular form (#13568)
        """
        output = self.engine.render_to_string(
            "i18n26", {"myextra_field": "test", "number": 1}
        )
        self.assertEqual(output, "singular test")

    @setup(
        {
            "legacyi18n26": (
                "{% load i18n %}"
                "{% blocktranslate with myextra_field as extra_field "
                "count number as counter %}singular {{ extra_field }}{% plural %}plural"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_legacyi18n26(self):
        """

        Tests rendering of a legacy i18n template block with a custom field and pluralization.

        This test verifies that the template engine correctly handles the legacy i18n syntax,
        including the use of a custom field and the pluralization of a string based on a count.
        The expected output is a singular string with the custom field value when the count is 1.

        """
        output = self.engine.render_to_string(
            "legacyi18n26", {"myextra_field": "test", "number": 1}
        )
        self.assertEqual(output, "singular test")

    @setup(
        {
            "i18n27": "{% load i18n %}{% blocktranslate count counter=number %}"
            "{{ counter }} result{% plural %}{{ counter }} results"
            "{% endblocktranslate %}"
        }
    )
    def test_i18n27(self):
        """translation of singular form in Russian (#14126)"""
        with translation.override("ru"):
            output = self.engine.render_to_string("i18n27", {"number": 1})
        self.assertEqual(
            output, "1 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442"
        )

    @setup(
        {
            "legacyi18n27": "{% load i18n %}"
            "{% blocktranslate count number as counter %}{{ counter }} result"
            "{% plural %}{{ counter }} results{% endblocktranslate %}"
        }
    )
    def test_legacyi18n27(self):
        """

        Tests the rendering of a legacy i18n template with blocktranslate and plural tags.

        Verifies that the rendered output is correctly translated when the locale is set to Russian ('ru').
        The test checks the correct usage of the plural form for the given number.

        """
        with translation.override("ru"):
            output = self.engine.render_to_string("legacyi18n27", {"number": 1})
        self.assertEqual(
            output, "1 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442"
        )

    @setup(
        {
            "i18n28": (
                "{% load i18n %}"
                "{% blocktranslate with a=anton b=berta %}{{ a }} + {{ b }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n28(self):
        """simple translation of multiple variables"""
        output = self.engine.render_to_string("i18n28", {"anton": "α", "berta": "β"})
        self.assertEqual(output, "α + β")

    @setup(
        {
            "legacyi18n28": "{% load i18n %}"
            "{% blocktranslate with anton as a and berta as b %}"
            "{{ a }} + {{ b }}{% endblocktranslate %}"
        }
    )
    def test_legacyi18n28(self):
        """
        Tests the rendering of a legacy i18n template blocktranslate.

        Verifies that the template engine correctly renders a template string containing 
        a blocktranslate tag with variables, replacing the variable names with their 
        respective values.

        Args:
            None

        Returns:
            None

        Note:
            This test case checks for the correct output of a specific template rendering 
            scenario, ensuring that the template engine behaves as expected when handling 
            legacy i18n syntax.

        """
        output = self.engine.render_to_string(
            "legacyi18n28", {"anton": "α", "berta": "β"}
        )
        self.assertEqual(output, "α + β")

    # blocktranslate handling of variables which are not in the context.
    # this should work as if blocktranslate was not there (#19915)
    @setup(
        {
            "i18n34": (
                "{% load i18n %}{% blocktranslate %}{{ missing }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n34(self):
        """

        Tests the rendering of internationalization (i18n) blocktranslate tags.

        Verifies that the i18n34 template renders correctly, checking for the presence
        of the 'INVALID' string if the engine is configured to raise an exception on
        invalid variables, or an empty string otherwise.

        """
        output = self.engine.render_to_string("i18n34")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup(
        {
            "i18n34_2": (
                "{% load i18n %}{% blocktranslate with a='α' %}{{ missing }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n34_2(self):
        """
        Tests the rendering of a template block with an untranslatable string.

        Verifies that the engine correctly handles the rendering of a blocktranslate
        tag with a missing translation, when the 'string_if_invalid' setting is
        enabled or disabled. The test checks that the output is either the
        'string_if_invalid' value or an empty string, depending on the engine's
        configuration.

        :raises AssertionError: if the rendered output does not match the expected
            value based on the 'string_if_invalid' setting.
        """
        output = self.engine.render_to_string("i18n34_2")
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup(
        {
            "i18n34_3": (
                "{% load i18n %}{% blocktranslate with a=anton %}{{ missing }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_i18n34_3(self):
        """
        Tests the handling of missing variables in a blocktranslate tag with the i18n template extension. 

        Checks if the templating engine correctly renders the template when a required variable is not provided, 
        either by outputting an 'INVALID' string if string_if_invalid is set, or an empty string otherwise.
        """
        output = self.engine.render_to_string("i18n34_3", {"anton": "\xce\xb1"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup(
        {
            "i18n37": "{% load i18n %}"
            '{% translate "Page not found" as page_not_found %}'
            "{% blocktranslate %}Error: {{ page_not_found }}{% endblocktranslate %}"
        }
    )
    def test_i18n37(self):
        """

        Tests the i18n37 template tag by rendering a template with a translation block.

        The test case overrides the language to German and checks if the expected translation
        of 'Page not found' is correctly rendered as 'Seite nicht gefunden'.

        This verifies that the translation mechanism is working correctly and that the
        blocktranslate tag is properly handling the translation of the given text.

        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n37")
        self.assertEqual(output, "Error: Seite nicht gefunden")

    # blocktranslate tag with asvar
    @setup(
        {
            "i18n39": (
                "{% load i18n %}"
                "{% blocktranslate asvar page_not_found %}Page not found"
                "{% endblocktranslate %}>{{ page_not_found }}<"
            )
        }
    )
    def test_i18n39(self):
        """

        Tests if the i18n template tag correctly translates a block of text.

        This test ensures that when the locale is set to German ('de'), the
        translated string \"Seite nicht gefunden\" is correctly rendered in the
        template. The test case verifies that the translation system is properly
        overridden and that the translated text is output as expected.

        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n39")
        self.assertEqual(output, ">Seite nicht gefunden<")

    @setup(
        {
            "i18n40": "{% load i18n %}"
            '{% translate "Page not found" as pg_404 %}'
            "{% blocktranslate with page_not_found=pg_404 asvar output %}"
            "Error: {{ page_not_found }}"
            "{% endblocktranslate %}"
        }
    )
    def test_i18n40(self):
        output = self.engine.render_to_string("i18n40")
        self.assertEqual(output, "")

    @setup(
        {
            "i18n41": "{% load i18n %}"
            '{% translate "Page not found" as pg_404 %}'
            "{% blocktranslate with page_not_found=pg_404 asvar output %}"
            "Error: {{ page_not_found }}"
            "{% endblocktranslate %}"
            ">{{ output }}<"
        }
    )
    def test_i18n41(self):
        """

         Tests that the i18n template tag correctly translates a string using the
         current locale.

         This test case verifies that when the locale is set to German ('de'), the 
         'Page not found' string is accurately translated to 'Seite nicht gefunden'.

         The test uses the `translation.override` context manager to temporarily
         switch the locale to German, and then checks that the rendered template
         output matches the expected translated string.

        """
        with translation.override("de"):
            output = self.engine.render_to_string("i18n41")
        self.assertEqual(output, ">Error: Seite nicht gefunden<")

    @setup(
        {
            "i18n_asvar_safestring": (
                "{% load i18n %}"
                "{% blocktranslate asvar the_title %}"
                "{{title}}other text"
                "{% endblocktranslate %}"
                "{{ the_title }}"
            )
        }
    )
    def test_i18n_asvar_safestring(self):
        """

        Tests the i18n 'asvar' and 'safestring' functionality within the templating engine.

        The test case verifies that the 'blocktranslate' tag can be used with the 'asvar' keyword
        to store the translated string in a variable and that the 'safestring' functionality
        correctly escapes any HTML entities in the original string.

        The expected output is a string where the title is replaced with its HTML-escaped version,
        followed by the additional text.

        """
        context = {"title": "<Main Title>"}
        output = self.engine.render_to_string("i18n_asvar_safestring", context=context)
        self.assertEqual(output, "&lt;Main Title&gt;other text")

    @setup(
        {
            "template": (
                "{% load i18n %}{% blocktranslate asvar %}Yes{% endblocktranslate %}"
            )
        }
    )
    def test_blocktrans_syntax_error_missing_assignment(self, tag_name):
        """
        Tests the behavior of the '{% blocktranslate %}' template tag when the 'asvar' option is used without an assignment.

        The test verifies that a TemplateSyntaxError is raised when no argument is provided to the 'asvar' option of the '{% blocktranslate %}' tag. It checks that the error message correctly identifies the missing assignment and the name of the tag that caused the error.
        """
        msg = "No argument provided to the '{}' tag for the asvar option.".format(
            tag_name
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup({"template": "{% load i18n %}{% blocktranslate %}%s{% endblocktranslate %}"})
    def test_blocktrans_tag_using_a_string_that_looks_like_str_fmt(self):
        """
        Tests the blocktrans tag in templating engine using a string that resembles a string format specifier, verifying its correct rendering and translation.
        """
        output = self.engine.render_to_string("template")
        self.assertEqual(output, "%s")

    @setup(
        {
            "template": (
                "{% load i18n %}{% blocktranslate %}{% block b %} {% endblock %}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_with_block(self, tag_name):
        """
        Tests that a template tag does not allow block tags inside it.

        This test case checks for a specific template syntax error, where a block tag
        is used within another tag that does not support it. The test expects a
        TemplateSyntaxError to be raised with a message indicating the disallowed
        tag name.

        :param tag_name: The name of the template tag being tested.

        """
        msg = "'{}' doesn't allow other block tags (seen 'block b') inside it".format(
            tag_name
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup(
        {
            "template": (
                "{% load i18n %}"
                "{% blocktranslate %}{% for b in [1, 2, 3] %} {% endfor %}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_with_for(self, tag_name):
        """
        Tests that a specific template tag does not allow other block tags inside it.

        This function checks that using a 'for' loop inside a given block tag raises a TemplateSyntaxError.
        The error message is verified to contain the specific tag name and the disallowed block tag ('for').

        :param tag_name: The name of the template tag being tested.

        """
        msg = (
            f"'{tag_name}' doesn't allow other block tags (seen 'for b in [1, 2, 3]') "
            f"inside it"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup(
        {
            "template": (
                "{% load i18n %}{% blocktranslate with foo=bar with %}{{ foo }}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_variable_twice(self):
        """

        Test that using the 'with' option more than once in a 'blocktranslate' template tag raises a TemplateSyntaxError.

        The test verifies that the template engine correctly identifies and reports the error when the 'with' option is specified multiple times in a 'blocktranslate' block.

        Args:
            None

        Raises:
            TemplateSyntaxError: If the 'with' option is specified more than once in the 'blocktranslate' tag.

        Returns:
            None

        Notes:
            This test ensures that the template engine enforces correct syntax for the 'blocktranslate' tag, preventing potential errors or unexpected behavior in templates.

        """
        with self.assertRaisesMessage(
            TemplateSyntaxError, "The 'with' option was specified more than once"
        ):
            self.engine.render_to_string("template", {"foo": "bar"})

    @setup(
        {"template": "{% load i18n %}{% blocktranslate with %}{% endblocktranslate %}"}
    )
    def test_no_args_with(self, tag_name):
        msg = "\"with\" in '{}' tag needs at least one keyword argument.".format(
            tag_name
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template")

    @setup(
        {
            "template": (
                "{% load i18n %}{% blocktranslate count a %}{% endblocktranslate %}"
            )
        }
    )
    def test_count(self, tag_name):
        """
        Tests that the given templating tag raises a TemplateSyntaxError when the 'count' keyword argument is missing or repeated.

        The test ensures that the tag can only be used with a single 'count' keyword argument, verifying the correct usage of the tag in templating.

        :param tag_name: The name of the templating tag being tested.
        :raises TemplateSyntaxError: If the 'count' keyword argument is not provided or is repeated.

        """
        msg = "\"count\" in '{}' tag expected exactly one keyword argument.".format(
            tag_name
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template", {"a": [1, 2, 3]})

    @setup(
        {
            "template": (
                "{% load i18n %}{% blocktranslate count counter=num %}{{ counter }}"
                "{% plural %}{{ counter }}{% endblocktranslate %}"
            )
        }
    )
    def test_count_not_number(self, tag_name):
        """
        .. function:: test_count_not_number(self, tag_name)
           :noindex:

           Tests that a specific template tag raises a TemplateSyntaxError when its 'counter' argument is not a number.

           This function checks the behavior of the given template tag when provided with a non-numeric 'counter' value. It expects the tag to raise an exception with a message indicating that the 'counter' argument must be a number. The test is used to ensure that template tags handle invalid input correctly and provide useful error messages.
        """
        msg = "'counter' argument to '{}' tag must be a number.".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template", {"num": "1"})

    @setup(
        {
            "template": (
                "{% load i18n %}{% blocktranslate count count=var|length %}"
                "There is {{ count }} object. {% block a %} {% endblock %}"
                "{% endblocktranslate %}"
            )
        }
    )
    def test_plural_bad_syntax(self, tag_name):
        msg = "'{}' doesn't allow other block tags inside it".format(tag_name)
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("template", {"var": [1, 2, 3]})


class TranslationBlockTranslateTagTests(SimpleTestCase):
    tag_name = "blocktranslate"

    def get_template(self, template_string):
        return Template(
            template_string.replace(
                "{{% blocktranslate ", "{{% {}".format(self.tag_name)
            ).replace(
                "{{% endblocktranslate %}}", "{{% end{} %}}".format(self.tag_name)
            )
        )

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_template_tags_pgettext(self):
        """{% blocktranslate %} takes message contexts into account (#14806)."""
        trans_real._active = Local()
        trans_real._translations = {}
        with translation.override("de"):
            # Nonexistent context
            t = self.get_template(
                '{% load i18n %}{% blocktranslate context "nonexistent" %}May'
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "May")

            # Existing context...  using a literal
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate context "month name" %}May{% endblocktranslate %}'
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Mai")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate context "verb" %}May{% endblocktranslate %}'
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Kann")

            # Using a variable
            t = self.get_template(
                "{% load i18n %}{% blocktranslate context message_context %}"
                "May{% endblocktranslate %}"
            )
            rendered = t.render(Context({"message_context": "month name"}))
            self.assertEqual(rendered, "Mai")
            t = self.get_template(
                "{% load i18n %}{% blocktranslate context message_context %}"
                "May{% endblocktranslate %}"
            )
            rendered = t.render(Context({"message_context": "verb"}))
            self.assertEqual(rendered, "Kann")

            # Using a filter
            t = self.get_template(
                "{% load i18n %}"
                "{% blocktranslate context message_context|lower %}May"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context({"message_context": "MONTH NAME"}))
            self.assertEqual(rendered, "Mai")
            t = self.get_template(
                "{% load i18n %}"
                "{% blocktranslate context message_context|lower %}May"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context({"message_context": "VERB"}))
            self.assertEqual(rendered, "Kann")

            # Using 'count'
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate count number=1 context "super search" %}{{ number }}'
                " super result{% plural %}{{ number }} super results"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "1 Super-Ergebnis")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate count number=2 context "super search" %}{{ number }}'
                " super result{% plural %}{{ number }} super results"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "2 Super-Ergebnisse")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate context "other super search" count number=1 %}'
                "{{ number }} super result{% plural %}{{ number }} super results"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "1 anderen Super-Ergebnis")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate context "other super search" count number=2 %}'
                "{{ number }} super result{% plural %}{{ number }} super results"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "2 andere Super-Ergebnisse")

            # Using 'with'
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate with num_comments=5 context "comment count" %}'
                "There are {{ num_comments }} comments{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Es gibt 5 Kommentare")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate with num_comments=5 context "other comment count" %}'
                "There are {{ num_comments }} comments{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Andere: Es gibt 5 Kommentare")

            # Using trimmed
            t = self.get_template(
                "{% load i18n %}{% blocktranslate trimmed %}\n\nThere\n\t are 5  "
                "\n\n   comments\n{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "There are 5 comments")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate with num_comments=5 context "comment count" trimmed '
                "%}\n\n"
                "There are  \t\n  \t {{ num_comments }} comments\n\n"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "Es gibt 5 Kommentare")
            t = self.get_template(
                "{% load i18n %}"
                '{% blocktranslate context "other super search" count number=2 trimmed '
                "%}\n{{ number }} super \n result{% plural %}{{ number }} super results"
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context())
            self.assertEqual(rendered, "2 andere Super-Ergebnisse")

            # Misuses
            msg = "Unknown argument for 'blocktranslate' tag: %r."
            with self.assertRaisesMessage(TemplateSyntaxError, msg % 'month="May"'):
                self.get_template(
                    '{% load i18n %}{% blocktranslate context with month="May" %}'
                    "{{ month }}{% endblocktranslate %}"
                )
            msg = (
                '"context" in %r tag expected exactly one argument.' % "blocktranslate"
            )
            with self.assertRaisesMessage(TemplateSyntaxError, msg):
                self.get_template(
                    "{% load i18n %}{% blocktranslate context %}{% endblocktranslate %}"
                )
            with self.assertRaisesMessage(TemplateSyntaxError, msg):
                self.get_template(
                    "{% load i18n %}{% blocktranslate count number=2 context %}"
                    "{{ number }} super result{% plural %}{{ number }}"
                    " super results{% endblocktranslate %}"
                )

    @override_settings(LOCALE_PATHS=[os.path.join(here, "other", "locale")])
    def test_bad_placeholder_1(self):
        """
        Error in translation file should not crash template rendering (#16516).
        (%(person)s is translated as %(personne)s in fr.po).
        """
        with translation.override("fr"):
            t = Template(
                "{% load i18n %}{% blocktranslate %}My name is {{ person }}."
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context({"person": "James"}))
            self.assertEqual(rendered, "My name is James.")

    @override_settings(LOCALE_PATHS=[os.path.join(here, "other", "locale")])
    def test_bad_placeholder_2(self):
        """
        Error in translation file should not crash template rendering (#18393).
        (%(person) misses a 's' in fr.po, causing the string formatting to fail)
        .
        """
        with translation.override("fr"):
            t = Template(
                "{% load i18n %}{% blocktranslate %}My other name is {{ person }}."
                "{% endblocktranslate %}"
            )
            rendered = t.render(Context({"person": "James"}))
            self.assertEqual(rendered, "My other name is James.")


class TranslationBlockTransnTagTests(TranslationBlockTranslateTagTests):
    tag_name = "blocktrans"


class MultipleLocaleActivationBlockTranslateTests(MultipleLocaleActivationTestCase):
    tag_name = "blocktranslate"

    def get_template(self, template_string):
        return Template(
            template_string.replace(
                "{{% blocktranslate ", "{{% {}".format(self.tag_name)
            ).replace(
                "{{% endblocktranslate %}}", "{{% end{} %}}".format(self.tag_name)
            )
        )

    def test_single_locale_activation(self):
        """
        Simple baseline behavior with one locale for all the supported i18n
        constructs.
        """
        with translation.override("fr"):
            self.assertEqual(
                self.get_template(
                    "{% load i18n %}{% blocktranslate %}Yes{% endblocktranslate %}"
                ).render(Context({})),
                "Oui",
            )

    def test_multiple_locale_btrans(self):
        """

        Tests the translation of a block of text with blocktranslate template tag in multiple locales.

        This test ensures that the blocktranslate tag correctly translates text to the
        specified locale. It checks the translation in two different languages: German ('de')
        and Dutch ('nl'). The test verifies that the rendered template contains the
        correctly translated text for each locale.

        """
        with translation.override("de"):
            t = self.get_template(
                "{% load i18n %}{% blocktranslate %}No{% endblocktranslate %}"
            )
        with translation.override(self._old_language), translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_deactivate_btrans(self):
        """
        Test that a block translation is rendered correctly when switching between multiple locales.

        This test case verifies that the block translation is deactivated when the locale is changed to 'de' and then reactivated when the locale is changed to 'nl'. The expected output is the translated string 'Nee' in the 'nl' locale.

        The test ensures that the block translation behaves correctly in a scenario where the locale is switched multiple times, and that the correct translation is rendered when the locale is set to 'nl'.
        """
        with translation.override("de", deactivate=True):
            t = self.get_template(
                "{% load i18n %}{% blocktranslate %}No{% endblocktranslate %}"
            )
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")

    def test_multiple_locale_direct_switch_btrans(self):
        """
        Test the blocktranslate tag with direct locale switching.

        This test case checks if the blocktranslate tag behaves correctly when the locale is switched directly.
        It verifies that the translation of a given string is correct after the locale has been changed to German ('de') and then Dutch ('nl').
        The test renders a template containing a blocktranslate tag and asserts that the resulting translation matches the expected output for the 'nl' locale.
        """
        with translation.override("de"):
            t = self.get_template(
                "{% load i18n %}{% blocktranslate %}No{% endblocktranslate %}"
            )
        with translation.override("nl"):
            self.assertEqual(t.render(Context({})), "Nee")


class MultipleLocaleActivationBlockTransTests(
    MultipleLocaleActivationBlockTranslateTests
):
    tag_name = "blocktrans"


class MiscTests(SimpleTestCase):
    tag_name = "blocktranslate"

    def get_template(self, template_string):
        return Template(
            template_string.replace(
                "{{% blocktranslate ", "{{% {}".format(self.tag_name)
            ).replace(
                "{{% endblocktranslate %}}", "{{% end{} %}}".format(self.tag_name)
            )
        )

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_percent_in_translatable_block(self):
        """
        Tests the rendering of a translatable block containing a percentage value.

        This function checks that the translation of a template block containing a
        percentage value is correct in both singular and plural forms. It uses the
        Django template language and the i18n module to load and render templates,
        and overrides the locale settings to test the translation in the German locale.

        The function covers two cases: a simple translatable block with a percentage
        value, and a block with a plural form that depends on a count variable. The
        expected translations are compared to the actual rendered output to ensure
        correctness.

        The tests cover the following scenarios:
        - Rendering a simple translatable block with a percentage value
        - Rendering a plural translatable block with a percentage value for singular and plural forms
        """
        t_sing = self.get_template(
            "{% load i18n %}{% blocktranslate %}The result was {{ percent }}%"
            "{% endblocktranslate %}"
        )
        t_plur = self.get_template(
            "{% load i18n %}{% blocktranslate count num as number %}"
            "{{ percent }}% represents {{ num }} object{% plural %}"
            "{{ percent }}% represents {{ num }} objects{% endblocktranslate %}"
        )
        with translation.override("de"):
            self.assertEqual(
                t_sing.render(Context({"percent": 42})), "Das Ergebnis war 42%"
            )
            self.assertEqual(
                t_plur.render(Context({"percent": 42, "num": 1})),
                "42% stellt 1 Objekt dar",
            )
            self.assertEqual(
                t_plur.render(Context({"percent": 42, "num": 4})),
                "42% stellt 4 Objekte dar",
            )

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_percent_formatting_in_blocktranslate(self):
        """
        Python's %-formatting is properly escaped in blocktranslate, singular,
        or plural.
        """
        t_sing = self.get_template(
            "{% load i18n %}{% blocktranslate %}There are %(num_comments)s comments"
            "{% endblocktranslate %}"
        )
        t_plur = self.get_template(
            "{% load i18n %}{% blocktranslate count num as number %}"
            "%(percent)s% represents {{ num }} object{% plural %}"
            "%(percent)s% represents {{ num }} objects{% endblocktranslate %}"
        )
        with translation.override("de"):
            # Strings won't get translated as they don't match after escaping %
            self.assertEqual(
                t_sing.render(Context({"num_comments": 42})),
                "There are %(num_comments)s comments",
            )
            self.assertEqual(
                t_plur.render(Context({"percent": 42, "num": 1})),
                "%(percent)s% represents 1 object",
            )
            self.assertEqual(
                t_plur.render(Context({"percent": 42, "num": 4})),
                "%(percent)s% represents 4 objects",
            )


class MiscBlockTranslationTests(MiscTests):
    tag_name = "blocktrans"


class BlockTranslateNodeTests(SimpleTestCase):
    def test_repr(self):
        """

        Tests the representation of a BlockTranslateNode instance.

        Verifies that the `repr` method returns a string that accurately represents the state of the node,
        including its extra context, singular and plural translations.

        The output string is expected to be in a human-readable format, providing a concise summary of the node's properties.

        """
        block_translate_node = BlockTranslateNode(
            extra_context={},
            singular=[
                Token(TokenType.TEXT, "content"),
                Token(TokenType.VAR, "variable"),
            ],
        )
        self.assertEqual(
            repr(block_translate_node),
            "<BlockTranslateNode: extra_context={} "
            'singular=[<Text token: "content...">, <Var token: "variable...">] '
            "plural=None>",
        )
