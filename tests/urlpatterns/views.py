from django.http import HttpResponse


def empty_view(request, *args, **kwargs):
    """
    This is a comment
    """
    return HttpResponse()
