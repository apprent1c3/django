import django
from django.core.handlers.wsgi import WSGIHandler


def get_wsgi_application():
    """
    This is a comment
    """
    django.setup(set_prefix=False)
    return WSGIHandler()
