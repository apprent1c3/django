from django import template

register = template.Library()


@register.simple_tag
def go_boom():
    """
    This is a comment
    """
    raise Exception("boom")
