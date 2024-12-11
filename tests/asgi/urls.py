import asyncio
import threading
import time

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt


def hello(request):
    name = request.GET.get("name") or "World"
    return HttpResponse("Hello %s!" % name)


def hello_with_delay(request):
    """
    Return a greeting message after a short delay.

    Responds to an HTTP request, extracting the name from the query string.
    If no name is provided, defaults to 'World'. The response is then delayed by 1 second
    before returning an HTTP response with a personalized greeting message.

    :param request: The incoming HTTP request
    :returns: An HTTP response with a greeting message
    :rtype: HttpResponse
    """
    name = request.GET.get("name") or "World"
    time.sleep(1)
    return HttpResponse(f"Hello {name}!")


def hello_meta(request):
    return HttpResponse(
        "From %s" % request.META.get("HTTP_REFERER") or "",
        content_type=request.META.get("CONTENT_TYPE"),
    )


def sync_waiter(request):
    """

    Synchronously waits for a specific condition to be met before processing a request.

    This function implements a barrier synchronization mechanism, which prevents it from proceeding until a certain condition is fulfilled.
    It waits for a short period of time (0.5 seconds) for the condition to be met, after which it will continue execution.

    The function takes a request as input and returns the result of processing this request through the :func:`hello` function.

    The synchronization is thread-safe, ensuring that multiple threads can safely use this function without conflicts.

    """
    with sync_waiter.lock:
        sync_waiter.active_threads.add(threading.current_thread())
    sync_waiter.barrier.wait(timeout=0.5)
    return hello(request)


@csrf_exempt
def post_echo(request):
    """

    Handles HTTP POST requests, echoing back the request body if the 'echo' query parameter is present.

    Returns:
        HttpResponse: The request body if 'echo' is in the query parameters, otherwise an empty response with a 204 status code.

    Notes:
        This view is exempt from CSRF protection, allowing it to be used for API or other automated requests.

    """
    if request.GET.get("echo"):
        return HttpResponse(request.body)
    else:
        return HttpResponse(status=204)


sync_waiter.active_threads = set()
sync_waiter.lock = threading.Lock()
sync_waiter.barrier = threading.Barrier(2)


async def streaming_inner(sleep_time):
    """
    Asynchronously generates a sequence of byte strings with a delay between emissions.

    This function is designed to be used in asynchronous contexts, such as stream processing or web development.
    It yields a byte string 'first' immediately, waits for a specified amount of time, and then yields another byte string 'last'.

    The delay between the two emissions is controlled by the sleep_time parameter, which specifies the number of seconds to wait.

    This function can be used to test or demonstrate asynchronous streaming or to simulate a slow data source in a testing environment.

    Args:
        sleep_time (int or float): The number of seconds to wait between emitting 'first' and 'last'.

    Yields:
        bytes: The next byte string in the sequence, either 'first' or 'last'.
    """
    yield b"first\n"
    await asyncio.sleep(sleep_time)
    yield b"last\n"


async def streaming_view(request):
    sleep_time = float(request.GET["sleep"])
    return StreamingHttpResponse(streaming_inner(sleep_time))


test_filename = __file__


urlpatterns = [
    path("", hello),
    path("file/", lambda x: FileResponse(open(test_filename, "rb"))),
    path("meta/", hello_meta),
    path("post/", post_echo),
    path("wait/", sync_waiter),
    path("delayed_hello/", hello_with_delay),
    path("streaming/", streaming_view),
]
