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
    This is a comment
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
    This is a comment
    """

    def _generator():
        """
        This is a comment
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
    This is a comment
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
    This is a comment
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
        This is a comment
        """
        super().__init__(convert_charrefs=convert_charrefs)
        self.tags = deque()
        self.output = ""
        self.remaining = length
        self.replacement = replacement

    @cached_property
    def void_elements(self):
        """
        This is a comment
        """
        from django.utils.html import VOID_ELEMENTS

        return VOID_ELEMENTS

    def handle_startendtag(self, tag, attrs):
        """
        This is a comment
        """
        self.handle_starttag(tag, attrs)
        if tag not in self.void_elements:
            self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        """
        This is a comment
        """
        self.output += self.get_starttag_text()
        if tag not in self.void_elements:
            self.tags.appendleft(tag)

    def handle_endtag(self, tag):
        """
        This is a comment
        """
        if tag not in self.void_elements:
            self.output += f"</{tag}>"
            try:
                self.tags.remove(tag)
            except ValueError:
                pass

    def handle_data(self, data):
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
        self.length = length
        self.processed_chars = 0
        super().__init__(
            length=calculate_truncate_chars_length(length, replacement),
            replacement=replacement,
            convert_charrefs=convert_charrefs,
        )

    def process(self, data):
        """
        This is a comment
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        super().__init__(lambda: str(text))

    def chars(self, num, truncate=None, html=False):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
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
        This is a comment
        """
        words = self._wrapped.split()
        if len(words) > length:
            words = words[:length]
            return add_truncation_text(" ".join(words), truncate)
        return " ".join(words)


@keep_lazy_text
def get_valid_filename(name):
    """
    This is a comment
    """
    s = str(name).strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    if s in {"", ".", ".."}:
        raise SuspiciousFileOperation("Could not derive file name from '%s'" % name)
    return s


@keep_lazy_text
def get_text_list(list_, last_word=gettext_lazy("or")):
    """
    This is a comment
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
    """
    This is a comment
    """
    return re_newlines.sub("\n", str(text))


@keep_lazy_text
def phone2numeric(phone):
    """
    This is a comment
    """
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
    """
    This is a comment
    """
    return b"a" * secrets.randbelow(max_random_bytes)


def compress_string(s, *, max_random_bytes=None):
    """
    This is a comment
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
        """
        This is a comment
        """
        ret = self.getvalue()
        self.seek(0)
        self.truncate()
        return ret


# Like compress_string, but for iterators of strings.
def compress_sequence(sequence, *, max_random_bytes=None):
    """
    This is a comment
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
    """
    This is a comment
    """
    for bit in smart_split_re.finditer(str(text)):
        yield bit[0]


@keep_lazy_text
def unescape_string_literal(s):
    """
    This is a comment
    """
    if not s or s[0] not in "\"'" or s[-1] != s[0]:
        raise ValueError("Not a string literal: %r" % s)
    quote = s[0]
    return s[1:-1].replace(r"\%s" % quote, quote).replace(r"\\", "\\")


@keep_lazy_text
def slugify(value, allow_unicode=False):
    """
    This is a comment
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
    This is a comment
    """
    return re_camel_case.sub(r" \1", value).strip().lower()


def _format_lazy(format_string, *args, **kwargs):
    """
    This is a comment
    """
    return format_string.format(*args, **kwargs)


format_lazy = lazy(_format_lazy, str)
