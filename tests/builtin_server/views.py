from io import BytesIO

from django.http import FileResponse

FILE_RESPONSE_HOLDER = {}


def file_response(request):
    """

    Handles file response by returning a FileResponse object.

    This function generates in-memory file objects, creates a FileResponse instance with one of these files, 
    and ensures that both files are properly closed when necessary, even if an exception occurs.

    The function maintains a record of the current response and the associated file objects for later use.

    Returns:
        FileResponse: The response object containing a file for download.

    """
    f1 = BytesIO(b"test1")
    f2 = BytesIO(b"test2")
    response = FileResponse(f1)
    response._resource_closers.append(f2.close)
    FILE_RESPONSE_HOLDER["response"] = response
    FILE_RESPONSE_HOLDER["buffers"] = (f1, f2)
    return response
