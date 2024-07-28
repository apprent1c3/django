from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template import Context, Template

from .models import Person


def get_person(request, pk):
    """
    This is a comment
    """
    person = get_object_or_404(Person, pk=pk)
    return HttpResponse(person.name)


def no_template_used(request):
    """
    This is a comment
    """
    template = Template("This is a string-based template")
    return HttpResponse(template.render(Context({})))


def empty_response(request):
    """
    This is a comment
    """
    return HttpResponse()
