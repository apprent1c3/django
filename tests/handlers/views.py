import asyncio
from http import HTTPStatus

from django.core.exceptions import BadRequest, SuspiciousOperation
from django.db import connection, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt


def regular(request):
    return HttpResponse(b"regular content")


def no_response(request):
    pass


class NoResponse:
    def __call__(self, request):
        pass


def streaming(request):
    return StreamingHttpResponse([b"streaming", b" ", b"content"])


def in_transaction(request):
    return HttpResponse(str(connection.in_atomic_block))


@transaction.non_atomic_requests
def not_in_transaction(request):
    return HttpResponse(str(connection.in_atomic_block))


@transaction.non_atomic_requests(using=None)
def not_in_transaction_using_none(request):
    return HttpResponse(str(connection.in_atomic_block))


@transaction.non_atomic_requests(using="incorrect")
def not_in_transaction_using_text(request):
    return HttpResponse(str(connection.in_atomic_block))


def bad_request(request):
    raise BadRequest()


def suspicious(request):
    raise SuspiciousOperation("dubious")


@csrf_exempt
def malformed_post(request):
    """
    Occurs when an HTTP POST request is made with a malformed or empty request body.
    This view handles such requests, processing the request data and returning an HTTP response.
    It is exempt from Cross-Site Request Forgery protection due to its handling of potentially compromised requests.
    """
    request.POST
    return HttpResponse()


def httpstatus_enum(request):
    return HttpResponse(status=HTTPStatus.OK)


async def async_regular(request):
    return HttpResponse(b"regular content")


async def async_streaming(request):
    async def async_streaming_generator():
        """
        Asynchronous generator function producing a streaming content.

        This function generates a sequence of bytes, allowing for efficient 
        streaming of data. It yields each chunk of the content one at a time, 
        enabling asynchronous processing and reducing memory usage.

        Yields:
            bytes: A chunk of the streaming content.

        """
        yield b"streaming"
        yield b" "
        yield b"content"

    return StreamingHttpResponse(async_streaming_generator())


class CoroutineClearingView:
    def __call__(self, request):
        """Return an unawaited coroutine (common error for async views)."""
        # Store coroutine to suppress 'unawaited' warning message
        self._unawaited_coroutine = asyncio.sleep(0)
        return self._unawaited_coroutine

    def __del__(self):
        """
        Destructor method to ensure cleanup of internal resources.

        When an instance of this class is about to be destroyed, this method is called to properly clean up any internal coroutines that may still be active. It attempts to close the unawaited coroutine if it exists, and silently ignores any instances where the coroutine attribute is not present.
        """
        try:
            self._unawaited_coroutine.close()
        except AttributeError:
            # View was never called.
            pass


async_unawaited = CoroutineClearingView()
