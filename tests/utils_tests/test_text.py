import json
import sys
from unittest.mock import patch

from django.core.exceptions import SuspiciousFileOperation
from django.test import SimpleTestCase
from django.utils import text
from django.utils.functional import lazystr
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy, override

IS_WIDE_BUILD = len("\U0001F4A9") == 1


class TestUtilsText(SimpleTestCase):
    def test_get_text_list(self):
        """
        Return a human-readable string representation of a list.

        This function formats a list of items into a string that is suitable for display to users.
        It handles lists of different lengths and can use different conjunctions (e.g., 'and', 'or') to join the last two items.
        The function also respects the current language and locale settings, so the output may vary depending on the context.

        Parameters:
            items (list): The list of items to format into a string.
            conjunction (str, optional): The conjunction to use to join the last two items in the list. Defaults to 'or'.

        Returns:
            str: A human-readable string representation of the input list.

        """
        self.assertEqual(text.get_text_list(["a", "b", "c", "d"]), "a, b, c or d")
        self.assertEqual(text.get_text_list(["a", "b", "c"], "and"), "a, b and c")
        self.assertEqual(text.get_text_list(["a", "b"], "and"), "a and b")
        self.assertEqual(text.get_text_list(["a"]), "a")
        self.assertEqual(text.get_text_list([]), "")
        with override("ar"):
            self.assertEqual(text.get_text_list(["a", "b", "c"]), "a، b أو c")

    def test_smart_split(self):
        testdata = [
            ('This is "a person" test.', ["This", "is", '"a person"', "test."]),
            ('This is "a person\'s" test.', ["This", "is", '"a person\'s"', "test."]),
            ('This is "a person\\"s" test.', ["This", "is", '"a person\\"s"', "test."]),
            ("\"a 'one", ['"a', "'one"]),
            ("all friends' tests", ["all", "friends'", "tests"]),
            (
                'url search_page words="something else"',
                ["url", "search_page", 'words="something else"'],
            ),
            (
                "url search_page words='something else'",
                ["url", "search_page", "words='something else'"],
            ),
            (
                'url search_page words "something else"',
                ["url", "search_page", "words", '"something else"'],
            ),
            (
                'url search_page words-"something else"',
                ["url", "search_page", 'words-"something else"'],
            ),
            ("url search_page words=hello", ["url", "search_page", "words=hello"]),
            (
                'url search_page words="something else',
                ["url", "search_page", 'words="something', "else"],
            ),
            ("cut:','|cut:' '", ["cut:','|cut:' '"]),
            (lazystr("a b c d"), ["a", "b", "c", "d"]),  # Test for #20231
        ]
        for test, expected in testdata:
            with self.subTest(value=test):
                self.assertEqual(list(text.smart_split(test)), expected)

    def test_truncate_chars(self):
        """
        Tests the truncation of characters in a string using the Truncator class.

        This function verifies that the chars method of the Truncator class correctly truncates a string to the specified length, handling various edge cases such as 
        non-ASCII characters, different truncation lengths, and custom truncation strings. The tests cover a range of scenarios, including:
        - Truncation of strings with and without ASCII characters.
        - Truncation to different lengths, including lengths that result in no truncation.
        - Use of custom truncation strings.
        - Handling of strings with Unicode characters in both NFC and NFD forms.
        - Truncation of strings with special characters.
        - Truncation of strings created from lazy string objects.

        By verifying the correctness of these scenarios, this function ensures that the Truncator class behaves as expected and produces the desired output for character truncation operations.
        """
        truncator = text.Truncator("The quick brown fox jumped over the lazy dog.")
        self.assertEqual(
            "The quick brown fox jumped over the lazy dog.", truncator.chars(100)
        ),
        self.assertEqual("The quick brown fox …", truncator.chars(21))
        self.assertEqual("The quick brown fo.....", truncator.chars(23, "....."))
        self.assertEqual(".....", truncator.chars(4, "....."))

        nfc = text.Truncator("o\xfco\xfco\xfco\xfc")
        nfd = text.Truncator("ou\u0308ou\u0308ou\u0308ou\u0308")
        self.assertEqual("oüoüoüoü", nfc.chars(8))
        self.assertEqual("oüoüoüoü", nfd.chars(8))
        self.assertEqual("oü…", nfc.chars(3))
        self.assertEqual("oü…", nfd.chars(3))

        # Ensure the final length is calculated correctly when there are
        # combining characters with no precomposed form, and that combining
        # characters are not split up.
        truncator = text.Truncator("-B\u030AB\u030A----8")
        self.assertEqual("-B\u030A…", truncator.chars(3))
        self.assertEqual("-B\u030AB\u030A-…", truncator.chars(5))
        self.assertEqual("-B\u030AB\u030A----8", truncator.chars(8))

        # Ensure the length of the end text is correctly calculated when it
        # contains combining characters with no precomposed form.
        truncator = text.Truncator("-----")
        self.assertEqual("---B\u030A", truncator.chars(4, "B\u030A"))
        self.assertEqual("-----", truncator.chars(5, "B\u030A"))

        # Make a best effort to shorten to the desired length, but requesting
        # a length shorter than the ellipsis shouldn't break
        self.assertEqual("...", text.Truncator("asdf").chars(1, truncate="..."))
        # lazy strings are handled correctly
        self.assertEqual(
            text.Truncator(lazystr("The quick brown fox")).chars(10), "The quick…"
        )

    def test_truncate_chars_html(self):
        """
        Truncates an HTML string to a specified number of characters while preserving HTML tags.

        This method ensures that the resulting string is still valid HTML, even when truncated.
        It handles various edge cases, including truncation to a length that is shorter than the remaining text within an HTML tag,
        or when the specified length is less than or equal to zero. 

        Additionally, it allows for a custom truncation string to be specified, which is appended to the end of the truncated text.
        If an empty string is provided as the truncation string, the text will be truncated without any suffix.Xã<|start_header_id|>assistant<|end_header_id|>

        Truncates an HTML string to a specified number of characters while preserving HTML tags.

        This method ensures that the resulting string is still valid HTML, even when truncated.
        It handles various edge cases, including truncation to a length that is shorter than the remaining text within an HTML tag,
        or when the specified length is less than or equal to zero. 

        Additionally, it allows for a custom truncation string to be specified, which is appended to the end of the truncated text.
        If an empty string is provided as the truncation string, the text will be truncated without any suffix.
        """
        truncator = text.Truncator(
            '<p id="par"><strong><em>The quick brown fox jumped over the lazy dog.</em>'
            "</strong></p>"
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox jumped over the lazy dog.</em>'
            "</strong></p>",
            truncator.chars(80, html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox jumped over the lazy dog.</em>'
            "</strong></p>",
            truncator.chars(46, html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox jumped over the lazy dog…</em>'
            "</strong></p>",
            truncator.chars(45, html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick…</em></strong></p>',
            truncator.chars(10, html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>…</em></strong></p>',
            truncator.chars(1, html=True),
        )
        self.assertEqual("", truncator.chars(0, html=True))
        self.assertEqual("", truncator.chars(-1, html=True))
        self.assertEqual(
            '<p id="par"><strong><em>The qu....</em></strong></p>',
            truncator.chars(10, "....", html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick </em></strong></p>',
            truncator.chars(10, "", html=True),
        )
        truncator = text.Truncator("foo</p>")
        self.assertEqual("foo</p>", truncator.chars(5, html=True))

    @patch("django.utils.text.Truncator.MAX_LENGTH_HTML", 10_000)
    def test_truncate_chars_html_size_limit(self):
        """

        Tests the Truncator class's chars method when truncating HTML strings, 
        ensuring it handles HTML size limits correctly and escapes special characters.

        The test covers various edge cases, including:
        - HTML tags with varying lengths
        - HTML tags that exceed the MAX_LENGTH_HTML limit
        - Strings containing special characters that require escaping
        - Valid HTML strings that need to be truncated while preserving their structure

        It verifies that the truncator correctly truncates the input string to the specified length, 
        escapes special characters, and respects HTML tag boundaries.

        """
        max_len = text.Truncator.MAX_LENGTH_HTML
        bigger_len = text.Truncator.MAX_LENGTH_HTML + 1
        valid_html = "<p>Joel is a slug</p>"  # 14 chars
        perf_test_values = [
            ("</a" + "\t" * (max_len - 6) + "//>", "</a>"),
            ("</p" + "\t" * bigger_len + "//>", "</p>"),
            ("&" * bigger_len, ""),
            ("_X<<<<<<<<<<<>", "_X&lt;&lt;&lt;&lt;&lt;&lt;&lt;…"),
            (valid_html * bigger_len, "<p>Joel is a…</p>"),  # 10 chars
        ]
        for value, expected in perf_test_values:
            with self.subTest(value=value):
                truncator = text.Truncator(value)
                self.assertEqual(expected, truncator.chars(10, html=True))

    def test_truncate_chars_html_with_newline_inside_tag(self):
        truncator = text.Truncator(
            '<p>The quick <a href="xyz.html"\n id="mylink">brown fox</a> jumped over '
            "the lazy dog.</p>"
        )
        self.assertEqual(
            '<p>The quick <a href="xyz.html"\n id="mylink">brow…</a></p>',
            truncator.chars(15, html=True),
        )
        self.assertEqual(
            "<p>Th…</p>",
            truncator.chars(3, html=True),
        )

    def test_truncate_chars_html_with_void_elements(self):
        truncator = text.Truncator(
            "<br/>The <hr />quick brown fox jumped over the lazy dog."
        )
        self.assertEqual("<br/>The <hr />quick brown…", truncator.chars(16, html=True))
        truncator = text.Truncator(
            "<br>The <hr/>quick <em>brown fox</em> jumped over the lazy dog."
        )
        self.assertEqual(
            "<br>The <hr/>quick <em>brown…</em>", truncator.chars(16, html=True)
        )
        self.assertEqual("<br>The <hr/>q…", truncator.chars(6, html=True))
        self.assertEqual("<br>The <hr/>…", truncator.chars(5, html=True))
        self.assertEqual("<br>The…", truncator.chars(4, html=True))
        self.assertEqual("<br>Th…", truncator.chars(3, html=True))

    def test_truncate_chars_html_with_html_entities(self):
        """

        Truncates HTML text to a specified character length while preserving HTML entities.

        This function ensures that HTML entities within the text are converted to their
        corresponding characters before truncation, preventing any entity from being
        split across the truncation boundary. The resulting truncated text retains its
        original HTML structure, including tags.

        The truncation process involves removing characters from the end of the text
        until the desired length is reached. If the resulting text is still longer than
        the specified length, an ellipsis is appended to indicate truncation.

        The function can be used to truncate HTML text in various contexts, such as
        displaying summaries of HTML content or generating previews of HTML pages.

        """
        truncator = text.Truncator(
            "<i>Buenos d&iacute;as! &#x00bf;C&oacute;mo est&aacute;?</i>"
        )
        self.assertEqual(
            "<i>Buenos días! ¿Cómo está?</i>",
            truncator.chars(40, html=True),
        )
        self.assertEqual(
            "<i>Buenos días…</i>",
            truncator.chars(12, html=True),
        )
        self.assertEqual(
            "<i>Buenos días! ¿Cómo está…</i>",
            truncator.chars(24, html=True),
        )
        truncator = text.Truncator("<p>I &lt;3 python, what about you?</p>")
        self.assertEqual("<p>I &lt;3 python, wh…</p>", truncator.chars(16, html=True))

    def test_truncate_words(self):
        truncator = text.Truncator("The quick brown fox jumped over the lazy dog.")
        self.assertEqual(
            "The quick brown fox jumped over the lazy dog.", truncator.words(10)
        )
        self.assertEqual("The quick brown fox…", truncator.words(4))
        self.assertEqual("The quick brown fox[snip]", truncator.words(4, "[snip]"))
        # lazy strings are handled correctly
        truncator = text.Truncator(
            lazystr("The quick brown fox jumped over the lazy dog.")
        )
        self.assertEqual("The quick brown fox…", truncator.words(4))
        self.assertEqual("", truncator.words(0))
        self.assertEqual("", truncator.words(-1))

    def test_truncate_html_words(self):
        """

        Tests the truncation of HTML text to a specified number of words.

        This function checks that the Truncator class can correctly truncate HTML text while preserving HTML tags and entities,
        and handling various edge cases such as empty strings, truncated words, and special characters.

        The test cases cover a range of scenarios, including:

        * Truncating text with simple HTML tags (e.g. <p>, <strong>, <em>)
        * Truncating text with more complex HTML tags (e.g. <a>, <hr />, <i>)
        * Handling HTML entities (e.g. &lt;, &gt;, &#x00bf;, &iacute;, &C&oacute;, &est&aacute;)
        * Truncating text with whitespace characters (e.g. spaces, tabs)
        * Truncating text with special characters (e.g. <, >)
        * Handling very long input strings
        * Truncating text with custom ellipsis strings

        The expected output of each test case is compared to the actual output of the Truncator class to ensure that the truncation is correct.

        """
        truncator = text.Truncator(
            '<p id="par"><strong><em>The quick brown fox jumped over the lazy dog.</em>'
            "</strong></p>"
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox jumped over the lazy dog.</em>'
            "</strong></p>",
            truncator.words(10, html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox…</em></strong></p>',
            truncator.words(4, html=True),
        )
        self.assertEqual(
            "",
            truncator.words(0, html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox....</em></strong></p>',
            truncator.words(4, "....", html=True),
        )
        self.assertEqual(
            '<p id="par"><strong><em>The quick brown fox</em></strong></p>',
            truncator.words(4, "", html=True),
        )

        truncator = text.Truncator(
            "<p>The  quick \t brown fox jumped over the lazy dog.</p>"
        )
        self.assertEqual(
            "<p>The quick brown fox…</p>",
            truncator.words(4, html=True),
        )

        # Test with new line inside tag
        truncator = text.Truncator(
            '<p>The quick <a href="xyz.html"\n id="mylink">brown fox</a> jumped over '
            "the lazy dog.</p>"
        )
        self.assertEqual(
            '<p>The quick <a href="xyz.html"\n id="mylink">brown…</a></p>',
            truncator.words(3, html=True),
        )
        self.assertEqual(
            "<p>The…</p>",
            truncator.words(1, html=True),
        )

        # Test self-closing tags
        truncator = text.Truncator(
            "<br/>The <hr />quick brown fox jumped over the lazy dog."
        )
        self.assertEqual("<br/>The <hr />quick brown…", truncator.words(3, html=True))
        truncator = text.Truncator(
            "<br>The <hr/>quick <em>brown fox</em> jumped over the lazy dog."
        )
        self.assertEqual(
            "<br>The <hr/>quick <em>brown…</em>", truncator.words(3, html=True)
        )

        # Test html entities
        truncator = text.Truncator(
            "<i>Buenos d&iacute;as! &#x00bf;C&oacute;mo est&aacute;?</i>"
        )
        self.assertEqual(
            "<i>Buenos días! ¿Cómo…</i>",
            truncator.words(3, html=True),
        )
        truncator = text.Truncator("<p>I &lt;3 python, what about you?</p>")
        self.assertEqual("<p>I &lt;3 python,…</p>", truncator.words(3, html=True))

        truncator = text.Truncator("foo</p>")
        self.assertEqual("foo</p>", truncator.words(3, html=True))

        # Only open brackets.
        truncator = text.Truncator("<" * 60_000)
        self.assertEqual(truncator.words(1, html=True), "&lt;…")

        # Tags with special chars in attrs.
        truncator = text.Truncator(
            """<i style="margin: 5%; font: *;">Hello, my dear lady!</i>"""
        )
        self.assertEqual(
            """<i style="margin: 5%; font: *;">Hello, my dear…</i>""",
            truncator.words(3, html=True),
        )

        # Tags with special non-latin chars in attrs.
        truncator = text.Truncator("""<p data-x="א">Hello, my dear lady!</p>""")
        self.assertEqual(
            """<p data-x="א">Hello, my dear…</p>""",
            truncator.words(3, html=True),
        )

        # Misplaced brackets.
        truncator = text.Truncator("hello >< world")
        self.assertEqual(truncator.words(1, html=True), "hello…")
        self.assertEqual(truncator.words(2, html=True), "hello &gt;…")
        self.assertEqual(truncator.words(3, html=True), "hello &gt;&lt;…")
        self.assertEqual(truncator.words(4, html=True), "hello &gt;&lt; world")

    @patch("django.utils.text.Truncator.MAX_LENGTH_HTML", 10_000)
    def test_truncate_words_html_size_limit(self):
        """

        Tests the truncation of HTML strings to a specified word limit while adhering to the maximum allowed HTML length.

        This test function verifies that the Truncator class correctly truncates HTML content
        to prevent exceeding the maximum allowed HTML length, ensuring that the resulting string
        is valid and properly truncated to the specified word limit.

        """
        max_len = text.Truncator.MAX_LENGTH_HTML
        bigger_len = text.Truncator.MAX_LENGTH_HTML + 1
        valid_html = "<p>Joel is a slug</p>"  # 4 words
        perf_test_values = [
            ("</a" + "\t" * (max_len - 6) + "//>", "</a>"),
            ("</p" + "\t" * bigger_len + "//>", "</p>"),
            ("&" * max_len, ""),
            ("&" * bigger_len, ""),
            ("_X<<<<<<<<<<<>", "_X&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&gt;"),
            (valid_html * bigger_len, valid_html * 12 + "<p>Joel is…</p>"),  # 50 words
        ]
        for value, expected in perf_test_values:
            with self.subTest(value=value):
                truncator = text.Truncator(value)
                self.assertEqual(expected, truncator.words(50, html=True))

    def test_wrap(self):
        digits = "1234 67 9"
        self.assertEqual(text.wrap(digits, 100), "1234 67 9")
        self.assertEqual(text.wrap(digits, 9), "1234 67 9")
        self.assertEqual(text.wrap(digits, 8), "1234 67\n9")

        self.assertEqual(text.wrap("short\na long line", 7), "short\na long\nline")
        self.assertEqual(
            text.wrap("do-not-break-long-words please? ok", 8),
            "do-not-break-long-words\nplease?\nok",
        )

        long_word = "l%sng" % ("o" * 20)
        self.assertEqual(text.wrap(long_word, 20), long_word)
        self.assertEqual(
            text.wrap("a %s word" % long_word, 10), "a\n%s\nword" % long_word
        )
        self.assertEqual(text.wrap(lazystr(digits), 100), "1234 67 9")

    def test_normalize_newlines(self):
        """
        Tests the function to normalize newlines in a given text.

        This function ensures that all newlines are standardized to '\n' across different platforms,
        replacing occurrences of '\r\n' and '\r' with a single '\n'. The function handles
        strings containing mixed newline characters, as well as strings without any newline characters.
        It also supports input from lazy string objects.

        The test covers various scenarios, including strings with multiple newline types,
        strings without newlines, empty strings, and lazy strings.

        """
        self.assertEqual(
            text.normalize_newlines("abc\ndef\rghi\r\n"), "abc\ndef\nghi\n"
        )
        self.assertEqual(text.normalize_newlines("\n\r\r\n\r"), "\n\n\n\n")
        self.assertEqual(text.normalize_newlines("abcdefghi"), "abcdefghi")
        self.assertEqual(text.normalize_newlines(""), "")
        self.assertEqual(
            text.normalize_newlines(lazystr("abc\ndef\rghi\r\n")), "abc\ndef\nghi\n"
        )

    def test_phone2numeric(self):
        numeric = text.phone2numeric("0800 flowers")
        self.assertEqual(numeric, "0800 3569377")
        lazy_numeric = lazystr(text.phone2numeric("0800 flowers"))
        self.assertEqual(lazy_numeric, "0800 3569377")

    def test_slugify(self):
        """

        Test the slugify function to ensure it correctly converts input strings into slug format.

        The test cases cover a variety of scenarios, including:
        * Converting special characters to hyphens
        * Removing whitespace and other unwanted characters
        * Handling strings with non-ASCII characters (unicode)
        * Stripping leading and trailing underscores and hyphens
        * Preserving non-ASCII characters when allowed

        The function is checked to produce the expected output for each test case and also verifies that the output is interned.

        """
        items = (
            # given - expected - Unicode?
            ("Hello, World!", "hello-world", False),
            ("spam & eggs", "spam-eggs", False),
            (" multiple---dash and  space ", "multiple-dash-and-space", False),
            ("\t whitespace-in-value \n", "whitespace-in-value", False),
            ("underscore_in-value", "underscore_in-value", False),
            ("__strip__underscore-value___", "strip__underscore-value", False),
            ("--strip-dash-value---", "strip-dash-value", False),
            ("__strip-mixed-value---", "strip-mixed-value", False),
            ("_ -strip-mixed-value _-", "strip-mixed-value", False),
            ("spam & ıçüş", "spam-ıçüş", True),
            ("foo ıç bar", "foo-ıç-bar", True),
            ("    foo ıç bar", "foo-ıç-bar", True),
            ("你好", "你好", True),
            ("İstanbul", "istanbul", True),
        )
        for value, output, is_unicode in items:
            with self.subTest(value=value):
                self.assertEqual(text.slugify(value, allow_unicode=is_unicode), output)
        # Interning the result may be useful, e.g. when fed to Path.
        with self.subTest("intern"):
            self.assertEqual(sys.intern(text.slugify("a")), "a")

    def test_unescape_string_literal(self):
        """

        Tests the unescape_string_literal function to ensure it correctly removes escape characters from string literals.

        The function is verified to work correctly with both single and double quoted strings, 
        as well as strings containing escaped quotes and other special characters. 
        The test also checks that the function works with lazy string inputs. 

        The expected output is the original string with any escape sequences properly interpreted.

        """
        items = [
            ('"abc"', "abc"),
            ("'abc'", "abc"),
            ('"a "bc""', 'a "bc"'),
            ("''ab' c'", "'ab' c"),
        ]
        for value, output in items:
            with self.subTest(value=value):
                self.assertEqual(text.unescape_string_literal(value), output)
                self.assertEqual(text.unescape_string_literal(lazystr(value)), output)

    def test_unescape_string_literal_invalid_value(self):
        items = ["", "abc", "'abc\""]
        for item in items:
            msg = f"Not a string literal: {item!r}"
            with self.assertRaisesMessage(ValueError, msg):
                text.unescape_string_literal(item)

    def test_get_valid_filename(self):
        """

        Generates a valid filename by removing or replacing invalid characters.

        This function takes a string as input, which may contain a variety of characters,
        including special characters and whitespace. It processes the input string to
        produce a safe and valid filename that can be used in different operating systems.

        The function replaces or removes characters that are not valid in filenames,
        such as certain special characters, to ensure the resulting filename is compatible
        with common file systems.

        If the input string does not contain any valid filename characters, the function
        raises a SuspiciousFileOperation exception to indicate that it was unable to derive
        a valid filename from the input.

        """
        filename = "^&'@{}[],$=!-#()%+~_123.txt"
        self.assertEqual(text.get_valid_filename(filename), "-_123.txt")
        self.assertEqual(text.get_valid_filename(lazystr(filename)), "-_123.txt")
        msg = "Could not derive file name from '???'"
        with self.assertRaisesMessage(SuspiciousFileOperation, msg):
            text.get_valid_filename("???")
        # After sanitizing this would yield '..'.
        msg = "Could not derive file name from '$.$.$'"
        with self.assertRaisesMessage(SuspiciousFileOperation, msg):
            text.get_valid_filename("$.$.$")

    def test_compress_sequence(self):
        """

        Tests the functionality of compressing a sequence of bytes.

        This test case creates a sample JSON dataset, encodes it into a sequence of bytes, 
        and then uses the :func:`text.compress_sequence` function to compress this sequence.
        The test verifies that the compressed sequence is shorter than the original sequence. 
        """
        data = [{"key": i} for i in range(10)]
        seq = list(json.JSONEncoder().iterencode(data))
        seq = [s.encode() for s in seq]
        actual_length = len(b"".join(seq))
        out = text.compress_sequence(seq)
        compressed_length = len(b"".join(out))
        self.assertLess(compressed_length, actual_length)

    def test_format_lazy(self):
        self.assertEqual("django/test", format_lazy("{}/{}", "django", lazystr("test")))
        self.assertEqual("django/test", format_lazy("{0}/{1}", *("django", "test")))
        self.assertEqual(
            "django/test", format_lazy("{a}/{b}", **{"a": "django", "b": "test"})
        )
        self.assertEqual(
            "django/test", format_lazy("{a[0]}/{a[1]}", a=("django", "test"))
        )

        t = {}
        s = format_lazy("{0[a]}-{p[a]}", t, p=t)
        t["a"] = lazystr("django")
        self.assertEqual("django-django", s)
        t["a"] = "update"
        self.assertEqual("update-update", s)

        # The format string can be lazy. (string comes from contrib.admin)
        s = format_lazy(
            gettext_lazy("Added {name} “{object}”."),
            name="article",
            object="My first try",
        )
        with override("fr"):
            self.assertEqual("Ajout de article «\xa0My first try\xa0».", s)
