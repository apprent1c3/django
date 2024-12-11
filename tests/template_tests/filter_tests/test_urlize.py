from django.template.defaultfilters import urlize
from django.test import SimpleTestCase
from django.utils.functional import lazy
from django.utils.safestring import mark_safe

from ..utils import setup


class UrlizeTests(SimpleTestCase):
    @setup(
        {
            "urlize01": (
                "{% autoescape off %}{{ a|urlize }} {{ b|urlize }}{% endautoescape %}"
            )
        }
    )
    def test_urlize01(self):
        """
        Tests the urlize template filter function.

        This function verifies that the urlize filter correctly converts URLs into HTML links,
        including proper handling of special characters and ampersand encoding.
        It also checks that the filter works correctly when used in conjunction with the mark_safe function.

        The test includes two different URL strings: one with special characters and one with HTML entities,
        to ensure that the urlize filter handles these cases correctly and produces the expected output.
        """
        output = self.engine.render_to_string(
            "urlize01",
            {
                "a": "http://example.com/?x=&y=",
                "b": mark_safe("http://example.com?x=&amp;y=&lt;2&gt;"),
            },
        )
        self.assertEqual(
            output,
            '<a href="http://example.com/?x=&amp;y=" rel="nofollow">'
            "http://example.com/?x=&y=</a> "
            '<a href="http://example.com?x=&amp;y=%3C2%3E" rel="nofollow">'
            "http://example.com?x=&amp;y=&lt;2&gt;</a>",
        )

    @setup({"urlize02": "{{ a|urlize }} {{ b|urlize }}"})
    def test_urlize02(self):
        """

        Test the urlize filter to ensure it correctly converts URLs into HTML links.

        The urlize filter is expected to handle various URL edge cases, including query strings and HTML entities.

        It should also properly handle URLs wrapped in mark_safe, to avoid double escaping.

        """
        output = self.engine.render_to_string(
            "urlize02",
            {
                "a": "http://example.com/?x=&y=",
                "b": mark_safe("http://example.com?x=&amp;y="),
            },
        )
        self.assertEqual(
            output,
            '<a href="http://example.com/?x=&amp;y=" rel="nofollow">'
            "http://example.com/?x=&amp;y=</a> "
            '<a href="http://example.com?x=&amp;y=" rel="nofollow">'
            "http://example.com?x=&amp;y=</a>",
        )

    @setup({"urlize03": "{% autoescape off %}{{ a|urlize }}{% endautoescape %}"})
    def test_urlize03(self):
        """
        Tests the urlize template filter with autoescape disabled.

        Verifies that the urlize filter does not alter the input when autoescape is
        disabled and the input contains HTML entities. The test checks if the rendered
        output matches the expected string, ensuring that the filter does not modify
        the input in this specific scenario.

        The test case specifically examines the behavior when the input contains an
        ampersand (&) character, which is a special character in HTML and may be
        affected by the urlize filter's behavior.

        The expected result is that the output remains unchanged from the input, with
        the ampersand character preserved as an HTML entity (&amp;).
        """
        output = self.engine.render_to_string("urlize03", {"a": mark_safe("a &amp; b")})
        self.assertEqual(output, "a &amp; b")

    @setup({"urlize04": "{{ a|urlize }}"})
    def test_urlize04(self):
        """
        Tests the urlize filter when passed a string with HTML entities.

        Verifies that the urlize filter does not alter the input string when it contains
        HTML entities, ensuring the output remains unchanged. This test case checks the
        filter's behavior with a specific input containing ampersands (&) to ensure it
        produces the expected result without modifying the original string.
        """
        output = self.engine.render_to_string("urlize04", {"a": mark_safe("a &amp; b")})
        self.assertEqual(output, "a &amp; b")

    # This will lead to a nonsense result, but at least it won't be
    # exploitable for XSS purposes when auto-escaping is on.
    @setup({"urlize05": "{% autoescape off %}{{ a|urlize }}{% endautoescape %}"})
    def test_urlize05(self):
        """

        Tests the urlize filter's behavior with autoescape disabled.

        This test case ensures that the urlize filter does not escape HTML entities when
        autoescape is turned off, allowing potentially malicious scripts to be injected
        into the output. The test renders a template with the urlize filter and verifies
        that the output matches the expected result, which in this case is the original
        input string containing a script tag.

        """
        output = self.engine.render_to_string(
            "urlize05", {"a": "<script>alert('foo')</script>"}
        )
        self.assertEqual(output, "<script>alert('foo')</script>")

    @setup({"urlize06": "{{ a|urlize }}"})
    def test_urlize06(self):
        output = self.engine.render_to_string(
            "urlize06", {"a": "<script>alert('foo')</script>"}
        )
        self.assertEqual(output, "&lt;script&gt;alert(&#x27;foo&#x27;)&lt;/script&gt;")

    # mailto: testing for urlize
    @setup({"urlize07": "{{ a|urlize }}"})
    def test_urlize07(self):
        """
        Tests the urlize engine functionality by rendering a template with an email address and verifying the output contains a correctly formatted HTML mailto link.
        """
        output = self.engine.render_to_string(
            "urlize07", {"a": "Email me at me@example.com"}
        )
        self.assertEqual(
            output,
            'Email me at <a href="mailto:me@example.com">me@example.com</a>',
        )

    @setup({"urlize08": "{{ a|urlize }}"})
    def test_urlize08(self):
        output = self.engine.render_to_string(
            "urlize08", {"a": "Email me at <me@example.com>"}
        )
        self.assertEqual(
            output,
            'Email me at &lt;<a href="mailto:me@example.com">me@example.com</a>&gt;',
        )

    @setup({"urlize09": "{% autoescape off %}{{ a|urlize }}{% endautoescape %}"})
    def test_urlize09(self):
        output = self.engine.render_to_string(
            "urlize09", {"a": "http://example.com/?x=&amp;y=&lt;2&gt;"}
        )
        self.assertEqual(
            output,
            '<a href="http://example.com/?x=&amp;y=%3C2%3E" rel="nofollow">'
            "http://example.com/?x=&amp;y=&lt;2&gt;</a>",
        )


class FunctionTests(SimpleTestCase):
    def test_urls(self):
        """
        Tests the functionality of the urlize function to ensure it correctly converts URLs into HTML links.

        The function verifies that the urlize function handles various URL formats, including those with and without the \"http://\" prefix, as well as those with and without a trailing slash. 

        It checks that the resulting HTML links have the correct URL and text, and that they include the \"rel='nofollow'\" attribute to prevent search engines from following the links.
        """
        self.assertEqual(
            urlize("http://google.com"),
            '<a href="http://google.com" rel="nofollow">http://google.com</a>',
        )
        self.assertEqual(
            urlize("http://google.com/"),
            '<a href="http://google.com/" rel="nofollow">http://google.com/</a>',
        )
        self.assertEqual(
            urlize("www.google.com"),
            '<a href="http://www.google.com" rel="nofollow">www.google.com</a>',
        )
        self.assertEqual(
            urlize("djangoproject.org"),
            '<a href="http://djangoproject.org" rel="nofollow">djangoproject.org</a>',
        )
        self.assertEqual(
            urlize("djangoproject.org/"),
            '<a href="http://djangoproject.org/" rel="nofollow">djangoproject.org/</a>',
        )

    def test_url_split_chars(self):
        # Quotes (single and double) and angle brackets shouldn't be considered
        # part of URLs.
        self.assertEqual(
            urlize('www.server.com"abc'),
            '<a href="http://www.server.com" rel="nofollow">www.server.com</a>&quot;'
            "abc",
        )
        self.assertEqual(
            urlize("www.server.com'abc"),
            '<a href="http://www.server.com" rel="nofollow">www.server.com</a>&#x27;'
            "abc",
        )
        self.assertEqual(
            urlize("www.server.com<abc"),
            '<a href="http://www.server.com" rel="nofollow">www.server.com</a>&lt;abc',
        )
        self.assertEqual(
            urlize("www.server.com>abc"),
            '<a href="http://www.server.com" rel="nofollow">www.server.com</a>&gt;abc',
        )

    def test_email(self):
        self.assertEqual(
            urlize("info@djangoproject.org"),
            '<a href="mailto:info@djangoproject.org">info@djangoproject.org</a>',
        )

    def test_word_with_dot(self):
        self.assertEqual(urlize("some.organization"), "some.organization")

    def test_https(self):
        self.assertEqual(
            urlize("https://google.com"),
            '<a href="https://google.com" rel="nofollow">https://google.com</a>',
        )

    def test_quoting(self):
        """
        #9655 - Check urlize doesn't overquote already quoted urls. The
        teststring is the urlquoted version of 'http://hi.baidu.com/重新开始'
        """
        self.assertEqual(
            urlize("http://hi.baidu.com/%E9%87%8D%E6%96%B0%E5%BC%80%E5%A7%8B"),
            '<a href="http://hi.baidu.com/%E9%87%8D%E6%96%B0%E5%BC%80%E5%A7%8B" '
            'rel="nofollow">http://hi.baidu.com/%E9%87%8D%E6%96%B0%E5%BC%80%E5%A7%8B'
            "</a>",
        )

    def test_urlencoded(self):
        """

        Tests the urlize function to ensure it properly converts URLs into HTML links.

        The function is expected to correctly handle URLs that are already encoded, 
        appending 'http://' to URLs that do not have a scheme, and maintaining the 
        encoding of special characters within the URL.

        The test cases cover various scenarios, including URLs with special characters 
        and those that are already encoded. The expected output is an HTML anchor tag 
        with the URL as the href attribute and the rel attribute set to 'nofollow'.

        """
        self.assertEqual(
            urlize("www.mystore.com/30%OffCoupons!"),
            '<a href="http://www.mystore.com/30%25OffCoupons" rel="nofollow">'
            "www.mystore.com/30%OffCoupons</a>!",
        )
        self.assertEqual(
            urlize("https://en.wikipedia.org/wiki/Caf%C3%A9"),
            '<a href="https://en.wikipedia.org/wiki/Caf%C3%A9" rel="nofollow">'
            "https://en.wikipedia.org/wiki/Caf%C3%A9</a>",
        )

    def test_unicode(self):
        self.assertEqual(
            urlize("https://en.wikipedia.org/wiki/Café"),
            '<a href="https://en.wikipedia.org/wiki/Caf%C3%A9" rel="nofollow">'
            "https://en.wikipedia.org/wiki/Café</a>",
        )

    def test_parenthesis(self):
        """
        #11911 - Check urlize keeps balanced parentheses
        """
        self.assertEqual(
            urlize("https://en.wikipedia.org/wiki/Django_(web_framework)"),
            '<a href="https://en.wikipedia.org/wiki/Django_(web_framework)" '
            'rel="nofollow">https://en.wikipedia.org/wiki/Django_(web_framework)</a>',
        )
        self.assertEqual(
            urlize("(see https://en.wikipedia.org/wiki/Django_(web_framework))"),
            '(see <a href="https://en.wikipedia.org/wiki/Django_(web_framework)" '
            'rel="nofollow">https://en.wikipedia.org/wiki/Django_(web_framework)</a>)',
        )

    def test_nofollow(self):
        """
        #12183 - Check urlize adds nofollow properly - see #12183
        """
        self.assertEqual(
            urlize("foo@bar.com or www.bar.com"),
            '<a href="mailto:foo@bar.com">foo@bar.com</a> or '
            '<a href="http://www.bar.com" rel="nofollow">www.bar.com</a>',
        )

    def test_idn(self):
        """
        #13704 - Check urlize handles IDN correctly
        """
        self.assertEqual(
            urlize("http://c✶.ws"),
            '<a href="http://xn--c-lgq.ws" rel="nofollow">http://c✶.ws</a>',
        )
        self.assertEqual(
            urlize("www.c✶.ws"),
            '<a href="http://www.xn--c-lgq.ws" rel="nofollow">www.c✶.ws</a>',
        )
        self.assertEqual(
            urlize("c✶.org"), '<a href="http://xn--c-lgq.org" rel="nofollow">c✶.org</a>'
        )
        self.assertEqual(
            urlize("info@c✶.org"), '<a href="mailto:info@xn--c-lgq.org">info@c✶.org</a>'
        )

    def test_malformed(self):
        """
        #16395 - Check urlize doesn't highlight malformed URIs
        """
        self.assertEqual(urlize("http:///www.google.com"), "http:///www.google.com")
        self.assertEqual(urlize("http://.google.com"), "http://.google.com")
        self.assertEqual(urlize("http://@foo.com"), "http://@foo.com")

    def test_tlds(self):
        """
        #16656 - Check urlize accepts more TLDs
        """
        self.assertEqual(
            urlize("usa.gov"), '<a href="http://usa.gov" rel="nofollow">usa.gov</a>'
        )

    def test_invalid_email(self):
        """
        #17592 - Check urlize don't crash on invalid email with dot-starting
        domain
        """
        self.assertEqual(urlize("email@.stream.ru"), "email@.stream.ru")

    def test_uppercase(self):
        """
        #18071 - Check urlize accepts uppercased URL schemes
        """
        self.assertEqual(
            urlize("HTTPS://github.com/"),
            '<a href="https://github.com/" rel="nofollow">HTTPS://github.com/</a>',
        )

    def test_trailing_period(self):
        """
        #18644 - Check urlize trims trailing period when followed by parenthesis
        """
        self.assertEqual(
            urlize("(Go to http://www.example.com/foo.)"),
            '(Go to <a href="http://www.example.com/foo" rel="nofollow">'
            "http://www.example.com/foo</a>.)",
        )

    def test_trailing_multiple_punctuation(self):
        """
        Tests the urlize function to ensure it correctly handles URLs followed by multiple punctuation marks.

        The function should verify that the urlize function can identify and replace URLs 
        in text with their corresponding HTML anchor tags, while preserving any trailing 
        punctuation marks. This helps to maintain the original formatting and readability 
        of the text, ensuring that URLs are properly hyperlinked without disrupting the 
        surrounding punctuation.
        """
        self.assertEqual(
            urlize("A test http://testing.com/example.."),
            'A test <a href="http://testing.com/example" rel="nofollow">'
            "http://testing.com/example</a>..",
        )
        self.assertEqual(
            urlize("A test http://testing.com/example!!"),
            'A test <a href="http://testing.com/example" rel="nofollow">'
            "http://testing.com/example</a>!!",
        )
        self.assertEqual(
            urlize("A test http://testing.com/example!!!"),
            'A test <a href="http://testing.com/example" rel="nofollow">'
            "http://testing.com/example</a>!!!",
        )
        self.assertEqual(
            urlize('A test http://testing.com/example.,:;)"!'),
            'A test <a href="http://testing.com/example" rel="nofollow">'
            "http://testing.com/example</a>.,:;)&quot;!",
        )

    def test_trailing_semicolon(self):
        self.assertEqual(
            urlize("http://example.com?x=&amp;", autoescape=False),
            '<a href="http://example.com?x=" rel="nofollow">'
            "http://example.com?x=&amp;</a>",
        )
        self.assertEqual(
            urlize("http://example.com?x=&amp;;", autoescape=False),
            '<a href="http://example.com?x=" rel="nofollow">'
            "http://example.com?x=&amp;</a>;",
        )
        self.assertEqual(
            urlize("http://example.com?x=&amp;;;", autoescape=False),
            '<a href="http://example.com?x=" rel="nofollow">'
            "http://example.com?x=&amp;</a>;;",
        )

    def test_brackets(self):
        """
        #19070 - Check urlize handles brackets properly
        """
        self.assertEqual(
            urlize("[see www.example.com]"),
            '[see <a href="http://www.example.com" rel="nofollow">www.example.com</a>]',
        )
        self.assertEqual(
            urlize("see test[at[example.com"),
            'see <a href="http://test[at[example.com" rel="nofollow">'
            "test[at[example.com</a>",
        )
        self.assertEqual(
            urlize("[http://168.192.0.1](http://168.192.0.1)"),
            '[<a href="http://168.192.0.1](http://168.192.0.1)" rel="nofollow">'
            "http://168.192.0.1](http://168.192.0.1)</a>",
        )

    def test_wrapping_characters(self):
        """

        Test that the urlize function correctly wraps URLs with various character pairs.

        The test checks that the function replaces input wrapping characters with their corresponding output HTML entities, 
        while properly formatting the URL as a link with a \"nofollow\" attribute.

        The test covers several common wrapping character pairs, including parentheses, angle brackets, square brackets, 
        double quotes, and single quotes. For each pair, it verifies that the output is correctly formatted and that 
        the URL is properly linked.

        """
        wrapping_chars = (
            ("()", ("(", ")")),
            ("<>", ("&lt;", "&gt;")),
            ("[]", ("[", "]")),
            ('""', ("&quot;", "&quot;")),
            ("''", ("&#x27;", "&#x27;")),
        )
        for wrapping_in, (start_out, end_out) in wrapping_chars:
            with self.subTest(wrapping_in=wrapping_in):
                start_in, end_in = wrapping_in
                self.assertEqual(
                    urlize(start_in + "https://www.example.org/" + end_in),
                    f'{start_out}<a href="https://www.example.org/" rel="nofollow">'
                    f"https://www.example.org/</a>{end_out}",
                )

    def test_ipv4(self):
        self.assertEqual(
            urlize("http://192.168.0.15/api/9"),
            '<a href="http://192.168.0.15/api/9" rel="nofollow">'
            "http://192.168.0.15/api/9</a>",
        )

    def test_ipv6(self):
        self.assertEqual(
            urlize("http://[2001:db8:cafe::2]/api/9"),
            '<a href="http://[2001:db8:cafe::2]/api/9" rel="nofollow">'
            "http://[2001:db8:cafe::2]/api/9</a>",
        )

    def test_quotation_marks(self):
        """
        #20364 - Check urlize correctly include quotation marks in links
        """
        self.assertEqual(
            urlize('before "hi@example.com" afterward', autoescape=False),
            'before "<a href="mailto:hi@example.com">hi@example.com</a>" afterward',
        )
        self.assertEqual(
            urlize('before hi@example.com" afterward', autoescape=False),
            'before <a href="mailto:hi@example.com">hi@example.com</a>" afterward',
        )
        self.assertEqual(
            urlize('before "hi@example.com afterward', autoescape=False),
            'before "<a href="mailto:hi@example.com">hi@example.com</a> afterward',
        )
        self.assertEqual(
            urlize("before 'hi@example.com' afterward", autoescape=False),
            "before '<a href=\"mailto:hi@example.com\">hi@example.com</a>' afterward",
        )
        self.assertEqual(
            urlize("before hi@example.com' afterward", autoescape=False),
            'before <a href="mailto:hi@example.com">hi@example.com</a>\' afterward',
        )
        self.assertEqual(
            urlize("before 'hi@example.com afterward", autoescape=False),
            'before \'<a href="mailto:hi@example.com">hi@example.com</a> afterward',
        )

    def test_quote_commas(self):
        """
        #20364 - Check urlize copes with commas following URLs in quotes
        """
        self.assertEqual(
            urlize(
                'Email us at "hi@example.com", or phone us at +xx.yy', autoescape=False
            ),
            'Email us at "<a href="mailto:hi@example.com">hi@example.com</a>", or '
            "phone us at +xx.yy",
        )

    def test_exclamation_marks(self):
        """
        #23715 - Check urlize correctly handles exclamation marks after TLDs
        or query string
        """
        self.assertEqual(
            urlize("Go to djangoproject.com! and enjoy."),
            'Go to <a href="http://djangoproject.com" rel="nofollow">djangoproject.com'
            "</a>! and enjoy.",
        )
        self.assertEqual(
            urlize("Search for google.com/?q=! and see."),
            'Search for <a href="http://google.com/?q=" rel="nofollow">google.com/?q='
            "</a>! and see.",
        )
        self.assertEqual(
            urlize("Search for google.com/?q=dj!`? and see."),
            'Search for <a href="http://google.com/?q=dj%21%60%3F" rel="nofollow">'
            "google.com/?q=dj!`?</a> and see.",
        )
        self.assertEqual(
            urlize("Search for google.com/?q=dj!`?! and see."),
            'Search for <a href="http://google.com/?q=dj%21%60%3F" rel="nofollow">'
            "google.com/?q=dj!`?</a>! and see.",
        )

    def test_non_string_input(self):
        self.assertEqual(urlize(123), "123")

    def test_autoescape(self):
        self.assertEqual(
            urlize('foo<a href=" google.com ">bar</a>buz'),
            'foo&lt;a href=&quot; <a href="http://google.com" rel="nofollow">google.com'
            "</a> &quot;&gt;bar&lt;/a&gt;buz",
        )

    def test_autoescape_off(self):
        self.assertEqual(
            urlize('foo<a href=" google.com ">bar</a>buz', autoescape=False),
            'foo<a href=" <a href="http://google.com" rel="nofollow">google.com</a> ">'
            "bar</a>buz",
        )

    def test_lazystring(self):
        """
        のかrecommend adding a docstring to the function is over, the actual function docstring is below:
        -tested test_lazystring method.
         Tests the lazystring functionality by prepending 'www.' to a given url and 
         then urlizing it, verifying that the output is correctly formatted as an HTML link.

         The test case checks if the output of the urlize function, applied to a lazystring 
         that prepends 'www.' to 'google.com', matches the expected HTML link format.

         The method ensures that the lazystring is properly evaluated and that the resulting 
         url is correctly formatted with the 'http://' protocol and 'nofollow' rel attribute.
        """
        prepend_www = lazy(lambda url: "www." + url, str)
        self.assertEqual(
            urlize(prepend_www("google.com")),
            '<a href="http://www.google.com" rel="nofollow">www.google.com</a>',
        )
