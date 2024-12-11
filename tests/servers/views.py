from urllib.request import urlopen

from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Person


def example_view(request):
    return HttpResponse("example view")


def streaming_example_view(request):
    return StreamingHttpResponse((b"I", b"am", b"a", b"stream"))


def model_view(request):
    people = Person.objects.all()
    return HttpResponse("\n".join(person.name for person in people))


def create_model_instance(request):
    """

        Creates and saves a new instance of the Person model.

        Responds to the request by generating a default model instance with a predefined name,
        persisting it to the database, and returning a successful HTTP response.

        :param request: The incoming HTTP request
        :return: An HTTP response indicating the outcome of the operation

    """
    person = Person(name="emily")
    person.save()
    return HttpResponse()


def environ_view(request):
    return HttpResponse(
        "\n".join("%s: %r" % (k, v) for k, v in request.environ.items())
    )


def subview(request):
    return HttpResponse("subview")


def subview_calling_view(request):
    """

    Makes an HTTP request to the provided URL's subview endpoint and returns the response.

    The function uses the provided URL, appends '/subview/' to it, and sends a GET request to the resulting URL.
    It then captures the response, decodes it, and returns it as part of an HttpResponse.

    The function expects the URL to be provided as a 'url' parameter in the request's GET data.

    Returns:
        HttpResponse: A response containing the result of the subview request.

    """
    with urlopen(request.GET["url"] + "/subview/") as response:
        return HttpResponse("subview calling view: {}".format(response.read().decode()))


def check_model_instance_from_subview(request):
    """
    Checks if a model instance can be created from a subview by making a request to the specified URL and then retrieves the corresponding model view.

    Args:
        request: The current HTTP request object containing the URL to check.

    Returns:
        An HTTP response containing the result of calling the model view from the subview.

    Note:
        The function expects the 'url' parameter to be present in the request's GET parameters.
    """
    with urlopen(request.GET["url"] + "/create_model_instance/"):
        pass
    with urlopen(request.GET["url"] + "/model_view/") as response:
        return HttpResponse("subview calling view: {}".format(response.read().decode()))


@csrf_exempt
def method_view(request):
    return HttpResponse(request.method)
