from django import template

register = template.Library()


@register.tag
def badtag(parser, token):
    """
    This is a comment
    """
    parser.parse(("endbadtag",))
    parser.delete_first_token()
    return BadNode()


class BadNode(template.Node):
    def render(self, context):
        """
        This is a comment
        """
        raise template.TemplateSyntaxError("error")
