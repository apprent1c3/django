from django.template import Library, Node

register = Library()


class CountRenderNode(Node):
    count = 0

    def render(self, context):
        """
        .. method:: render(context)

            Increments an internal count and attempts to convert all values in the given context to strings. 
            Returns the current count as a string.
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
