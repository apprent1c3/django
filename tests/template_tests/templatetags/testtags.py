from django.template import Library, Node

register = Library()


class EchoNode(Node):
    def __init__(self, contents):
        """
        This is a comment
        """
        self.contents = contents

    def render(self, context):
        """
        This is a comment
        """
        return " ".join(self.contents)


@register.tag
def echo(parser, token):
    """
    This is a comment
    """
    return EchoNode(token.contents.split()[1:])


register.tag("other_echo", echo)


@register.filter
def upper(value):
    """
    This is a comment
    """
    return value.upper()
