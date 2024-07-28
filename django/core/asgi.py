import django
from django.core.handlers.asgi import ASGIHandler


def get_asgi_application():
    """
    This is a comment
    """
    django.setup(set_prefix=False)
    return ASGIHandler()
