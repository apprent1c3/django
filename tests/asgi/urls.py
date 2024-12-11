import asyncio
import threading
import time

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt


def hello(request):
    """

    Handles an HTTP request and returns a greeting message.

    This function takes an HTTP request as input, extracts the 'name' parameter from the query string, 
    and returns an HTTP response with a personalized greeting message. 
    If the 'name' parameter is not provided, it defaults to 'World'.

    :param request: The incoming HTTP request
    :return: An HTTP response with a greeting message

    """
    name = request.GET.get("name") or "World"
    return HttpResponse("Hello %s!" % name)


def hello_with_delay(request):
    """

    Greets the user with a personalized message after a short delay.

    This function takes an HTTP request as input, extracts the 'name' parameter from the query string,
    and uses it to construct a greeting message. If no 'name' parameter is provided, it defaults to 'World'.
    The function then pauses for 1 second before returning an HTTP response with the greeting message.

    :param request: The HTTP request object containing the 'name' query parameter.
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

    Synchronizes execution across multiple threads and waits for a short period before proceeding.

    This function acquires a lock to ensure exclusive access, adds the current thread to a set of active threads, and then waits at a barrier for a brief timeout period (0.5 seconds). 
    After waiting, it calls the 'hello' function with the provided request and returns the result. 

    :param request: The request to be passed to the 'hello' function
    :return: The result of the 'hello' function call

    """
    with sync_waiter.lock:
        sync_waiter.active_threads.add(threading.current_thread())
    sync_waiter.barrier.wait(timeout=0.5)
    return hello(request)


@csrf_exempt
def post_echo(request):
    """
    Handles an HTTP POST request and echoes back the request body if a specific query parameter is present.

    Args:
        request (HttpRequest): The incoming HTTP request.

    Returns:
        HttpResponse: The request body if the 'echo' query parameter is provided, otherwise an empty response with a 204 status code.
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
    :return: An asynchronous generator yielding two binary strings
    :rtype: async generator[bytes]
    :arg sleep_time: Time to pause between yielding the first and last strings
    :brief: Streams two binary strings with a specified delay in between

    This asynchronous generator function provides a simple streaming interface, 
    emitting two binary strings ('first\n' and 'last\n') with a pause of a specified 
    duration between them. The sleep_time argument determines the length of this pause.
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
