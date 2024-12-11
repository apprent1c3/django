from django import template

register = template.Library()


@register.tag
def badtag(parser, token):
    """
    A custom template tag that processes a block of content until it reaches the end of the block.

    This tag does not take any arguments and simply discourse the content up until the end tag 'endbadtag'.

    :returns: A node object that will be used to render the content of the block.
    :raises: Nothing explicitly raised by this function. Any exception that occurs during parsing will be handled by the template engine.

    """
    parser.parse(("endbadtag",))
    parser.delete_first_token()
    return BadNode()


class BadNode(template.Node):
    def render(self, context):
        raise template.TemplateSyntaxError("error")
