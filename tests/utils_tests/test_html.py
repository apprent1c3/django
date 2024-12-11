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
        Tests the HTML escaping functionality of the `escape` function.

        This function verifies that special HTML characters are correctly replaced with 
        their corresponding HTML entities. The tested characters include ampersand (&),
        less-than sign (<), greater-than sign (>), quotation mark (\"), and single 
        quotation mark (').

        The function also checks that the `escape` function works correctly with 
        various input patterns, including the special characters alone, surrounded by 
        other text, and repeated. Additionally, it tests the function's behavior when 
        passed a `lazystr` object instead of a regular string.

        The expected output for each test case is compared with the actual output of 
        the `escape` function to ensure that it produces the correct HTML-escaped 
        strings.
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
        """
        Tests that the format_html function returns the correct HTML string when called without passing any arguments or keyword arguments.

        The test checks that a deprecation warning is raised when format_html is called without arguments or keyword arguments, as this behavior is deprecated and will be removed in Django 6.0.

        The test case uses a simple HTML string containing a name, and verifies that the formatted HTML string matches the expected output.
        """
        msg = "Calling format_html() without passing args or kwargs is deprecated."
        # RemovedInDjango60Warning: when the deprecation ends, replace with:
        # msg = "args or kwargs must be provided."
        # with self.assertRaisesMessage(ValueError, msg):
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            name = "Adam"
            self.assertEqual(format_html(f"<i>{name}</i>"), "<i>Adam</i>")

    def test_linebreaks(self):
        """
        测试输语句(linebreaks)处理多种换行符的功能，包括换行（\n）和回车（\r）。 

        该测试案例包括多个具有不同换行符输入及其预期输出的测试场景，并检查linebreaks函数生成的输出与预期输出是否匹配，包括使用lazystr进行包装的输入情况。测试场景涵盖了嵌套换行、单行内的多个换行符以及混合换行符的常见使用方式。
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
        """

        Tests the json_script function to ensure it correctly escapes special characters
        and generates a JSON script tag.

        The function is tested with various inputs, including strings, dictionaries, and lazy strings,
        to verify that the output is a properly formatted JSON script tag with escaped characters.

        The tests cover different scenarios, such as:
        - Escaping special characters in strings
        - Escaping special characters in dictionary values
        - Handling lazy strings

        The test function checks if the output of the json_script function matches the expected result
        for each test case, ensuring the function behaves as expected.

        """
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

        Escapes HTML special characters in a string if it hasn't been marked as safe.

        This function checks if a given string has been marked as safe from HTML escaping,
        and if so, it returns the string unchanged. If the string hasn't been marked as safe,
        it escapes any HTML special characters it contains.

        For example, if a string contains HTML tags like '<h1>', they will be replaced with
        their equivalent HTML entities like '&lt;h1&gt;'. This helps prevent XSS attacks
        by ensuring that user-provided data is properly sanitized before being rendered as HTML.

        """
        s = "<h1>interop</h1>"
        self.assertEqual(conditional_escape(s), "&lt;h1&gt;interop&lt;/h1&gt;")
        self.assertEqual(conditional_escape(mark_safe(s)), s)
        self.assertEqual(conditional_escape(lazystr(mark_safe(s))), s)

    def test_html_safe(self):
        @html_safe
        """

        Tests that the @html_safe decorator correctly marks classes and instances as HTML safe.

        This decorator should add an __html__ method to both the class and instances of the class,
        allowing them to be safely rendered as HTML without escaping. The test verifies that the
        decorator has the desired effect by checking for the presence of the __html__ attribute
        and ensuring that its output matches the string representation of the object.

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
        msg = "can't apply @html_safe to HtmlClass because it defines __html__()."
        with self.assertRaisesMessage(ValueError, msg):

            @html_safe
            class HtmlClass:
                def __html__(self):
                    return "<h1>I'm a html class!</h1>"

    def test_html_safe_doesnt_define_str(self):
        msg = "can't apply @html_safe to HtmlClass because it doesn't define __str__()."
        with self.assertRaisesMessage(ValueError, msg):

            @html_safe
            class HtmlClass:
                pass

    def test_urlize(self):
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
