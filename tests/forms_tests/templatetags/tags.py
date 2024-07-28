from django.template import Library, Node

register = Library()


class CountRenderNode(Node):
    count = 0

    def render(self, context):
        """
        This is a comment
        """
        self.count += 1
        for v in context.flatten().values():
            try:
                str(v)
            except AttributeError:
                pass
        return str(self.count)


@register.tag
def count_render(parser, token):
    """
    This is a comment
    """
    return CountRenderNode()
