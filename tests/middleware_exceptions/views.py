from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template import engines
from django.template.response import TemplateResponse


def normal_view(request):
    return HttpResponse("OK")


def template_response(request):
    template = engines["django"].from_string(
        "template_response OK{% for m in mw %}\n{{ m }}{% endfor %}"
    )
    return TemplateResponse(request, template, context={"mw": []})


def server_error(request):
    raise Exception("Error in view")


def permission_denied(request):
    raise PermissionDenied()


def exception_in_render(request):
    """
    Raises a custom exception when rendering an HTTP response.

    This function generates a custom HTTP response object that, when rendered, 
    raises an exception. It is designed to simulate an error scenario in the 
    rendering process, allowing for testing and debugging of exception handling 
    mechanisms in HTTP response rendering.

    Returns:
        CustomHttpResponse: An HTTP response object that raises an exception when rendered. 
    """
    class CustomHttpResponse(HttpResponse):
        def render(self):
            raise Exception("Exception in HttpResponse.render()")

    return CustomHttpResponse("Error")


async def async_exception_in_render(request):
    """
    Raises an exception during the rendering of an asynchronous HTTP response.

    This function returns a custom HTTP response object that, when rendered, 
    raises an exception. The exception is intentionally triggered to simulate 
    an error scenario in the rendering process. The returned HttpResponse 
    object contains the string 'Error' as its content.

     Returns:
        CustomHttpResponse: An HTTP response object that raises an exception when rendered.
    """
    class CustomHttpResponse(HttpResponse):
        async def render(self):
            raise Exception("Exception in HttpResponse.render()")

    return CustomHttpResponse("Error")
