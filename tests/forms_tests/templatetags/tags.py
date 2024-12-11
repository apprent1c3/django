from django.template import Library, Node

register = Library()


class CountRenderNode(Node):
    count = 0

    def render(self, context):
        """
        Renders the current state by iterating over the provided context and returns a string representation of the current count.

        The context is first flattened, and then each value is checked to ensure it can be converted to a string. If a value cannot be converted, it is silently ignored.

        The function increments an internal counter each time it is called and returns the current count as a string.

        :returns: A string representation of the current count.
        :rtype: str
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
