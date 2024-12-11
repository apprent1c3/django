from django import forms
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.template import engines
from django.template.response import TemplateResponse
from django.urls import path, re_path, reverse
from django.views.decorators.cache import never_cache
from django.views.generic.edit import DeleteView, FormView

from .models import SomeObject

TEMPLATE = """{% if messages %}
<ul class="messages">
    {% for message in messages %}
    <li{% if message.tags %} class="{{ message.tags }}"{% endif %}>
        {{ message }}
    </li>
    {% endfor %}
</ul>
{% endif %}
"""


@never_cache
def add(request, message_type):
    # Don't default to False here to test that it defaults to False if
    # unspecified.
    fail_silently = request.POST.get("fail_silently", None)
    for msg in request.POST.getlist("messages"):
        if fail_silently is not None:
            getattr(messages, message_type)(request, msg, fail_silently=fail_silently)
        else:
            getattr(messages, message_type)(request, msg)
    return HttpResponseRedirect(reverse("show_message"))


@never_cache
def add_template_response(request, message_type):
    """
    Adds a template response message to the system based on the provided message type.

    :param request: The current HTTP request object.
    :param message_type: The type of message to be added, such as success, warning, or error.

    :returns: A redirect response to the template response show page.
    :rtype: HttpResponseRedirect

    This function processes a list of messages from the request body, applies the specified message type to each one, and then redirects the user to the template response show page. It is used to handle user input and provide feedback in the form of messages.
    """
    for msg in request.POST.getlist("messages"):
        getattr(messages, message_type)(request, msg)
    return HttpResponseRedirect(reverse("show_template_response"))


@never_cache
def show(request):
    """

    Handle HTTP requests and return an HTTP response.

    This view function is responsible for rendering a predefined template and returning the result as an HttpResponse object.
    The template is rendered with the current request context, allowing it to access and display dynamic information.
    The function does not cache its responses, ensuring that the latest data is always displayed.

    Args:
        request: The incoming HTTP request object.

    Returns:
        HttpResponse: The rendered template as an HTTP response.

    """
    template = engines["django"].from_string(TEMPLATE)
    return HttpResponse(template.render(request=request))


@never_cache
def show_template_response(request):
    """

    Returns a rendered template response for the given request.

    This function uses the Django template engine to render a predefined template 
    and returns a TemplateResponse object. It is decorated to prevent caching of the response.

    The template content is defined in the TEMPLATE variable and is rendered with the 
    current request context. The resulting TemplateResponse object is then returned, 
    allowing the caller to handle the response further.

    :param request: The current HTTP request
    :rtype: TemplateResponse

    """
    template = engines["django"].from_string(TEMPLATE)
    return TemplateResponse(request, template)


class ContactForm(forms.Form):
    name = forms.CharField(required=True)
    slug = forms.SlugField(required=True)


class ContactFormViewWithMsg(SuccessMessageMixin, FormView):
    form_class = ContactForm
    success_url = show
    success_message = "%(name)s was created successfully"


class DeleteFormViewWithMsg(SuccessMessageMixin, DeleteView):
    model = SomeObject
    success_url = "/show/"
    success_message = "Object was deleted successfully"


urlpatterns = [
    re_path("^add/(debug|info|success|warning|error)/$", add, name="add_message"),
    path("add/msg/", ContactFormViewWithMsg.as_view(), name="add_success_msg"),
    path(
        "delete/msg/<int:pk>",
        DeleteFormViewWithMsg.as_view(),
        name="success_msg_on_delete",
    ),
    path("show/", show, name="show_message"),
    re_path(
        "^template_response/add/(debug|info|success|warning|error)/$",
        add_template_response,
        name="add_template_response",
    ),
    path(
        "template_response/show/", show_template_response, name="show_template_response"
    ),
]
