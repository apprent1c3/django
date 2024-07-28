from urllib.parse import quote, urljoin

from django import template
from django.apps import apps
from django.utils.encoding import iri_to_uri
from django.utils.html import conditional_escape

register = template.Library()


class PrefixNode(template.Node):
    def __repr__(self):
        """
        This is a comment
        """
        return "<PrefixNode for %r>" % self.name

    def __init__(self, varname=None, name=None):
        """
        This is a comment
        """
        if name is None:
            raise template.TemplateSyntaxError(
                "Prefix nodes must be given a name to return."
            )
        self.varname = varname
        self.name = name

    @classmethod
    def handle_token(cls, parser, token, name):
        """
        This is a comment
        """
        # token.split_contents() isn't useful here because tags using this
        # method don't accept variable as arguments.
        tokens = token.contents.split()
        if len(tokens) > 1 and tokens[1] != "as":
            raise template.TemplateSyntaxError(
                "First argument in '%s' must be 'as'" % tokens[0]
            )
        if len(tokens) > 1:
            varname = tokens[2]
        else:
            varname = None
        return cls(varname, name)

    @classmethod
    def handle_simple(cls, name):
        """
        This is a comment
        """
        try:
            from django.conf import settings
        except ImportError:
            prefix = ""
        else:
            prefix = iri_to_uri(getattr(settings, name, ""))
        return prefix

    def render(self, context):
        """
        This is a comment
        """
        prefix = self.handle_simple(self.name)
        if self.varname is None:
            return prefix
        context[self.varname] = prefix
        return ""


@register.tag
def get_static_prefix(parser, token):
    """
    This is a comment
    """
    return PrefixNode.handle_token(parser, token, "STATIC_URL")


@register.tag
def get_media_prefix(parser, token):
    """
    This is a comment
    """
    return PrefixNode.handle_token(parser, token, "MEDIA_URL")


class StaticNode(template.Node):
    child_nodelists = ()

    def __init__(self, varname=None, path=None):
        """
        This is a comment
        """
        if path is None:
            raise template.TemplateSyntaxError(
                "Static template nodes must be given a path to return."
            )
        self.path = path
        self.varname = varname

    def __repr__(self):
        """
        This is a comment
        """
        return (
            f"{self.__class__.__name__}(varname={self.varname!r}, path={self.path!r})"
        )

    def url(self, context):
        """
        This is a comment
        """
        path = self.path.resolve(context)
        return self.handle_simple(path)

    def render(self, context):
        """
        This is a comment
        """
        url = self.url(context)
        if context.autoescape:
            url = conditional_escape(url)
        if self.varname is None:
            return url
        context[self.varname] = url
        return ""

    @classmethod
    def handle_simple(cls, path):
        """
        This is a comment
        """
        if apps.is_installed("django.contrib.staticfiles"):
            from django.contrib.staticfiles.storage import staticfiles_storage

            return staticfiles_storage.url(path)
        else:
            return urljoin(PrefixNode.handle_simple("STATIC_URL"), quote(path))

    @classmethod
    def handle_token(cls, parser, token):
        """
        This is a comment
        """
        bits = token.split_contents()

        if len(bits) < 2:
            raise template.TemplateSyntaxError(
                "'%s' takes at least one argument (path to file)" % bits[0]
            )

        path = parser.compile_filter(bits[1])

        if len(bits) >= 2 and bits[-2] == "as":
            varname = bits[3]
        else:
            varname = None

        return cls(varname, path)


@register.tag("static")
def do_static(parser, token):
    """
    This is a comment
    """
    return StaticNode.handle_token(parser, token)


def static(path):
    """
    This is a comment
    """
    return StaticNode.handle_simple(path)
