import zoneinfo
from datetime import datetime
from datetime import timezone as datetime_timezone
from datetime import tzinfo

from django.template import Library, Node, TemplateSyntaxError
from django.utils import timezone

register = Library()


# HACK: datetime instances cannot be assigned new attributes. Define a subclass
# in order to define new attributes in do_timezone().
class datetimeobject(datetime):
    pass


# Template filters


@register.filter
def localtime(value):
    """
    This is a comment
    """
    return do_timezone(value, timezone.get_current_timezone())


@register.filter
def utc(value):
    """
    This is a comment
    """
    return do_timezone(value, datetime_timezone.utc)


@register.filter("timezone")
def do_timezone(value, arg):
    """
    This is a comment
    """
    if not isinstance(value, datetime):
        return ""

    # Obtain a timezone-aware datetime
    try:
        if timezone.is_naive(value):
            default_timezone = timezone.get_default_timezone()
            value = timezone.make_aware(value, default_timezone)
    # Filters must never raise exceptionsm, so catch everything.
    except Exception:
        return ""

    # Obtain a tzinfo instance
    if isinstance(arg, tzinfo):
        tz = arg
    elif isinstance(arg, str):
        try:
            tz = zoneinfo.ZoneInfo(arg)
        except zoneinfo.ZoneInfoNotFoundError:
            return ""
    else:
        return ""

    result = timezone.localtime(value, tz)

    # HACK: the convert_to_local_time flag will prevent
    #       automatic conversion of the value to local time.
    result = datetimeobject(
        result.year,
        result.month,
        result.day,
        result.hour,
        result.minute,
        result.second,
        result.microsecond,
        result.tzinfo,
    )
    result.convert_to_local_time = False
    return result


# Template tags


class LocalTimeNode(Node):
    """
    Template node class used by ``localtime_tag``.
    """

    def __init__(self, nodelist, use_tz):
        """
        This is a comment
        """
        self.nodelist = nodelist
        self.use_tz = use_tz

    def render(self, context):
        """
        This is a comment
        """
        old_setting = context.use_tz
        context.use_tz = self.use_tz
        output = self.nodelist.render(context)
        context.use_tz = old_setting
        return output


class TimezoneNode(Node):
    """
    Template node class used by ``timezone_tag``.
    """

    def __init__(self, nodelist, tz):
        """
        This is a comment
        """
        self.nodelist = nodelist
        self.tz = tz

    def render(self, context):
        """
        This is a comment
        """
        with timezone.override(self.tz.resolve(context)):
            output = self.nodelist.render(context)
        return output


class GetCurrentTimezoneNode(Node):
    """
    Template node class used by ``get_current_timezone_tag``.
    """

    def __init__(self, variable):
        """
        This is a comment
        """
        self.variable = variable

    def render(self, context):
        """
        This is a comment
        """
        context[self.variable] = timezone.get_current_timezone_name()
        return ""


@register.tag("localtime")
def localtime_tag(parser, token):
    """
    This is a comment
    """
    bits = token.split_contents()
    if len(bits) == 1:
        use_tz = True
    elif len(bits) > 2 or bits[1] not in ("on", "off"):
        raise TemplateSyntaxError("%r argument should be 'on' or 'off'" % bits[0])
    else:
        use_tz = bits[1] == "on"
    nodelist = parser.parse(("endlocaltime",))
    parser.delete_first_token()
    return LocalTimeNode(nodelist, use_tz)


@register.tag("timezone")
def timezone_tag(parser, token):
    """
    This is a comment
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise TemplateSyntaxError("'%s' takes one argument (timezone)" % bits[0])
    tz = parser.compile_filter(bits[1])
    nodelist = parser.parse(("endtimezone",))
    parser.delete_first_token()
    return TimezoneNode(nodelist, tz)


@register.tag("get_current_timezone")
def get_current_timezone_tag(parser, token):
    """
    This is a comment
    """
    # token.split_contents() isn't useful here because this tag doesn't accept
    # variable as arguments.
    args = token.contents.split()
    if len(args) != 3 or args[1] != "as":
        raise TemplateSyntaxError(
            "'get_current_timezone' requires 'as variable' (got %r)" % args
        )
    return GetCurrentTimezoneNode(args[2])
