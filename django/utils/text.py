import gzip
import re
import secrets
import unicodedata
from collections import deque
from gzip import GzipFile
from gzip import compress as gzip_compress
from html import escape
from html.parser import HTMLParser
from io import BytesIO

from django.core.exceptions import SuspiciousFileOperation
from django.utils.functional import (
    SimpleLazyObject,
    cached_property,
    keep_lazy_text,
    lazy,
)
from django.utils.regex_helper import _lazy_re_compile
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, pgettext


@keep_lazy_text
def capfirst(x):
    """
    Capitalize the first letter of a given string or string representation of an object, returning the resulting string.
    """
    if not x:
        return x
    if not isinstance(x, str):
        x = str(x)
    return x[0].upper() + x[1:]


# Set up regular expressions
re_newlines = _lazy_re_compile(r"\r\n|\r")  # Used in normalize_newlines
re_camel_case = _lazy_re_compile(r"(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))")


@keep_lazy_text
def wrap(text, width):
    """
    Wraps input text to a specified width while preserving existing line breaks.
    Preserves whitespace, except for added line breaks which consume the preceding space.
    Note that long words are not wrapped, potentially resulting in lines exceeding the specified width.
    """

    def _generator():
        """

        Generates a sequence of lines by wrapping a given text to a specified width.
        The function splits the text into lines, then divides each line into chunks
        of a specified maximum width, attempting to split at spaces.

        """
        for line in text.splitlines(True):  # True keeps trailing linebreaks
            max_width = min((line.endswith("\n") and width + 1 or width), width)
            while len(line) > max_width:
                space = line[: max_width + 1].rfind(" ") + 1
                if space == 0:
                    space = line.find(" ") + 1
                    if space == 0:
                        yield line
                        line = ""
                        break
                yield "%s\n" % line[: space - 1]
                line = line[space:]
                max_width = min((line.endswith("\n") and width + 1 or width), width)
            if line:
                yield line

    return "".join(_generator())


def add_truncation_text(text, truncate=None):
    """
    Appends a truncation text to the input text if it does not already end with it, allowing for optional customization of the truncation text.
    """
    if truncate is None:
        truncate = pgettext(
            "String to return when truncating text", "%(truncated_text)s…"
        )
    if "%(truncated_text)s" in truncate:
        return truncate % {"truncated_text": text}
    # The truncation text didn't contain the %(truncated_text)s string
    # replacement argument so just append it to the text.
    if text.endswith(truncate):
        # But don't append the truncation text if the current text already ends
        # in this.
        return text
    return f"{text}{truncate}"


def calculate_truncate_chars_length(length, replacement):
    """
    Calculate the available length for a truncated string, taking into account the length of the replacement text that will be appended.
    """
    truncate_len = length
    for char in add_truncation_text("", replacement):
        if not unicodedata.combining(char):
            truncate_len -= 1
            if truncate_len == 0:
                break
    return truncate_len


class TruncateHTMLParser(HTMLParser):
    class TruncationCompleted(Exception):
        pass

    def __init__(self, *, length, replacement, convert_charrefs=True):
        """
        Initializes the HTML unescaping parser with the specified length and replacement character, preparing it to process a stream of HTML data.
        """
        super().__init__(convert_charrefs=convert_charrefs)
        self.tags = deque()
        self.output = ""
        self.remaining = length
        self.replacement = replacement

    @cached_property
    def void_elements(self):
        from django.utils.html import VOID_ELEMENTS

        return VOID_ELEMENTS

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.void_elements:
            self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        self.output += self.get_starttag_text()
        if tag not in self.void_elements:
            self.tags.appendleft(tag)

    def handle_endtag(self, tag):
        """
        Closes an HTML tag by appending the corresponding end tag to the output and removing it from the list of open tags, unless it is a void element that does not require a closing tag.
        """
        if tag not in self.void_elements:
            self.output += f"</{tag}>"
            try:
                self.tags.remove(tag)
            except ValueError:
                pass

    def handle_data(self, data):
        """
        Handle incoming data, processing it and adding it to the output while tracking a truncation limit.

        If the data exceeds the remaining truncation limit, truncation is marked as completed, 
        a replacement string is added to the output, and a TruncationCompleted exception is raised. 
        Otherwise, the remaining truncation limit is updated and the processed data is appended to the output.
        """
        data, output = self.process(data)
        data_len = len(data)
        if self.remaining < data_len:
            self.remaining = 0
            self.output += add_truncation_text(output, self.replacement)
            raise self.TruncationCompleted
        self.remaining -= data_len
        self.output += output

    def feed(self, data):
        """
        Feeds data to the parser, handling truncation and resetting the state as necessary.
        """
        try:
            super().feed(data)
        except self.TruncationCompleted:
            self.output += "".join([f"</{tag}>" for tag in self.tags])
            self.tags.clear()
            self.reset()
        else:
            # No data was handled.
            self.reset()


class TruncateCharsHTMLParser(TruncateHTMLParser):
    def __init__(self, *, length, replacement, convert_charrefs=True):
        self.length = length
        self.processed_chars = 0
        super().__init__(
            length=calculate_truncate_chars_length(length, replacement),
            replacement=replacement,
            convert_charrefs=convert_charrefs,
        )

    def process(self, data):
        """
        Process a chunk of data, potentially completing the truncation process and raising an exception when finished, while also generating escaped output for the current chunk.
        """
        self.processed_chars += len(data)
        if (self.processed_chars == self.length) and (
            len(self.output) + len(data) == len(self.rawdata)
        ):
            self.output += data
            raise self.TruncationCompleted
        output = escape("".join(data[: self.remaining]))
        return data, output


class TruncateWordsHTMLParser(TruncateHTMLParser):
    def process(self, data):
        data = re.split(r"(?<=\S)\s+(?=\S)", data)
        output = escape(" ".join(data[: self.remaining]))
        return data, output


class Truncator(SimpleLazyObject):
    """
    An object used to truncate text, either by characters or words.

    When truncating HTML text (either chars or words), input will be limited to
    at most `MAX_LENGTH_HTML` characters.
    """

    # 5 million characters are approximately 4000 text pages or 3 web pages.
    MAX_LENGTH_HTML = 5_000_000

    def __init__(self, text):
        super().__init__(lambda: str(text))

    def chars(self, num, truncate=None, html=False):
        """

        Return the text truncated to a specified number of characters.

        The truncated text can be customized with a notification string.
        Optional HTML parsing allows for truncation while preserving HTML structure.

        """
        self._setup()
        length = int(num)
        if length <= 0:
            return ""
        text = unicodedata.normalize("NFC", self._wrapped)

        if html:
            parser = TruncateCharsHTMLParser(length=length, replacement=truncate)
            parser.feed(text)
            parser.close()
            return parser.output
        return self._text_chars(length, truncate, text)

    def _text_chars(self, length, truncate, text):
        """
        Truncates a given text to a specified length, considering Unicode characters and optionally appending a truncation indicator.
        """
        truncate_len = calculate_truncate_chars_length(length, truncate)
        s_len = 0
        end_index = None
        for i, char in enumerate(text):
            if unicodedata.combining(char):
                # Don't consider combining characters
                # as adding to the string length
                continue
            s_len += 1
            if end_index is None and s_len > truncate_len:
                end_index = i
            if s_len > length:
                # Return the truncated string
                return add_truncation_text(text[: end_index or 0], truncate)

        # Return the original string since no truncation was necessary
        return text

    def words(self, num, truncate=None, html=False):
        """
        Truncates a string after a specified number of words, optionally appending a notification that the string has been shortened. 
        The truncation notification can be customized with the `truncate` parameter. 
        Also supports HTML truncation, preserving the original HTML structure, when `html` is enabled.
        """
        self._setup()
        length = int(num)
        if length <= 0:
            return ""
        if html:
            parser = TruncateWordsHTMLParser(length=length, replacement=truncate)
            parser.feed(self._wrapped)
            parser.close()
            return parser.output
        return self._text_words(length, truncate)

    def _text_words(self, length, truncate):
        """
        Truncates a string to a specified number of words, removing newlines and adding a truncation indicator if necessary.
        """
        words = self._wrapped.split()
        if len(words) > length:
            words = words[:length]
            return add_truncation_text(" ".join(words), truncate)
        return " ".join(words)


@keep_lazy_text
def get_valid_filename(name):
    """

    Return a string converted to a valid filename by removing leading and trailing spaces, 
    converting other spaces to underscores, and removing non-alphanumeric, non-dash, non-underscore, and non-dot characters.

    :param name: The string to be converted to a valid filename
    :return: A string that can be used as a clean filename
    :raises SuspiciousFileOperation: If the derived filename is empty, '.' or '..'

    """
    s = str(name).strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    if s in {"", ".", ".."}:
        raise SuspiciousFileOperation("Could not derive file name from '%s'" % name)
    return s


@keep_lazy_text
def get_text_list(list_, last_word=gettext_lazy("or")):
    """

    Converts a list of items into a human-readable string, 
    joining all but the last item with commas and the last item with a specified conjunction.

    :param list_: The list of items to convert to a string
    :param last_word: The word to use to join the last item, defaults to 'or'
    :return: A string representation of the list

    """
    if not list_:
        return ""
    if len(list_) == 1:
        return str(list_[0])
    return "%s %s %s" % (
        # Translators: This string is used as a separator between list elements
        _(", ").join(str(i) for i in list_[:-1]),
        str(last_word),
        str(list_[-1]),
    )


@keep_lazy_text
def normalize_newlines(text):
    """Normalize CRLF and CR newlines to just LF."""
    return re_newlines.sub("\n", str(text))


@keep_lazy_text
def phone2numeric(phone):
    """Convert a phone number with letters into its numeric equivalent."""
    char2number = {
        "a": "2",
        "b": "2",
        "c": "2",
        "d": "3",
        "e": "3",
        "f": "3",
        "g": "4",
        "h": "4",
        "i": "4",
        "j": "5",
        "k": "5",
        "l": "5",
        "m": "6",
        "n": "6",
        "o": "6",
        "p": "7",
        "q": "7",
        "r": "7",
        "s": "7",
        "t": "8",
        "u": "8",
        "v": "8",
        "w": "9",
        "x": "9",
        "y": "9",
        "z": "9",
    }
    return "".join(char2number.get(c, c) for c in phone.lower())


def _get_random_filename(max_random_bytes):
    return b"a" * secrets.randbelow(max_random_bytes)


def compress_string(s, *, max_random_bytes=None):
    """
    Compress a string using gzip compression and optionally add a random filename to the header.

    :arg str s: The input string to be compressed.
    :arg int max_random_bytes: Optional maximum number of bytes for the random filename.
    :return bytes: The compressed data with optional random filename in the gzip header.
    """
    compressed_data = gzip_compress(s, compresslevel=6, mtime=0)

    if not max_random_bytes:
        return compressed_data

    compressed_view = memoryview(compressed_data)
    header = bytearray(compressed_view[:10])
    header[3] = gzip.FNAME

    filename = _get_random_filename(max_random_bytes) + b"\x00"

    return bytes(header) + filename + compressed_view[10:]


class StreamingBuffer(BytesIO):
    def read(self):
        ret = self.getvalue()
        self.seek(0)
        self.truncate()
        return ret


# Like compress_string, but for iterators of strings.
def compress_sequence(sequence, *, max_random_bytes=None):
    """
    Generate compressed data from a sequence of items on-the-fly.

    This function takes a sequence of items and returns a generator that produces compressed chunks of data.
    It uses gzip compression and allows for optional specification of a random filename.
    The compressed data is yielded as it is generated, allowing for efficient handling of large sequences.
    """
    buf = StreamingBuffer()
    filename = _get_random_filename(max_random_bytes) if max_random_bytes else None
    with GzipFile(
        filename=filename, mode="wb", compresslevel=6, fileobj=buf, mtime=0
    ) as zfile:
        # Output headers...
        yield buf.read()
        for item in sequence:
            zfile.write(item)
            data = buf.read()
            if data:
                yield data
    yield buf.read()


# Expression to match some_token and some_token="with spaces" (and similarly
# for single-quoted strings).
smart_split_re = _lazy_re_compile(
    r"""
    ((?:
        [^\s'"]*
        (?:
            (?:"(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*')
            [^\s'"]*
        )+
    ) | \S+)
""",
    re.VERBOSE,
)


def smart_split(text):
    r"""
    Generator that splits a string by spaces, leaving quoted phrases together.
    Supports both single and double quotes, and supports escaping quotes with
    backslashes. In the output, strings will keep their initial and trailing
    quote marks and escaped quotes will remain escaped (the results can then
    be further processed with unescape_string_literal()).

    >>> list(smart_split(r'This is "a person\'s" test.'))
    ['This', 'is', '"a person\\\'s"', 'test.']
    >>> list(smart_split(r"Another 'person\'s' test."))
    ['Another', "'person\\'s'", 'test.']
    >>> list(smart_split(r'A "\"funky\" style" test.'))
    ['A', '"\\"funky\\" style"', 'test.']
    """
    for bit in smart_split_re.finditer(str(text)):
        yield bit[0]


@keep_lazy_text
def unescape_string_literal(s):
    """
    Removes quotes and unescapes characters in a string literal, returning the contained string.
    It supports both single and double quoted strings and correctly handles escaped quotes and backslashes.
    """
    if not s or s[0] not in "\"'" or s[-1] != s[0]:
        raise ValueError("Not a string literal: %r" % s)
    quote = s[0]
    return s[1:-1].replace(r"\%s" % quote, quote).replace(r"\\", "\\")


@keep_lazy_text
def slugify(value, allow_unicode=False):
    """
    Converts a string into a slug, a lowercase string suitable for use in URLs, by removing unwanted characters and replacing spaces with dashes.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def camel_case_to_spaces(value):
    """
    Split CamelCase and convert to lowercase. Strip surrounding whitespace.
    """
    return re_camel_case.sub(r" \1", value).strip().lower()


def _format_lazy(format_string, *args, **kwargs):
    """
    Apply str.format() on 'format_string' where format_string, args,
    and/or kwargs might be lazy.
    """
    return format_string.format(*args, **kwargs)


format_lazy = lazy(_format_lazy, str)
