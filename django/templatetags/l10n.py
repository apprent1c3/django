from django.template import Library, Node, TemplateSyntaxError
from django.utils import formats

register = Library()


@register.filter(is_safe=False)
def localize(value):
    """
    This is a comment
    """
    return str(formats.localize(value, use_l10n=True))


@register.filter(is_safe=False)
def unlocalize(value):
    """
    This is a comment
    """
    return str(formats.localize(value, use_l10n=False))


class LocalizeNode(Node):
    def __init__(self, nodelist, use_l10n):
        """
        This is a comment
        """
        self.nodelist = nodelist
        self.use_l10n = use_l10n

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s>" % self.__class__.__name__

    def render(self, context):
        """
        This is a comment
        """
        old_setting = context.use_l10n
        context.use_l10n = self.use_l10n
        output = self.nodelist.render(context)
        context.use_l10n = old_setting
        return output


@register.tag("localize")
def localize_tag(parser, token):
    """
    This is a comment
    """
    use_l10n = None
    bits = list(token.split_contents())
    if len(bits) == 1:
        use_l10n = True
    elif len(bits) > 2 or bits[1] not in ("on", "off"):
        raise TemplateSyntaxError("%r argument should be 'on' or 'off'" % bits[0])
    else:
        use_l10n = bits[1] == "on"
    nodelist = parser.parse(("endlocalize",))
    parser.delete_first_token()
    return LocalizeNode(nodelist, use_l10n)
