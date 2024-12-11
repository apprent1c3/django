from django.template.defaultfilters import urlizetrunc
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from ..utils import setup


class UrlizetruncTests(SimpleTestCase):
    @setup(
        {
            "urlizetrunc01": (
                '{% autoescape off %}{{ a|urlizetrunc:"8" }} {{ b|urlizetrunc:"8" }}'
                "{% endautoescape %}"
            )
        }
    )
    def test_urlizetrunc01(self):
        """
        Test the urlizetrunc template filter, which truncates and converts URLs to HTML links.

        This test case checks the functionality of the urlizetrunc filter with unsafe and safe input strings.
        It verifies that the filter correctly truncates the URLs to a specified length, converts them to HTML links,
        and applies the nofollow attribute. The test also ensures that the filter handles escaped characters correctly.
        """
        output = self.engine.render_to_string(
            "urlizetrunc01",
            {
                "a": '"Unsafe" http://example.com/x=&y=',
                "b": mark_safe("&quot;Safe&quot; http://example.com?x=&amp;y="),
            },
        )
        self.assertEqual(
            output,
            '"Unsafe" '
            '<a href="http://example.com/x=&amp;y=" rel="nofollow">http://…</a> '
            "&quot;Safe&quot; "
            '<a href="http://example.com?x=&amp;y=" rel="nofollow">http://…</a>',
        )

    @setup({"urlizetrunc02": '{{ a|urlizetrunc:"8" }} {{ b|urlizetrunc:"8" }}'})
    def test_urlizetrunc02(self):
        """
        )..Test the urlizetrunc filter with unsafe and safe input.

        This test case verifies that the urlizetrunc filter correctly handles both unsafe and safe strings, truncating URLs to a specified length and wrapping them in an anchor tag with a rel=\"nofollow\" attribute. The filter is applied to two inputs: one containing an unsafe string with special characters, and another containing a safe string with HTML entities. The test checks that the output matches the expected rendering, ensuring that the filter behaves as expected in different scenarios.
        """
        output = self.engine.render_to_string(
            "urlizetrunc02",
            {
                "a": '"Unsafe" http://example.com/x=&y=',
                "b": mark_safe("&quot;Safe&quot; http://example.com?x=&amp;y="),
            },
        )
        self.assertEqual(
            output,
            '&quot;Unsafe&quot; <a href="http://example.com/x=&amp;y=" rel="nofollow">'
            "http://…</a> "
            '&quot;Safe&quot; <a href="http://example.com?x=&amp;y=" rel="nofollow">'
            "http://…</a>",
        )


class FunctionTests(SimpleTestCase):
    def test_truncate(self):
        """
        Tests the urlizetrunc function to ensure it correctly truncates a given URI.

        The function checks the urlizetrunc function's behavior at different truncation lengths, 
        verifying that it correctly truncates the URI while maintaining the rel=\"nofollow\" attribute 
        and wrapping the result in an HTML anchor tag.

        The test cases cover scenarios where the truncation length is equal to, less than, 
        and significantly less than the original length of the URI, ensuring the function 
        produces the expected output in each case.
        """
        uri = "http://31characteruri.com/test/"
        self.assertEqual(len(uri), 31)

        self.assertEqual(
            urlizetrunc(uri, 31),
            '<a href="http://31characteruri.com/test/" rel="nofollow">'
            "http://31characteruri.com/test/</a>",
        )

        self.assertEqual(
            urlizetrunc(uri, 30),
            '<a href="http://31characteruri.com/test/" rel="nofollow">'
            "http://31characteruri.com/tes…</a>",
        )

        self.assertEqual(
            urlizetrunc(uri, 1),
            '<a href="http://31characteruri.com/test/" rel="nofollow">…</a>',
        )

    def test_overtruncate(self):
        self.assertEqual(
            urlizetrunc("http://short.com/", 20),
            '<a href="http://short.com/" rel="nofollow">http://short.com/</a>',
        )

    def test_query_string(self):
        self.assertEqual(
            urlizetrunc(
                "http://www.google.co.uk/search?hl=en&q=some+long+url&btnG=Search"
                "&meta=",
                20,
            ),
            '<a href="http://www.google.co.uk/search?hl=en&amp;q=some+long+url&amp;'
            'btnG=Search&amp;meta=" rel="nofollow">http://www.google.c…</a>',
        )

    def test_non_string_input(self):
        self.assertEqual(urlizetrunc(123, 1), "123")

    def test_autoescape(self):
        self.assertEqual(
            urlizetrunc('foo<a href=" google.com ">bar</a>buz', 10),
            'foo&lt;a href=&quot; <a href="http://google.com" rel="nofollow">google.com'
            "</a> &quot;&gt;bar&lt;/a&gt;buz",
        )

    def test_autoescape_off(self):
        self.assertEqual(
            urlizetrunc('foo<a href=" google.com ">bar</a>buz', 9, autoescape=False),
            'foo<a href=" <a href="http://google.com" rel="nofollow">google.c…</a> ">'
            "bar</a>buz",
        )
