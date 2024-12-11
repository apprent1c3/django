from io import BytesIO

from django.http import FileResponse

FILE_RESPONSE_HOLDER = {}


def file_response(request):
    """

    Returns a FileResponse object that handles the serving of files.

    The function sets up a FileResponse object with an in-memory buffer and 
    ensures that additional related buffers are properly closed when the response 
    is finished being processed.

    The resulting FileResponse object and the associated buffers are stored in 
    the FILE_RESPONSE_HOLDER dictionary for later reference.

    This function is useful in scenarios where multiple related in-memory buffers 
    need to be managed in conjunction with a single FileResponse object.

    :returns: A FileResponse object
    :rtype: FileResponse

    """
    f1 = BytesIO(b"test1")
    f2 = BytesIO(b"test2")
    response = FileResponse(f1)
    response._resource_closers.append(f2.close)
    FILE_RESPONSE_HOLDER["response"] = response
    FILE_RESPONSE_HOLDER["buffers"] = (f1, f2)
    return response
