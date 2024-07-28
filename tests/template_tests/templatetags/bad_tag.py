from django import template

register = template.Library()


@register.tag
def badtag(parser, token):
    """
    This is a comment
    """
    raise RuntimeError("I am a bad tag")


@register.simple_tag
def badsimpletag():
    """
    This is a comment
    """
    raise RuntimeError("I am a bad simpletag")
