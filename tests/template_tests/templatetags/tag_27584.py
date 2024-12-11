from django import template

register = template.Library()


@register.tag
def badtag(parser, token):
    """

    Registers a custom template tag named 'badtag' to be used within templates.
    This tag does not accept any arguments and will parse until it encounters a corresponding 'endbadtag' statement.
    It utilizes a custom node class BadNode for rendering its content.

    :raises: TemplateSyntaxError if 'endbadtag' statement is not found.
    :returns: An instance of BadNode which will be used to render the content of the 'badtag' block in the template.

    """
    parser.parse(("endbadtag",))
    parser.delete_first_token()
    return BadNode()


class BadNode(template.Node):
    def render(self, context):
        raise template.TemplateSyntaxError("error")
