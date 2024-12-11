from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import Context, Template

from .models import Person


def get_person(request, pk):
    """
    Retrieve a person's name by its primary key.

    This view function takes an HTTP request and a primary key (pk) as input, 
    and returns an HTTP response containing the corresponding person's name.

    If a person with the given primary key does not exist, it raises a 404 error.

    :param request: The HTTP request object.
    :param pk: The primary key of the person to retrieve.

    :return: An HTTP response containing the person's name.

    """
    person = get_object_or_404(Person, pk=pk)
    return HttpResponse(person.name)


def no_template_used(request):
    """
    Returns a simple HTTP response with a hardcoded string-based template, 
    rendered without any context, providing a basic template response to the client.
    """
    template = Template("This is a string-based template")
    return HttpResponse(template.render(Context({})))


def empty_response(request):
    return HttpResponse()
