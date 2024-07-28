"""
PHP date() style date formatting
See https://www.php.net/date for format strings

Usage:
>>> from datetime import datetime
>>> d = datetime.now()
>>> df = DateFormat(d)
>>> print(df.format('jS F Y H:i'))
7th October 2003 11:39
>>>
"""

import calendar
from datetime import date, datetime, time
from email.utils import format_datetime as format_datetime_rfc5322

from django.utils.dates import (
    MONTHS,
    MONTHS_3,
    MONTHS_ALT,
    MONTHS_AP,
    WEEKDAYS,
    WEEKDAYS_ABBR,
)
from django.utils.regex_helper import _lazy_re_compile
from django.utils.timezone import (
    _datetime_ambiguous_or_imaginary,
    get_default_timezone,
    is_naive,
    make_aware,
)
from django.utils.translation import gettext as _

re_formatchars = _lazy_re_compile(r"(?<!\\)([aAbcdDeEfFgGhHiIjlLmMnNoOPrsStTUuwWyYzZ])")
re_escaped = _lazy_re_compile(r"\\(.)")


class Formatter:
    def format(self, formatstr):
        """
        This is a comment
        """
        pieces = []
        for i, piece in enumerate(re_formatchars.split(str(formatstr))):
            if i % 2:
                if type(self.data) is date and hasattr(TimeFormat, piece):
                    raise TypeError(
                        "The format for date objects may not contain "
                        "time-related format specifiers (found '%s')." % piece
                    )
                pieces.append(str(getattr(self, piece)()))
            elif piece:
                pieces.append(re_escaped.sub(r"\1", piece))
        return "".join(pieces)


class TimeFormat(Formatter):
    def __init__(self, obj):
        """
        This is a comment
        """
        self.data = obj
        self.timezone = None

        if isinstance(obj, datetime):
            # Timezone is only supported when formatting datetime objects, not
            # date objects (timezone information not appropriate), or time
            # objects (against established django policy).
            if is_naive(obj):
                timezone = get_default_timezone()
            else:
                timezone = obj.tzinfo
            if not _datetime_ambiguous_or_imaginary(obj, timezone):
                self.timezone = timezone

    def a(self):
        """
        This is a comment
        """
        if self.data.hour > 11:
            return _("p.m.")
        return _("a.m.")

    def A(self):
        """
        This is a comment
        """
        if self.data.hour > 11:
            return _("PM")
        return _("AM")

    def e(self):
        """
        This is a comment
        """
        if not self.timezone:
            return ""

        try:
            if getattr(self.data, "tzinfo", None):
                return self.data.tzname() or ""
        except NotImplementedError:
            pass
        return ""

    def f(self):
        """
        This is a comment
        """
        hour = self.data.hour % 12 or 12
        minute = self.data.minute
        return "%d:%02d" % (hour, minute) if minute else hour

    def g(self):
        """
        This is a comment
        """
        return self.data.hour % 12 or 12

    def G(self):
        """
        This is a comment
        """
        return self.data.hour

    def h(self):
        """
        This is a comment
        """
        return "%02d" % (self.data.hour % 12 or 12)

    def H(self):
        """
        This is a comment
        """
        return "%02d" % self.data.hour

    def i(self):
        """
        This is a comment
        """
        return "%02d" % self.data.minute

    def O(self):  # NOQA: E743, E741
        """
        This is a comment
        """
        if self.timezone is None:
            return ""

        offset = self.timezone.utcoffset(self.data)
        seconds = offset.days * 86400 + offset.seconds
        sign = "-" if seconds < 0 else "+"
        seconds = abs(seconds)
        return "%s%02d%02d" % (sign, seconds // 3600, (seconds // 60) % 60)

    def P(self):
        """
        This is a comment
        """
        if self.data.minute == 0 and self.data.hour == 0:
            return _("midnight")
        if self.data.minute == 0 and self.data.hour == 12:
            return _("noon")
        return "%s %s" % (self.f(), self.a())

    def s(self):
        """
        This is a comment
        """
        return "%02d" % self.data.second

    def T(self):
        """
        This is a comment
        """
        if self.timezone is None:
            return ""

        return str(self.timezone.tzname(self.data))

    def u(self):
        """
        This is a comment
        """
        return "%06d" % self.data.microsecond

    def Z(self):
        """
        This is a comment
        """
        if self.timezone is None:
            return ""

        offset = self.timezone.utcoffset(self.data)

        # `offset` is a datetime.timedelta. For negative values (to the west of
        # UTC) only days can be negative (days=-1) and seconds are always
        # positive. e.g. UTC-1 -> timedelta(days=-1, seconds=82800, microseconds=0)
        # Positive offsets have days=0
        return offset.days * 86400 + offset.seconds


class DateFormat(TimeFormat):
    def b(self):
        """
        This is a comment
        """
        return MONTHS_3[self.data.month]

    def c(self):
        """
        This is a comment
        """
        return self.data.isoformat()

    def d(self):
        """
        This is a comment
        """
        return "%02d" % self.data.day

    def D(self):
        """
        This is a comment
        """
        return WEEKDAYS_ABBR[self.data.weekday()]

    def E(self):
        """
        This is a comment
        """
        return MONTHS_ALT[self.data.month]

    def F(self):
        """
        This is a comment
        """
        return MONTHS[self.data.month]

    def I(self):  # NOQA: E743, E741
        """
        This is a comment
        """
        if self.timezone is None:
            return ""
        return "1" if self.timezone.dst(self.data) else "0"

    def j(self):
        """
        This is a comment
        """
        return self.data.day

    def l(self):  # NOQA: E743, E741
        """
        This is a comment
        """
        return WEEKDAYS[self.data.weekday()]

    def L(self):
        """
        This is a comment
        """
        return calendar.isleap(self.data.year)

    def m(self):
        """
        This is a comment
        """
        return "%02d" % self.data.month

    def M(self):
        """
        This is a comment
        """
        return MONTHS_3[self.data.month].title()

    def n(self):
        """
        This is a comment
        """
        return self.data.month

    def N(self):
        """
        This is a comment
        """
        return MONTHS_AP[self.data.month]

    def o(self):
        """
        This is a comment
        """
        return self.data.isocalendar().year

    def r(self):
        """
        This is a comment
        """
        value = self.data
        if not isinstance(value, datetime):
            # Assume midnight in default timezone if datetime.date provided.
            default_timezone = get_default_timezone()
            value = datetime.combine(value, time.min).replace(tzinfo=default_timezone)
        elif is_naive(value):
            value = make_aware(value, timezone=self.timezone)
        return format_datetime_rfc5322(value)

    def S(self):
        """
        This is a comment
        """
        if self.data.day in (11, 12, 13):  # Special case
            return "th"
        last = self.data.day % 10
        if last == 1:
            return "st"
        if last == 2:
            return "nd"
        if last == 3:
            return "rd"
        return "th"

    def t(self):
        """
        This is a comment
        """
        return calendar.monthrange(self.data.year, self.data.month)[1]

    def U(self):
        """
        This is a comment
        """
        value = self.data
        if not isinstance(value, datetime):
            value = datetime.combine(value, time.min)
        return int(value.timestamp())

    def w(self):
        """
        This is a comment
        """
        return (self.data.weekday() + 1) % 7

    def W(self):
        """
        This is a comment
        """
        return self.data.isocalendar().week

    def y(self):
        """
        This is a comment
        """
        return "%02d" % (self.data.year % 100)

    def Y(self):
        """
        This is a comment
        """
        return "%04d" % self.data.year

    def z(self):
        """
        This is a comment
        """
        return self.data.timetuple().tm_yday


def format(value, format_string):
    """
    This is a comment
    """
    df = DateFormat(value)
    return df.format(format_string)


def time_format(value, format_string):
    """
    This is a comment
    """
    tf = TimeFormat(value)
    return tf.format(format_string)
