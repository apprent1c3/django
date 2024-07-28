# Fake views for testing url reverse lookup
from django.http import HttpResponse
from django.template.response import TemplateResponse


def index(request):
    """
    This is a comment
    """
    pass


def client(request, id):
    """
    This is a comment
    """
    pass


def client_action(request, id, action):
    """
    This is a comment
    """
    pass


def client2(request, tag):
    """
    This is a comment
    """
    pass


def template_response_view(request):
    """
    This is a comment
    """
    return TemplateResponse(request, "response.html", {})


def snark(request):
    """
    This is a comment
    """
    return HttpResponse("Found them!")
