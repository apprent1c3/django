"""Default variable filters."""

import random as random_module
import re
import types
from decimal import ROUND_HALF_UP, Context, Decimal, InvalidOperation, getcontext
from functools import wraps
from inspect import unwrap
from operator import itemgetter
from pprint import pformat
from urllib.parse import quote

from django.utils import formats
from django.utils.dateformat import format, time_format
from django.utils.encoding import iri_to_uri
from django.utils.html import avoid_wrapping, conditional_escape, escape, escapejs
from django.utils.html import json_script as _json_script
from django.utils.html import linebreaks, strip_tags
from django.utils.html import urlize as _urlize
from django.utils.safestring import SafeData, mark_safe
from django.utils.text import Truncator, normalize_newlines, phone2numeric
from django.utils.text import slugify as _slugify
from django.utils.text import wrap
from django.utils.timesince import timesince, timeuntil
from django.utils.translation import gettext, ngettext

from .base import VARIABLE_ATTRIBUTE_SEPARATOR
from .library import Library

register = Library()


#######################
# STRING DECORATOR    #
#######################


def stringfilter(func):
    """
    Ensures that the decorated function receives a string as its first positional argument, converting it if necessary, and optionally marks the result as safe if the original input was safe data and the function is marked as safe.
    """

    @wraps(func)
    def _dec(first, *args, **kwargs):
        """

        Decorator function to wrap another function, ensuring the result is marked as safe 
        if the original function is marked as safe and the input is an instance of SafeData.

        """
        first = str(first)
        result = func(first, *args, **kwargs)
        if isinstance(first, SafeData) and getattr(unwrap(func), "is_safe", False):
            result = mark_safe(result)
        return result

    return _dec


###################
# STRINGS         #
###################


@register.filter(is_safe=True)
@stringfilter
def addslashes(value):
    """
    Add slashes before quotes. Useful for escaping strings in CSV, for
    example. Less useful for escaping JavaScript; use the ``escapejs``
    filter instead.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")


@register.filter(is_safe=True)
@stringfilter
def capfirst(value):
    """Capitalize the first character of the value."""
    return value and value[0].upper() + value[1:]


@register.filter("escapejs")
@stringfilter
def escapejs_filter(value):
    """Hex encode characters for use in JavaScript strings."""
    return escapejs(value)


@register.filter(is_safe=True)
def json_script(value, element_id=None):
    """
    Output value JSON-encoded, wrapped in a <script type="application/json">
    tag (with an optional id).
    """
    return _json_script(value, element_id)


@register.filter(is_safe=True)
def floatformat(text, arg=-1):
    """
    Formats a float number to display a specified number of decimal places, with options for localized formatting and grouping by thousands.
    """
    force_grouping = False
    use_l10n = True
    if isinstance(arg, str):
        last_char = arg[-1]
        if arg[-2:] in {"gu", "ug"}:
            force_grouping = True
            use_l10n = False
            arg = arg[:-2] or -1
        elif last_char == "g":
            force_grouping = True
            arg = arg[:-1] or -1
        elif last_char == "u":
            use_l10n = False
            arg = arg[:-1] or -1
    try:
        input_val = str(text)
        d = Decimal(input_val)
    except InvalidOperation:
        try:
            d = Decimal(str(float(text)))
        except (ValueError, InvalidOperation, TypeError):
            return ""
    try:
        p = int(arg)
    except ValueError:
        return input_val

    try:
        m = int(d) - d
    except (ValueError, OverflowError, InvalidOperation):
        return input_val

    if not m and p <= 0:
        return mark_safe(
            formats.number_format(
                "%d" % (int(d)),
                0,
                use_l10n=use_l10n,
                force_grouping=force_grouping,
            )
        )

    exp = Decimal(1).scaleb(-abs(p))
    # Set the precision high enough to avoid an exception (#15789).
    tupl = d.as_tuple()
    units = len(tupl[1])
    units += -tupl[2] if m else tupl[2]
    prec = abs(p) + units + 1
    prec = max(getcontext().prec, prec)

    # Avoid conversion to scientific notation by accessing `sign`, `digits`,
    # and `exponent` from Decimal.as_tuple() directly.
    rounded_d = d.quantize(exp, ROUND_HALF_UP, Context(prec=prec))
    sign, digits, exponent = rounded_d.as_tuple()
    digits = [str(digit) for digit in reversed(digits)]
    while len(digits) <= abs(exponent):
        digits.append("0")
    digits.insert(-exponent, ".")
    if sign and rounded_d:
        digits.append("-")
    number = "".join(reversed(digits))
    return mark_safe(
        formats.number_format(
            number,
            abs(p),
            use_l10n=use_l10n,
            force_grouping=force_grouping,
        )
    )


@register.filter(is_safe=True)
@stringfilter
def iriencode(value):
    """Escape an IRI value for use in a URL."""
    return iri_to_uri(value)


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def linenumbers(value, autoescape=True):
    """
    Display text with line numbers. 

    This filter takes a text string as input, splits it into lines, 
    and prefixes each line with a zero-padded line number, 
    ensuring the line numbers are aligned for easy reading. 
    The filter also handles autoescaping to prevent XSS attacks.
    """
    lines = value.split("\n")
    # Find the maximum width of the line count, for use with zero padding
    # string format command
    width = str(len(str(len(lines))))
    if not autoescape or isinstance(value, SafeData):
        for i, line in enumerate(lines):
            lines[i] = ("%0" + width + "d. %s") % (i + 1, line)
    else:
        for i, line in enumerate(lines):
            lines[i] = ("%0" + width + "d. %s") % (i + 1, escape(line))
    return mark_safe("\n".join(lines))


@register.filter(is_safe=True)
@stringfilter
def lower(value):
    """Convert a string into all lowercase."""
    return value.lower()


@register.filter(is_safe=False)
@stringfilter
def make_list(value):
    """
    Return the value turned into a list.

    For an integer, it's a list of digits.
    For a string, it's a list of characters.
    """
    return list(value)


@register.filter(is_safe=True)
@stringfilter
def slugify(value):
    """
    Convert to ASCII. Convert spaces to hyphens. Remove characters that aren't
    alphanumerics, underscores, or hyphens. Convert to lowercase. Also strip
    leading and trailing whitespace.
    """
    return _slugify(value)


@register.filter(is_safe=True)
def stringformat(value, arg):
    """
    Format the input value according to the provided string formatting specifier, 
    supporting Python's printf-style string formatting, with the exception of the 
    leading \"%\" symbol. If formatting fails, an empty string is returned.
    """
    if isinstance(value, tuple):
        value = str(value)
    try:
        return ("%" + str(arg)) % value
    except (ValueError, TypeError):
        return ""


@register.filter(is_safe=True)
@stringfilter
def title(value):
    """Convert a string into titlecase."""
    t = re.sub("([a-z])'([A-Z])", lambda m: m[0].lower(), value.title())
    return re.sub(r"\d([A-Z])", lambda m: m[0].lower(), t)


@register.filter(is_safe=True)
@stringfilter
def truncatechars(value, arg):
    """
    Truncates a string to a specified length, removing excess characters. The resulting string is truncated after the specified number of characters, effectively shortening the original string.
    """
    try:
        length = int(arg)
    except ValueError:  # Invalid literal for int().
        return value  # Fail silently.
    return Truncator(value).chars(length)


@register.filter(is_safe=True)
@stringfilter
def truncatechars_html(value, arg):
    """
    Truncates HTML text to a specified number of characters while preserving newlines, ensuring safe rendering of the truncated HTML.
    """
    try:
        length = int(arg)
    except ValueError:  # invalid literal for int()
        return value  # Fail silently.
    return Truncator(value).chars(length, html=True)


@register.filter(is_safe=True)
@stringfilter
def truncatewords(value, arg):
    """
    Truncates a given string to a specified number of words and removes newlines, appending an ellipsis if shortened.
    """
    try:
        length = int(arg)
    except ValueError:  # Invalid literal for int().
        return value  # Fail silently.
    return Truncator(value).words(length, truncate=" …")


@register.filter(is_safe=True)
@stringfilter
def truncatewords_html(value, arg):
    """
    Truncates HTML content after a specified number of words, preserving newlines and indicating truncation with an ellipsis.
    """
    try:
        length = int(arg)
    except ValueError:  # invalid literal for int()
        return value  # Fail silently.
    return Truncator(value).words(length, html=True, truncate=" …")


@register.filter(is_safe=False)
@stringfilter
def upper(value):
    """Convert a string into all uppercase."""
    return value.upper()


@register.filter(is_safe=False)
@stringfilter
def urlencode(value, safe=None):
    """
    Escape a value for use in a URL, optionally specifying characters that should not be escaped.
    """
    kwargs = {}
    if safe is not None:
        kwargs["safe"] = safe
    return quote(value, **kwargs)


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlize(value, autoescape=True):
    """Convert URLs in plain text into clickable links."""
    return mark_safe(_urlize(value, nofollow=True, autoescape=autoescape))


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def urlizetrunc(value, limit, autoescape=True):
    """
    Convert URLs into clickable links, truncating URLs to the given character
    limit, and adding 'rel=nofollow' attribute to discourage spamming.

    Argument: Length to truncate URLs to.
    """
    return mark_safe(
        _urlize(value, trim_url_limit=int(limit), nofollow=True, autoescape=autoescape)
    )


@register.filter(is_safe=False)
@stringfilter
def wordcount(value):
    """Return the number of words."""
    return len(value.split())


@register.filter(is_safe=True)
@stringfilter
def wordwrap(value, arg):
    """Wrap words at `arg` line length."""
    return wrap(value, int(arg))


@register.filter(is_safe=True)
@stringfilter
def ljust(value, arg):
    """Left-align the value in a field of a given width."""
    return value.ljust(int(arg))


@register.filter(is_safe=True)
@stringfilter
def rjust(value, arg):
    """Right-align the value in a field of a given width."""
    return value.rjust(int(arg))


@register.filter(is_safe=True)
@stringfilter
def center(value, arg):
    """Center the value in a field of a given width."""
    return value.center(int(arg))


@register.filter
@stringfilter
def cut(value, arg):
    """
    Remove all occurrences of a specified substring from a given string, handling cases where the original string was marked as safe for HTML rendering.
    """
    safe = isinstance(value, SafeData)
    value = value.replace(arg, "")
    if safe and arg != ";":
        return mark_safe(value)
    return value


###################
# HTML STRINGS    #
###################


@register.filter("escape", is_safe=True)
@stringfilter
def escape_filter(value):
    """Mark the value as a string that should be auto-escaped."""
    return conditional_escape(value)


@register.filter(is_safe=True)
def escapeseq(value):
    """
    An "escape" filter for sequences. Mark each element in the sequence,
    individually, as a string that should be auto-escaped. Return a list with
    the results.
    """
    return [conditional_escape(obj) for obj in value]


@register.filter(is_safe=True)
@stringfilter
def force_escape(value):
    """
    Escape a string's HTML. Return a new string containing the escaped
    characters (as opposed to "escape", which marks the content for later
    possible escaping).
    """
    return escape(value)


@register.filter("linebreaks", is_safe=True, needs_autoescape=True)
@stringfilter
def linebreaks_filter(value, autoescape=True):
    """
    Replace line breaks in plain text with appropriate HTML; a single
    newline becomes an HTML line break (``<br>``) and a new line
    followed by a blank line becomes a paragraph break (``</p>``).
    """
    autoescape = autoescape and not isinstance(value, SafeData)
    return mark_safe(linebreaks(value, autoescape))


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def linebreaksbr(value, autoescape=True):
    """
    Converts plain text newlines to HTML line breaks for display in a web page, optionally escaping special characters to prevent XSS attacks.
    """
    autoescape = autoescape and not isinstance(value, SafeData)
    value = normalize_newlines(value)
    if autoescape:
        value = escape(value)
    return mark_safe(value.replace("\n", "<br>"))


@register.filter(is_safe=True)
@stringfilter
def safe(value):
    """Mark the value as a string that should not be auto-escaped."""
    return mark_safe(value)


@register.filter(is_safe=True)
def safeseq(value):
    """
    A "safe" filter for sequences. Mark each element in the sequence,
    individually, as safe, after converting them to strings. Return a list
    with the results.
    """
    return [mark_safe(obj) for obj in value]


@register.filter(is_safe=True)
@stringfilter
def striptags(value):
    """Strip all [X]HTML tags."""
    return strip_tags(value)


###################
# LISTS           #
###################


def _property_resolver(arg):
    """
    ```python
    def _property_resolver(arg):
        \"\"\"
        Resolves an attribute or index from an object.

        If the provided argument can be converted to a float, it acts as an index getter.
        Otherwise, it attempts to access the attribute or key of the object using a chain of __getitem__() and getattr() methods.

        This function is designed to handle both numerical and string-based attribute or index access in a flexible manner, while also respecting private variable access restrictions.
        \"\"\"
    ```
    """
    try:
        float(arg)
    except ValueError:
        if VARIABLE_ATTRIBUTE_SEPARATOR + "_" in arg or arg[0] == "_":
            raise AttributeError("Access to private variables is forbidden.")
        parts = arg.split(VARIABLE_ATTRIBUTE_SEPARATOR)

        def resolve(value):
            """

            Resolves a nested attribute or item from a given value.

            The function iterates through a predefined sequence of parts, attempting to access the value as an attribute or item until it is successfully resolved.

            It handles various exceptions that may occur during attribute or item access, including attribute and key errors.

            Returns the resolved value or the attribute that matches the sequence of parts.

            """
            for part in parts:
                try:
                    value = value[part]
                except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                    value = getattr(value, part)
            return value

        return resolve
    else:
        return itemgetter(arg)


@register.filter(is_safe=False)
def dictsort(value, arg):
    """
    Sorts a list of dictionaries by a specified property.

    :param value: The list of dictionaries to be sorted
    :param arg: The property to sort by
    :returns: A new sorted list of dictionaries, or an empty string if sorting fails
    :rtype: list or str
    """
    try:
        return sorted(value, key=_property_resolver(arg))
    except (AttributeError, TypeError):
        return ""


@register.filter(is_safe=False)
def dictsortreversed(value, arg):
    """
    Given a list of dictionaries, sorts the list in reverse order by the specified property and returns the sorted list. If the sorting fails, an empty string is returned.
    """
    try:
        return sorted(value, key=_property_resolver(arg), reverse=True)
    except (AttributeError, TypeError):
        return ""


@register.filter(is_safe=False)
def first(value):
    """
    Return the first item of a given list, or an empty string if the list is empty.
    """
    try:
        return value[0]
    except IndexError:
        return ""


@register.filter(is_safe=True, needs_autoescape=True)
def join(value, arg, autoescape=True):
    """

    Join a list of values into a single string, using a specified separator.

    This filter concatenates all elements of the input list with the provided string 
    in between each element, similar to the ``str.join()`` method in Python.

    """
    try:
        if autoescape:
            data = conditional_escape(arg).join([conditional_escape(v) for v in value])
        else:
            data = arg.join(value)
    except TypeError:  # Fail silently if arg isn't iterable.
        return value
    return mark_safe(data)


@register.filter(is_safe=True)
def last(value):
    """
    Returns the last item in a given list, or an empty string if the list is empty.
    """
    try:
        return value[-1]
    except IndexError:
        return ""


@register.filter(is_safe=False)
def length(value):
    """
    Return the length of the input value, primarily intended for use with lists and other iterable objects. If the input is not a valid object for determining length, returns 0.
    """
    try:
        return len(value)
    except (ValueError, TypeError):
        return 0


@register.filter(is_safe=True)
def random(value):
    """
    Returns a random item from a given list, or an empty string if the list is empty.
    """
    try:
        return random_module.choice(value)
    except IndexError:
        return ""


@register.filter("slice", is_safe=True)
def slice_filter(value, arg):
    """
    Return a slice of the input list using Python's list slicing syntax, for example \"1:3\", \":5\", or \":-1\". Handles invalid inputs by returning the original list.
    """
    try:
        bits = []
        for x in str(arg).split(":"):
            if not x:
                bits.append(None)
            else:
                bits.append(int(x))
        return value[slice(*bits)]

    except (ValueError, TypeError, KeyError):
        return value  # Fail silently.


@register.filter(is_safe=True, needs_autoescape=True)
def unordered_list(value, autoescape=True):
    """
    Recursively generates an HTML unordered list from a self-nested list, 
    excluding opening and closing <ul> tags. The input list is assumed to 
    be in a proper format, where each sublist is interpreted as a nested 
    unordered list in the resulting HTML.
    """
    if autoescape:
        escaper = conditional_escape
    else:

        def escaper(x):
            return x

    def walk_items(item_list):
        """
        Iterate through items in a list, yielding each item along with the next item 
        if it is a collection (list, tuple, or generator), otherwise yield the item with None.
        """
        item_iterator = iter(item_list)
        try:
            item = next(item_iterator)
            while True:
                try:
                    next_item = next(item_iterator)
                except StopIteration:
                    yield item, None
                    break
                if isinstance(next_item, (list, tuple, types.GeneratorType)):
                    try:
                        iter(next_item)
                    except TypeError:
                        pass
                    else:
                        yield item, next_item
                        item = next(item_iterator)
                        continue
                yield item, None
                item = next_item
        except StopIteration:
            pass

    def list_formatter(item_list, tabs=1):
        """
        Formats a list of items into an HTML unordered list with nested lists and indentation.

        :param item_list: The list of items to format, potentially containing nested lists
        :param int tabs: The number of tabs to use for indentation (default: 1)
        :returns: A string of HTML representing the formatted list
        """
        indent = "\t" * tabs
        output = []
        for item, children in walk_items(item_list):
            sublist = ""
            if children:
                sublist = "\n%s<ul>\n%s\n%s</ul>\n%s" % (
                    indent,
                    list_formatter(children, tabs + 1),
                    indent,
                    indent,
                )
            output.append("%s<li>%s%s</li>" % (indent, escaper(item), sublist))
        return "\n".join(output)

    return mark_safe(list_formatter(value))


###################
# INTEGERS        #
###################


@register.filter(is_safe=False)
def add(value, arg):
    """
    Concatenates or adds two values together, attempting integer addition if possible, falling back to string concatenation if not, and returning an empty string on failure.
    """
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        try:
            return value + arg
        except Exception:
            return ""


@register.filter(is_safe=False)
def get_digit(value, arg):
    """
    Extracts a specific digit from a given whole number, counting from the right. Returns the original value if the input or argument is invalid, or the specified digit if valid.
    """
    try:
        arg = int(arg)
        value = int(value)
    except ValueError:
        return value  # Fail silently for an invalid argument
    if arg < 1:
        return value
    try:
        return int(str(value)[-arg])
    except IndexError:
        return 0


###################
# DATES           #
###################


@register.filter(expects_localtime=True, is_safe=False)
def date(value, arg=None):
    """
    Formats a date using the specified format string, returning an empty string if the input date is invalid or missing.
    """
    if value in (None, ""):
        return ""
    try:
        return formats.date_format(value, arg)
    except AttributeError:
        try:
            return format(value, arg)
        except AttributeError:
            return ""


@register.filter(expects_localtime=True, is_safe=False)
def time(value, arg=None):
    """
    Formats a given time value according to a specified format, returning an empty string if the input value is empty or formatting fails.
    """
    if value in (None, ""):
        return ""
    try:
        return formats.time_format(value, arg)
    except (AttributeError, TypeError):
        try:
            return time_format(value, arg)
        except (AttributeError, TypeError):
            return ""


@register.filter("timesince", is_safe=False)
def timesince_filter(value, arg=None):
    """

    Format a date as the time since that date, providing a human-readable representation 
    of the elapsed time (e.g. \"4 days, 6 hours\"). If no time has elapsed, an empty string 
    is returned. Accepts an optional argument for custom date comparison. 

    """
    if not value:
        return ""
    try:
        if arg:
            return timesince(value, arg)
        return timesince(value)
    except (ValueError, TypeError):
        return ""


@register.filter("timeuntil", is_safe=False)
def timeuntil_filter(value, arg=None):
    """

    Format a date as the time until that date, displaying the difference in human-readable format.

    :param value: The date to calculate the time until
    :param arg: Optional argument to customize the calculation
    :return: A string representing the time until the given date, or an empty string if the input is invalid

    """
    if not value:
        return ""
    try:
        return timeuntil(value, arg)
    except (ValueError, TypeError):
        return ""


###################
# LOGIC           #
###################


@register.filter(is_safe=False)
def default(value, arg):
    """If value is unavailable, use given default."""
    return value or arg


@register.filter(is_safe=False)
def default_if_none(value, arg):
    """If value is None, use given default."""
    if value is None:
        return arg
    return value


@register.filter(is_safe=False)
def divisibleby(value, arg):
    """Return True if the value is divisible by the argument."""
    return int(value) % int(arg) == 0


@register.filter(is_safe=False)
def yesno(value, arg=None):
    """
    Given a boolean or null value, returns a string representing a human-readable interpretation of that value based on a customizable mapping of true, false, and optional null values.
    """
    if arg is None:
        # Translators: Please do not add spaces around commas.
        arg = gettext("yes,no,maybe")
    bits = arg.split(",")
    if len(bits) < 2:
        return value  # Invalid arg.
    try:
        yes, no, maybe = bits
    except ValueError:
        # Unpack list of wrong size (no "maybe" value provided).
        yes, no, maybe = bits[0], bits[1], bits[1]
    if value is None:
        return maybe
    if value:
        return yes
    return no


###################
# MISC            #
###################


@register.filter(is_safe=True)
def filesizeformat(bytes_):
    """
    Format the given number of bytes into a human-readable file size string.
    """
    try:
        bytes_ = int(bytes_)
    except (TypeError, ValueError, UnicodeDecodeError):
        value = ngettext("%(size)d byte", "%(size)d bytes", 0) % {"size": 0}
        return avoid_wrapping(value)

    def filesize_number_format(value):
        return formats.number_format(round(value, 1), 1)

    KB = 1 << 10
    MB = 1 << 20
    GB = 1 << 30
    TB = 1 << 40
    PB = 1 << 50

    negative = bytes_ < 0
    if negative:
        bytes_ = -bytes_  # Allow formatting of negative numbers.

    if bytes_ < KB:
        value = ngettext("%(size)d byte", "%(size)d bytes", bytes_) % {"size": bytes_}
    elif bytes_ < MB:
        value = gettext("%s KB") % filesize_number_format(bytes_ / KB)
    elif bytes_ < GB:
        value = gettext("%s MB") % filesize_number_format(bytes_ / MB)
    elif bytes_ < TB:
        value = gettext("%s GB") % filesize_number_format(bytes_ / GB)
    elif bytes_ < PB:
        value = gettext("%s TB") % filesize_number_format(bytes_ / TB)
    else:
        value = gettext("%s PB") % filesize_number_format(bytes_ / PB)

    if negative:
        value = "-%s" % value
    return avoid_wrapping(value)


@register.filter(is_safe=False)
def pluralize(value, arg="s"):
    """
    Return the singular or plural suffix for the given value, depending on whether the value is 1 or not. The suffix can be customized using the provided argument, allowing for flexible pluralization rules.
    """
    if "," not in arg:
        arg = "," + arg
    bits = arg.split(",")
    if len(bits) > 2:
        return ""
    singular_suffix, plural_suffix = bits[:2]

    try:
        return singular_suffix if float(value) == 1 else plural_suffix
    except ValueError:  # Invalid string that's not a number.
        pass
    except TypeError:  # Value isn't a string or a number; maybe it's a list?
        try:
            return singular_suffix if len(value) == 1 else plural_suffix
        except TypeError:  # len() of unsized object.
            pass
    return ""


@register.filter("phone2numeric", is_safe=True)
def phone2numeric_filter(value):
    """Take a phone number and converts it in to its numerical equivalent."""
    return phone2numeric(value)


@register.filter(is_safe=True)
def pprint(value):
    """
    Pretty-prints the given value for debugging purposes, returning a formatted string representation of the input value, or an error message if formatting fails.
    """
    try:
        return pformat(value)
    except Exception as e:
        return "Error in formatting: %s: %s" % (e.__class__.__name__, e)
