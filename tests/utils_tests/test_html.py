import os
from datetime import datetime

from django.core.serializers.json import DjangoJSONEncoder
from django.test import SimpleTestCase
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.functional import lazystr
from django.utils.html import (
    conditional_escape,
    escape,
    escapejs,
    format_html,
    html_safe,
    json_script,
    linebreaks,
    smart_urlquote,
    strip_spaces_between_tags,
    strip_tags,
    urlize,
)
from django.utils.safestring import mark_safe


class TestUtilsHtml(SimpleTestCase):
    def check_output(self, function, value, output=None):
        """
        function(value) equals output. If output is None, function(value)
        equals value.
        """
        if output is None:
            output = value
        self.assertEqual(function(value), output)

    def test_escape(self):
        """

        Tests the escape function to ensure it correctly replaces special characters with their HTML entity equivalents.

        The function tests various input patterns and values, including ampersand, less than, greater than, double quote, and single quote characters.
        It verifies that the escape function can handle simple and complex input strings, as well as repeated characters.

        Additionally, it checks the function's behavior with both string and lazy string inputs, ensuring consistent output in all cases.

        The test cases cover a range of scenarios to provide comprehensive coverage of the escape function's functionality.

        """
        items = (
            ("&", "&amp;"),
            ("<", "&lt;"),
            (">", "&gt;"),
            ('"', "&quot;"),
            ("'", "&#x27;"),
        )
        # Substitution patterns for testing the above items.
        patterns = ("%s", "asdf%sfdsa", "%s1", "1%sb")
        for value, output in items:
            with self.subTest(value=value, output=output):
                for pattern in patterns:
                    with self.subTest(value=value, output=output, pattern=pattern):
                        self.check_output(escape, pattern % value, pattern % output)
                        self.check_output(
                            escape, lazystr(pattern % value), pattern % output
                        )
                # Check repeated values.
                self.check_output(escape, value * 2, output * 2)
        # Verify it doesn't double replace &.
        self.check_output(escape, "<&", "&lt;&amp;")

    def test_format_html(self):
        self.assertEqual(
            format_html(
                "{} {} {third} {fourth}",
                "< Dangerous >",
                mark_safe("<b>safe</b>"),
                third="< dangerous again",
                fourth=mark_safe("<i>safe again</i>"),
            ),
            "&lt; Dangerous &gt; <b>safe</b> &lt; dangerous again <i>safe again</i>",
        )

    def test_format_html_no_params(self):
        msg = "Calling format_html() without passing args or kwargs is deprecated."
        # RemovedInDjango60Warning: when the deprecation ends, replace with:
        # msg = "args or kwargs must be provided."
        # with self.assertRaisesMessage(ValueError, msg):
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            name = "Adam"
            self.assertEqual(format_html(f"<i>{name}</i>"), "<i>Adam</i>")

    def test_linebreaks(self):
        """
        Tests the linebreaks function to ensure it correctly handles various types of line breaks and formatting.

        The function is tested with a range of input strings containing different types of line breaks, including newline characters, carriage returns, and tab characters. The expected output is compared to the actual output to verify that the function is correctly converting these line breaks into HTML-compatible breaks.

        The test cases cover a variety of scenarios, including multiple consecutive line breaks, line breaks within paragraphs, and line breaks at the start or end of a string. The function is also tested with both regular strings and lazy strings to ensure it works correctly in both cases.

        Overall, this test ensures that the linebreaks function is working as expected and producing the correct output for a range of different input strings and formatting scenarios.
        """
        items = (
            ("para1\n\npara2\r\rpara3", "<p>para1</p>\n\n<p>para2</p>\n\n<p>para3</p>"),
            (
                "para1\nsub1\rsub2\n\npara2",
                "<p>para1<br>sub1<br>sub2</p>\n\n<p>para2</p>",
            ),
            (
                "para1\r\n\r\npara2\rsub1\r\rpara4",
                "<p>para1</p>\n\n<p>para2<br>sub1</p>\n\n<p>para4</p>",
            ),
            ("para1\tmore\n\npara2", "<p>para1\tmore</p>\n\n<p>para2</p>"),
        )
        for value, output in items:
            with self.subTest(value=value, output=output):
                self.check_output(linebreaks, value, output)
                self.check_output(linebreaks, lazystr(value), output)

    def test_strip_tags(self):
        """
        Tests the strip_tags function by comparing its output to the expected output for a variety of input strings.

        The test cases cover a range of scenarios, including HTML tags with attributes, escaped characters, and malformed or nested tags.
        The function's ability to handle these cases is verified by checking the output against the expected result for each input string.

        This test ensures that the strip_tags function correctly removes HTML tags from input strings, leaving only the text content.
        It also verifies that the function works correctly with both regular strings and lazy strings, and that it handles a large number of consecutive HTML entities without issue.
        """
        items = (
            (
                "<p>See: &#39;&eacute; is an apostrophe followed by e acute</p>",
                "See: &#39;&eacute; is an apostrophe followed by e acute",
            ),
            (
                "<p>See: &#x27;&eacute; is an apostrophe followed by e acute</p>",
                "See: &#x27;&eacute; is an apostrophe followed by e acute",
            ),
            ("<adf>a", "a"),
            ("</adf>a", "a"),
            ("<asdf><asdf>e", "e"),
            ("hi, <f x", "hi, <f x"),
            ("234<235, right?", "234<235, right?"),
            ("a4<a5 right?", "a4<a5 right?"),
            ("b7>b2!", "b7>b2!"),
            ("</fe", "</fe"),
            ("<x>b<y>", "b"),
            ("a<p onclick=\"alert('<test>')\">b</p>c", "abc"),
            ("a<p a >b</p>c", "abc"),
            ("d<a:b c:d>e</p>f", "def"),
            ('<strong>foo</strong><a href="http://example.com">bar</a>', "foobar"),
            # caused infinite loop on Pythons not patched with
            # https://bugs.python.org/issue20288
            ("&gotcha&#;<>", "&gotcha&#;<>"),
            ("<sc<!-- -->ript>test<<!-- -->/script>", "ript>test"),
            ("<script>alert()</script>&h", "alert()h"),
            ("><!" + ("&" * 16000) + "D", "><!" + ("&" * 16000) + "D"),
            ("X<<<<br>br>br>br>X", "XX"),
        )
        for value, output in items:
            with self.subTest(value=value, output=output):
                self.check_output(strip_tags, value, output)
                self.check_output(strip_tags, lazystr(value), output)

    def test_strip_tags_files(self):
        # Test with more lengthy content (also catching performance regressions)
        for filename in ("strip_tags1.html", "strip_tags2.txt"):
            with self.subTest(filename=filename):
                path = os.path.join(os.path.dirname(__file__), "files", filename)
                with open(path) as fp:
                    content = fp.read()
                    start = datetime.now()
                    stripped = strip_tags(content)
                    elapsed = datetime.now() - start
                self.assertEqual(elapsed.seconds, 0)
                self.assertIn("Test string that has not been stripped.", stripped)
                self.assertNotIn("<", stripped)

    def test_strip_spaces_between_tags(self):
        # Strings that should come out untouched.
        """

        Tests the strip_spaces_between_tags function for removing whitespace between XML tags.

        This function checks that the strip_spaces_between_tags function correctly removes 
        spaces, tabs, and newline characters between XML tags, while preserving content 
        within the tags. It tests various input cases, including tags with leading or 
        trailing whitespace, empty tags, and tags with content. The function also 
        verifies that the strip_spaces_between_tags function works correctly with both 
        string and lazy string inputs.

        The test cases cover a range of scenarios to ensure the function behaves as 
        expected, including removal of whitespace between adjacent tags and preservation 
        of content and formatting within the tags.

        """
        items = (" <adf>", "<adf> ", " </adf> ", " <f> x</f>")
        for value in items:
            with self.subTest(value=value):
                self.check_output(strip_spaces_between_tags, value)
                self.check_output(strip_spaces_between_tags, lazystr(value))

        # Strings that have spaces to strip.
        items = (
            ("<d> </d>", "<d></d>"),
            ("<p>hello </p>\n<p> world</p>", "<p>hello </p><p> world</p>"),
            ("\n<p>\t</p>\n<p> </p>\n", "\n<p></p><p></p>\n"),
        )
        for value, output in items:
            with self.subTest(value=value, output=output):
                self.check_output(strip_spaces_between_tags, value, output)
                self.check_output(strip_spaces_between_tags, lazystr(value), output)

    def test_escapejs(self):
        """

        Test the escapejs function to ensure it correctly escapes special characters in JavaScript strings.

        This function validates the escapejs function's output for various input strings, 
        including those containing double quotes, single quotes, backslashes, whitespace, 
        and HTML script tags. It also checks escaping of Unicode characters, such as 
        paragraph and line separators.

        The test covers both regular strings and lazy strings as input to the escapejs function, 
        verifying that the output matches the expected escaped string in all cases.

        """
        items = (
            (
                "\"double quotes\" and 'single quotes'",
                "\\u0022double quotes\\u0022 and \\u0027single quotes\\u0027",
            ),
            (r"\ : backslashes, too", "\\u005C : backslashes, too"),
            (
                "and lots of whitespace: \r\n\t\v\f\b",
                "and lots of whitespace: \\u000D\\u000A\\u0009\\u000B\\u000C\\u0008",
            ),
            (
                r"<script>and this</script>",
                "\\u003Cscript\\u003Eand this\\u003C/script\\u003E",
            ),
            (
                "paragraph separator:\u2029and line separator:\u2028",
                "paragraph separator:\\u2029and line separator:\\u2028",
            ),
            ("`", "\\u0060"),
        )
        for value, output in items:
            with self.subTest(value=value, output=output):
                self.check_output(escapejs, value, output)
                self.check_output(escapejs, lazystr(value), output)

    def test_json_script(self):
        tests = (
            # "<", ">" and "&" are quoted inside JSON strings
            (
                (
                    "&<>",
                    '<script id="test_id" type="application/json">'
                    '"\\u0026\\u003C\\u003E"</script>',
                )
            ),
            # "<", ">" and "&" are quoted inside JSON objects
            (
                {"a": "<script>test&ing</script>"},
                '<script id="test_id" type="application/json">'
                '{"a": "\\u003Cscript\\u003Etest\\u0026ing\\u003C/script\\u003E"}'
                "</script>",
            ),
            # Lazy strings are quoted
            (
                lazystr("&<>"),
                '<script id="test_id" type="application/json">"\\u0026\\u003C\\u003E"'
                "</script>",
            ),
            (
                {"a": lazystr("<script>test&ing</script>")},
                '<script id="test_id" type="application/json">'
                '{"a": "\\u003Cscript\\u003Etest\\u0026ing\\u003C/script\\u003E"}'
                "</script>",
            ),
        )
        for arg, expected in tests:
            with self.subTest(arg=arg):
                self.assertEqual(json_script(arg, "test_id"), expected)

    def test_json_script_custom_encoder(self):
        """

        Tests the json_script function with a custom JSON encoder.

        The function is expected to generate a JSON script tag using the custom encoder.
        The test verifies that the output matches the expected HTML format,
        with the custom-encoded JSON data wrapped in a script tag of type application/json.

        """
        class CustomDjangoJSONEncoder(DjangoJSONEncoder):
            def encode(self, o):
                return '{"hello": "world"}'

        self.assertHTMLEqual(
            json_script({}, encoder=CustomDjangoJSONEncoder),
            '<script type="application/json">{"hello": "world"}</script>',
        )

    def test_json_script_without_id(self):
        self.assertHTMLEqual(
            json_script({"key": "value"}),
            '<script type="application/json">{"key": "value"}</script>',
        )

    def test_smart_urlquote(self):
        """
        ```def test_smart_urlquote(self):
            \"\"\"
            Tests the smart_urlquote function with various URLs, ensuring that it correctly 
            encodes special characters in the URL path and query parameters.

            This test case covers a range of scenarios, including:
            - IDsN (Internationalized Domain Names)
            - non-ASCII characters in the URL path
            - special characters in query parameters
            - URLs with multiple query parameters
            - URLs with ampersands (&) and other special characters
            - edge cases such as empty query parameters and special characters in the domain name
            \"\"\"
        ```
        """
        items = (
            ("http://öäü.com/", "http://xn--4ca9at.com/"),
            ("http://öäü.com/öäü/", "http://xn--4ca9at.com/%C3%B6%C3%A4%C3%BC/"),
            # Everything unsafe is quoted, !*'();:@&=+$,/?#[]~ is considered
            # safe as per RFC.
            (
                "http://example.com/path/öäü/",
                "http://example.com/path/%C3%B6%C3%A4%C3%BC/",
            ),
            ("http://example.com/%C3%B6/ä/", "http://example.com/%C3%B6/%C3%A4/"),
            ("http://example.com/?x=1&y=2+3&z=", "http://example.com/?x=1&y=2+3&z="),
            ("http://example.com/?x=<>\"'", "http://example.com/?x=%3C%3E%22%27"),
            (
                "http://example.com/?q=http://example.com/?x=1%26q=django",
                "http://example.com/?q=http%3A%2F%2Fexample.com%2F%3Fx%3D1%26q%3D"
                "django",
            ),
            (
                "http://example.com/?q=http%3A%2F%2Fexample.com%2F%3Fx%3D1%26q%3D"
                "django",
                "http://example.com/?q=http%3A%2F%2Fexample.com%2F%3Fx%3D1%26q%3D"
                "django",
            ),
            ("http://.www.f oo.bar/", "http://.www.f%20oo.bar/"),
        )
        # IDNs are properly quoted
        for value, output in items:
            with self.subTest(value=value, output=output):
                self.assertEqual(smart_urlquote(value), output)

    def test_conditional_escape(self):
        """
        Conditionally escapes HTML strings to prevent XSS attacks.

        This function checks if the input string is marked as safe and returns it unchanged.
        If the string is not marked as safe, it replaces special characters with their HTML entity equivalents.

        The function handles not only raw strings but also string-like objects (e.g. lazy strings).

        :returns: The escaped string or the original string if it is marked as safe.
        """
        s = "<h1>interop</h1>"
        self.assertEqual(conditional_escape(s), "&lt;h1&gt;interop&lt;/h1&gt;")
        self.assertEqual(conditional_escape(mark_safe(s)), s)
        self.assertEqual(conditional_escape(lazystr(mark_safe(s))), s)

    def test_html_safe(self):
        @html_safe
        """

        Tests that the html_safe decorator correctly marks a class and its instances as HTML safe.

        The html_safe decorator is expected to add an __html__ method to the class and its instances,
        which should return the same output as the __str__ method. This test verifies that the
        decorator is working correctly by checking for the presence of the __html__ attribute on
        both the class and an instance of the class, and by comparing the output of the __str__
        and __html__ methods.

        """
        class HtmlClass:
            def __str__(self):
                return "<h1>I'm a html class!</h1>"

        html_obj = HtmlClass()
        self.assertTrue(hasattr(HtmlClass, "__html__"))
        self.assertTrue(hasattr(html_obj, "__html__"))
        self.assertEqual(str(html_obj), html_obj.__html__())

    def test_html_safe_subclass(self):
        class BaseClass:
            def __html__(self):
                # defines __html__ on its own
                return "some html content"

            def __str__(self):
                return "some non html content"

        @html_safe
        class Subclass(BaseClass):
            def __str__(self):
                # overrides __str__ and is marked as html_safe
                return "some html safe content"

        subclass_obj = Subclass()
        self.assertEqual(str(subclass_obj), subclass_obj.__html__())

    def test_html_safe_defines_html_error(self):
        """
        Tests that applying the @html_safe decorator to a class that defines its own __html__() method raises a ValueError, as @html_safe is intended for strings that are already safe for HTML display and should not be used to override custom HTML rendering behavior.
        """
        msg = "can't apply @html_safe to HtmlClass because it defines __html__()."
        with self.assertRaisesMessage(ValueError, msg):

            @html_safe
            class HtmlClass:
                def __html__(self):
                    return "<h1>I'm a html class!</h1>"

    def test_html_safe_doesnt_define_str(self):
        """
        Tests that attempting to apply the @html_safe decorator to a class that does not define the __str__() method raises a ValueError.

        The @html_safe decorator is intended to mark a class as being safe for use in HTML contexts, implying that its string representation is properly escaped.
        However, if the class does not define how to convert itself to a string, it cannot be marked as HTML-safe.

        This test ensures that the @html_safe decorator correctly detects and raises an error when attempting to decorate such a class, providing a helpful error message to inform the developer of the issue.
        """
        msg = "can't apply @html_safe to HtmlClass because it doesn't define __str__()."
        with self.assertRaisesMessage(ValueError, msg):

            @html_safe
            class HtmlClass:
                pass

    def test_urlize(self):
        """
        Tests the functionality of the urlize function.

        This test case verifies that the urlize function correctly converts plain text URLs 
        and email addresses into HTML hyperlinks, while also properly handling special characters. 

        Several test scenarios are covered, including URLs with query parameters and email addresses. 

        The test ensures that the output of the urlize function matches the expected HTML 
        hyperlinks for each test case, helping to guarantee the correctness and reliability of the function.
        """
        tests = (
            (
                "Search for google.com/?q=! and see.",
                'Search for <a href="http://google.com/?q=">google.com/?q=</a>! and '
                "see.",
            ),
            (
                "Search for google.com/?q=1&lt! and see.",
                'Search for <a href="http://google.com/?q=1%3C">google.com/?q=1&lt'
                "</a>! and see.",
            ),
            (
                lazystr("Search for google.com/?q=!"),
                'Search for <a href="http://google.com/?q=">google.com/?q=</a>!',
            ),
            ("foo@example.com", '<a href="mailto:foo@example.com">foo@example.com</a>'),
        )
        for value, output in tests:
            with self.subTest(value=value):
                self.assertEqual(urlize(value), output)

    def test_urlize_unchanged_inputs(self):
        """

        Test that urlize function does not modify inputs that do not contain valid URLs.

        The function tests a variety of input strings, including very long strings containing random characters, punctuation, and special cases like usernames, domain names, and localhost.
        It checks that the output of the urlize function is identical to the input, ensuring that the function does not introduce any changes to the input strings.
        The test cases cover edge cases and boundary conditions, providing assurance that the urlize function behaves as expected and does not modify inputs unnecessarily.

        """
        tests = (
            ("a" + "@a" * 50000) + "a",  # simple_email_re catastrophic test
            ("a" + "." * 1000000) + "a",  # trailing_punctuation catastrophic test
            "foo@",
            "@foo.com",
            "foo@.example.com",
            "foo@localhost",
            "foo@localhost.",
            # trim_punctuation catastrophic tests
            "(" * 100_000 + ":" + ")" * 100_000,
            "(" * 100_000 + "&:" + ")" * 100_000,
            "([" * 100_000 + ":" + "])" * 100_000,
            "[(" * 100_000 + ":" + ")]" * 100_000,
            "([[" * 100_000 + ":" + "]])" * 100_000,
            "&:" + ";" * 100_000,
        )
        for value in tests:
            with self.subTest(value=value):
                self.assertEqual(urlize(value), value)
