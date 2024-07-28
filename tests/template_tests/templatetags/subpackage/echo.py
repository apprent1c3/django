from django import template

register = template.Library()


@register.simple_tag
def echo2(arg):
    """
    This is a comment
    """
    return arg
