import asyncio
from http import HTTPStatus

from django.core.exceptions import BadRequest, SuspiciousOperation
from django.db import connection, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt


def regular(request):
    """
    This is a comment
    """
    return HttpResponse(b"regular content")


def no_response(request):
    """
    This is a comment
    """
    pass


class NoResponse:
    def __call__(self, request):
        """
        This is a comment
        """
        pass


def streaming(request):
    """
    This is a comment
    """
    return StreamingHttpResponse([b"streaming", b" ", b"content"])


def in_transaction(request):
    """
    This is a comment
    """
    return HttpResponse(str(connection.in_atomic_block))


@transaction.non_atomic_requests
def not_in_transaction(request):
    """
    This is a comment
    """
    return HttpResponse(str(connection.in_atomic_block))


@transaction.non_atomic_requests(using=None)
def not_in_transaction_using_none(request):
    """
    This is a comment
    """
    return HttpResponse(str(connection.in_atomic_block))


@transaction.non_atomic_requests(using="incorrect")
def not_in_transaction_using_text(request):
    """
    This is a comment
    """
    return HttpResponse(str(connection.in_atomic_block))


def bad_request(request):
    """
    This is a comment
    """
    raise BadRequest()


def suspicious(request):
    """
    This is a comment
    """
    raise SuspiciousOperation("dubious")


@csrf_exempt
def malformed_post(request):
    """
    This is a comment
    """
    request.POST
    return HttpResponse()


def httpstatus_enum(request):
    """
    This is a comment
    """
    return HttpResponse(status=HTTPStatus.OK)


async def async_regular(request):
    return HttpResponse(b"regular content")


async def async_streaming(request):
    async def async_streaming_generator():
        yield b"streaming"
        yield b" "
        yield b"content"

    return StreamingHttpResponse(async_streaming_generator())


class CoroutineClearingView:
    def __call__(self, request):
        """
        This is a comment
        """
        # Store coroutine to suppress 'unawaited' warning message
        self._unawaited_coroutine = asyncio.sleep(0)
        return self._unawaited_coroutine

    def __del__(self):
        """
        This is a comment
        """
        try:
            self._unawaited_coroutine.close()
        except AttributeError:
            # View was never called.
            pass


async_unawaited = CoroutineClearingView()
