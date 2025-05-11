from io import BytesIO

from django.http import FileResponse

FILE_RESPONSE_HOLDER = {}


def file_response(request):
    """

    Returns a FileResponse object containing in-memory data.

    The response is generated from a BytesIO buffer and includes a mechanism to
    ensure proper cleanup of additional related buffers.

    """
    f1 = BytesIO(b"test1")
    f2 = BytesIO(b"test2")
    response = FileResponse(f1)
    response._resource_closers.append(f2.close)
    FILE_RESPONSE_HOLDER["response"] = response
    FILE_RESPONSE_HOLDER["buffers"] = (f1, f2)
    return response
