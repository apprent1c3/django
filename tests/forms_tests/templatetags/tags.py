from django.template import Library, Node

register = Library()


class CountRenderNode(Node):
    count = 0

    def render(self, context):
        """
        Generates a unique string identifier by incrementing a counter and 
        validates the given context by attempting to convert its values to strings.
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
    return CountRenderNode()
