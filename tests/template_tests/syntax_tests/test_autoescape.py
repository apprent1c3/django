from django.template import TemplateSyntaxError
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import SafeClass, UnsafeClass, setup


class AutoescapeTagTests(SimpleTestCase):
    @setup({"autoescape-tag01": "{% autoescape off %}hello{% endautoescape %}"})
    def test_autoescape_tag01(self):
        output = self.engine.render_to_string("autoescape-tag01")
        self.assertEqual(output, "hello")

    @setup({"autoescape-tag02": "{% autoescape off %}{{ first }}{% endautoescape %}"})
    def test_autoescape_tag02(self):
        """
        Tests whether the autoescape tag works correctly when set to 'off' within a template. 
        It checks if HTML tags passed as template variables are rendered without being escaped. 
        The test case verifies that the output contains the expected unescaped HTML content.
        """
        output = self.engine.render_to_string(
            "autoescape-tag02", {"first": "<b>hello</b>"}
        )
        self.assertEqual(output, "<b>hello</b>")

    @setup({"autoescape-tag03": "{% autoescape on %}{{ first }}{% endautoescape %}"})
    def test_autoescape_tag03(self):
        """
        Tests the autoescape functionality in the templating engine, ensuring that HTML characters are properly escaped.

        The test case verifies that when autoescape is enabled, the templating engine correctly escapes HTML tags in the input data, preventing potential security vulnerabilities such as cross-site scripting (XSS) attacks.

        Args:
            None

        Returns:
            None, but the test passes if the output of the templating engine matches the expected escaped HTML string.
        """
        output = self.engine.render_to_string(
            "autoescape-tag03", {"first": "<b>hello</b>"}
        )
        self.assertEqual(output, "&lt;b&gt;hello&lt;/b&gt;")

    # Autoescape disabling and enabling nest in a predictable way.
    @setup(
        {
            "autoescape-tag04": (
                "{% autoescape off %}{{ first }} {% autoescape on %}{{ first }}"
                "{% endautoescape %}{% endautoescape %}"
            )
        }
    )
    def test_autoescape_tag04(self):
        """
        Tests the autoescape tag functionality in the templating engine, specifically verifying that the output of a template with autoescape toggled on and off produces the expected HTML-escaped and unescaped results. 

        The test checks that when autoescape is off, HTML characters are rendered as is, and when autoescape is on, HTML characters are properly escaped to prevent potential security vulnerabilities. 

        The expected output is a combination of an unescaped HTML character and its corresponding escaped representation, ensuring that the templating engine correctly handles autoescape tag directives.
        """
        output = self.engine.render_to_string("autoescape-tag04", {"first": "<a>"})
        self.assertEqual(output, "<a> &lt;a&gt;")

    @setup({"autoescape-tag05": "{% autoescape on %}{{ first }}{% endautoescape %}"})
    def test_autoescape_tag05(self):
        """
        Tests the autoescape functionality in templates.

        This test verifies that autoescape is enabled correctly when using the autoescape
        tag. It checks that HTML special characters in template variables are properly
        escaped, preventing potential XSS vulnerabilities.

        The test case renders a template with the autoescape tag and a variable containing
        HTML markup, then asserts that the output is escaped as expected.

        :param None
        :returns: None
        :raises AssertionError: if the autoescape functionality is not working correctly
        """
        output = self.engine.render_to_string(
            "autoescape-tag05", {"first": "<b>first</b>"}
        )
        self.assertEqual(output, "&lt;b&gt;first&lt;/b&gt;")

    # Strings (ASCII or Unicode) already marked as "safe" are not
    # auto-escaped
    @setup({"autoescape-tag06": "{{ first }}"})
    def test_autoescape_tag06(self):
        output = self.engine.render_to_string(
            "autoescape-tag06", {"first": mark_safe("<b>first</b>")}
        )
        self.assertEqual(output, "<b>first</b>")

    @setup({"autoescape-tag07": "{% autoescape on %}{{ first }}{% endautoescape %}"})
    def test_autoescape_tag07(self):
        output = self.engine.render_to_string(
            "autoescape-tag07", {"first": mark_safe("<b>Apple</b>")}
        )
        self.assertEqual(output, "<b>Apple</b>")

    @setup(
        {
            "autoescape-tag08": (
                r'{% autoescape on %}{{ var|default_if_none:" endquote\" hah" }}'
                r"{% endautoescape %}"
            )
        }
    )
    def test_autoescape_tag08(self):
        """
        Literal string arguments to filters, if used in the result, are safe.
        """
        output = self.engine.render_to_string("autoescape-tag08", {"var": None})
        self.assertEqual(output, ' endquote" hah')

    # Objects which return safe strings as their __str__ method
    # won't get double-escaped.
    @setup({"autoescape-tag09": r"{{ unsafe }}"})
    def test_autoescape_tag09(self):
        output = self.engine.render_to_string(
            "autoescape-tag09", {"unsafe": UnsafeClass()}
        )
        self.assertEqual(output, "you &amp; me")

    @setup({"autoescape-tag10": r"{{ safe }}"})
    def test_autoescape_tag10(self):
        output = self.engine.render_to_string("autoescape-tag10", {"safe": SafeClass()})
        self.assertEqual(output, "you &gt; me")

    @setup(
        {
            "autoescape-filtertag01": (
                "{{ first }}{% filter safe %}{{ first }} x<y{% endfilter %}"
            )
        }
    )
    def test_autoescape_filtertag01(self):
        """
        The "safe" and "escape" filters cannot work due to internal
        implementation details (fortunately, the (no)autoescape block
        tags can be used in those cases)
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("autoescape-filtertag01", {"first": "<a>"})

    # Arguments to filters are 'safe' and manipulate their input unescaped.
    @setup({"autoescape-filters01": '{{ var|cut:"&" }}'})
    def test_autoescape_filters01(self):
        """
        Test the autoescaping of template filters in the engine, specifically the cut filter.
        The function checks if the engine correctly removes specified characters from a variable.
        In this case, it verifies that the '&' character is removed from the string 'this & that', resulting in 'this  that'.
        """
        output = self.engine.render_to_string(
            "autoescape-filters01", {"var": "this & that"}
        )
        self.assertEqual(output, "this  that")

    @setup({"autoescape-filters02": '{{ var|join:" & " }}'})
    def test_autoescape_filters02(self):
        """
        Tests the autoescape filters functionality with the join filter.

        This test case verifies that the join filter can be used to concatenate 
        tuple elements with a specified separator. The test input is a tuple 
        of names and the expected output is a string where the names are joined 
        by ' & '. The test ensures that the engine correctly renders the template 
        with the provided variable and filter, resulting in the expected output string.
        """
        output = self.engine.render_to_string(
            "autoescape-filters02", {"var": ("Tom", "Dick", "Harry")}
        )
        self.assertEqual(output, "Tom & Dick & Harry")

    @setup({"autoescape-literals01": '{{ "this & that" }}'})
    def test_autoescape_literals01(self):
        """
        Literal strings are safe.
        """
        output = self.engine.render_to_string("autoescape-literals01")
        self.assertEqual(output, "this & that")

    @setup({"autoescape-stringiterations01": "{% for l in var %}{{ l }},{% endfor %}"})
    def test_autoescape_stringiterations01(self):
        """
        Iterating over strings outputs safe characters.
        """
        output = self.engine.render_to_string(
            "autoescape-stringiterations01", {"var": "K&R"}
        )
        self.assertEqual(output, "K,&amp;,R,")

    @setup({"autoescape-lookup01": "{{ var.key }}"})
    def test_autoescape_lookup01(self):
        """
        Escape requirement survives lookup.
        """
        output = self.engine.render_to_string(
            "autoescape-lookup01", {"var": {"key": "this & that"}}
        )
        self.assertEqual(output, "this &amp; that")

    @setup(
        {
            "autoescape-incorrect-arg": (
                "{% autoescape true %}{{ var.key }}{% endautoescape %}"
            )
        }
    )
    def test_invalid_arg(self):
        msg = "'autoescape' argument should be 'on' or 'off'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string(
                "autoescape-incorrect-arg", {"var": {"key": "this & that"}}
            )

    @setup(
        {"autoescape-incorrect-arg": "{% autoescape %}{{ var.key }}{% endautoescape %}"}
    )
    def test_no_arg(self):
        """
        Tests that the 'autoescape' template tag raises a TemplateSyntaxError when no argument is provided.

        This test case verifies that the 'autoescape' tag correctly enforces its requirement of having exactly one argument.
        It checks that a TemplateSyntaxError is raised with a specific error message when the tag is used without any arguments.

        The test uses a template string containing the 'autoescape' tag without any argument and attempts to render it to a string.
        It then asserts that the expected error message is included in the raised exception, indicating that the 'autoescape' tag requires exactly one argument to function correctly.
        """
        msg = "'autoescape' tag requires exactly one argument."
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string(
                "autoescape-incorrect-arg", {"var": {"key": "this & that"}}
            )
