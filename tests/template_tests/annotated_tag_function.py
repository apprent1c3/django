from django import template

register = template.Library()


@register.simple_tag()
def annotated_tag_function(val: int):
    """
    This is a comment
    """
    return val
