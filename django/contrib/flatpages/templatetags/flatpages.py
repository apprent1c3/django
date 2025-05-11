from django import template
from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.shortcuts import get_current_site

register = template.Library()


class FlatpageNode(template.Node):
    def __init__(self, context_name, starts_with=None, user=None):
        """
        Initializes a context filter with a given name and optional prefix and user filters.

        :param context_name: The name of the context to filter.
        :param starts_with: Optional prefix to filter the context by.
        :param user: Optional user to filter the context by.
        """
        self.context_name = context_name
        if starts_with:
            self.starts_with = template.Variable(starts_with)
        else:
            self.starts_with = None
        if user:
            self.user = template.Variable(user)
        else:
            self.user = None

    def render(self, context):
        """
        Renders a list of flatpages filtered by the current site, authentication status, and optional starts_with condition.

        Parameters
        ----------
        context : dict
            Template context containing the 'request' object (optional)

        Returns
        -------
        str
            Empty string. The filtered flatpages are stored in the context under the key specified by `context_name`.

        Note
        ----
        The function applies the following filters: site ID (determined by the 'request' object or settings), starts_with condition (if specified), and authentication status (if user is not authenticated, only non-registration required flatpages are included).
        """
        if "request" in context:
            site_pk = get_current_site(context["request"]).pk
        else:
            site_pk = settings.SITE_ID
        flatpages = FlatPage.objects.filter(sites__id=site_pk)
        # If a prefix was specified, add a filter
        if self.starts_with:
            flatpages = flatpages.filter(
                url__startswith=self.starts_with.resolve(context)
            )

        # If the provided user is not authenticated, or no user
        # was provided, filter the list to only public flatpages.
        if self.user:
            user = self.user.resolve(context)
            if not user.is_authenticated:
                flatpages = flatpages.filter(registration_required=False)
        else:
            flatpages = flatpages.filter(registration_required=False)

        context[self.context_name] = flatpages
        return ""


@register.tag
def get_flatpages(parser, token):
    """
    Retrieve all flatpage objects available for the current site and visible to the specific user, populating the template context with them in a variable.

    The function allows filtering by a user and a URL prefix, returning only the flatpages that match these criteria.

    Syntax and example usage are provided to facilitate template integration.
    """
    bits = token.split_contents()
    syntax_message = (
        "%(tag_name)s expects a syntax of %(tag_name)s "
        "['url_starts_with'] [for user] as context_name" % {"tag_name": bits[0]}
    )
    # Must have at 3-6 bits in the tag
    if 3 <= len(bits) <= 6:
        # If there's an even number of bits, there's no prefix
        if len(bits) % 2 == 0:
            prefix = bits[1]
        else:
            prefix = None

        # The very last bit must be the context name
        if bits[-2] != "as":
            raise template.TemplateSyntaxError(syntax_message)
        context_name = bits[-1]

        # If there are 5 or 6 bits, there is a user defined
        if len(bits) >= 5:
            if bits[-4] != "for":
                raise template.TemplateSyntaxError(syntax_message)
            user = bits[-3]
        else:
            user = None

        return FlatpageNode(context_name, starts_with=prefix, user=user)
    else:
        raise template.TemplateSyntaxError(syntax_message)
