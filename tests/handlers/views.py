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
    request.POST
    return HttpResponse()


def httpstatus_enum(request):
    return HttpResponse(status=HTTPStatus.OK)


async def async_regular(request):
    return HttpResponse(b"regular content")


async def async_streaming(request):
    async def async_streaming_generator():
        """
        Asynchronous generator that produces a stream of bytes.

        This generator yields a sequence of byte strings, enabling asynchronous streaming of content.
        It can be used in applications where data needs to be processed in a streaming fashion,
        such as when handling large amounts of data or working with real-time data sources.

        Yields:
            bytes: The next chunk of the stream as a byte string
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
        Finalizer method to clean up resources when an instance is about to be destroyed.

        This method ensures that any open coroutines are properly closed to prevent resource leaks.
        If the instance does not have an unawaited coroutine, this method does nothing.
        """
        try:
            self._unawaited_coroutine.close()
        except AttributeError:
            # View was never called.
            pass


async_unawaited = CoroutineClearingView()
